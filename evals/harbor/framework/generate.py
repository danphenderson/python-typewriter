from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib  # type: ignore[import-not-found]
except ModuleNotFoundError:  # pragma: no cover - Python 3.10
    import tomli as tomllib


REPO_ROOT = Path(__file__).resolve().parents[3]
HARBOR_ROOT = REPO_ROOT / "evals" / "harbor"
SPECS_ROOT = HARBOR_ROOT / "specs"
FRAMEWORK_ROOT = HARBOR_ROOT / "framework"
CONTRACT_PATH = HARBOR_ROOT / "image" / "image-contract.toml"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "build" / "harbor" / "tasks"
DOCKER_COMPOSE = """services:
  main:
    network_mode: none
"""


class EvalBuildError(RuntimeError):
    """Raised when an eval cannot be materialized safely."""


@dataclass(frozen=True)
class EvalSpec:
    slug: str
    task_name: str
    task_version: str
    description: str
    base_ref: str
    solution_ref: str
    solution_paths: tuple[str, ...]
    hidden_test_files: tuple[str, ...]
    keywords: tuple[str, ...]
    difficulty: str
    category: str
    agent_timeout_sec: float
    verifier_timeout_sec: float
    cpus: int
    memory_mb: int
    storage_mb: int
    author_name: str
    author_email: str


def _run_git(*args: str, text: bool = True) -> str | bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=text,
    )
    return result.stdout


def _required_string(data: dict[str, Any], name: str) -> str:
    value = data.get(name)
    if not isinstance(value, str) or not value.strip():
        raise EvalBuildError(f"{name} must be a non-empty string")
    return value


def _string_tuple(data: dict[str, Any], name: str) -> tuple[str, ...]:
    value = data.get(name)
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
        raise EvalBuildError(f"{name} must be a non-empty list of strings")
    return tuple(value)


def load_spec(slug: str) -> tuple[EvalSpec, Path]:
    spec_dir = (SPECS_ROOT / slug).resolve()
    if spec_dir.parent != SPECS_ROOT.resolve():
        raise EvalBuildError(f"invalid eval slug: {slug!r}")

    spec_path = spec_dir / "spec.toml"
    if not spec_path.is_file():
        raise EvalBuildError(f"eval spec not found: {spec_path}")

    with spec_path.open("rb") as spec_file:
        data = tomllib.load(spec_file)

    if data.get("schema_version") != 1:
        raise EvalBuildError("spec schema_version must be 1")
    if _required_string(data, "slug") != slug:
        raise EvalBuildError("spec slug must match its directory name")

    spec = EvalSpec(
        slug=slug,
        task_name=_required_string(data, "task_name"),
        task_version=_required_string(data, "task_version"),
        description=_required_string(data, "description"),
        base_ref=_required_string(data, "base_ref"),
        solution_ref=_required_string(data, "solution_ref"),
        solution_paths=_string_tuple(data, "solution_paths"),
        hidden_test_files=_string_tuple(data, "hidden_test_files"),
        keywords=_string_tuple(data, "keywords"),
        difficulty=_required_string(data, "difficulty"),
        category=_required_string(data, "category"),
        agent_timeout_sec=float(data.get("agent_timeout_sec", 900.0)),
        verifier_timeout_sec=float(data.get("verifier_timeout_sec", 900.0)),
        cpus=int(data.get("cpus", 2)),
        memory_mb=int(data.get("memory_mb", 4096)),
        storage_mb=int(data.get("storage_mb", 10240)),
        author_name=_required_string(data, "author_name"),
        author_email=_required_string(data, "author_email"),
    )
    if spec.agent_timeout_sec <= 0 or spec.verifier_timeout_sec <= 0:
        raise EvalBuildError("timeouts must be positive")
    if spec.cpus <= 0 or spec.memory_mb <= 0 or spec.storage_mb <= 0:
        raise EvalBuildError("task resources must be positive")
    return spec, spec_dir


def _resolve_commit(ref: str) -> str:
    try:
        return str(_run_git("rev-parse", "--verify", f"{ref}^{{commit}}")).strip()
    except subprocess.CalledProcessError as exc:
        raise EvalBuildError(f"cannot resolve commit {ref!r}") from exc


def _validate_spec_paths(spec: EvalSpec, spec_dir: Path) -> None:
    for relative_path in (*spec.solution_paths, *spec.hidden_test_files):
        path = Path(relative_path)
        if path.is_absolute() or ".." in path.parts or "\\" in relative_path or path.as_posix() != relative_path:
            raise EvalBuildError(f"path must stay within its declared root: {relative_path}")

    for relative_path in spec.hidden_test_files:
        relative_hidden_path = Path(relative_path)
        if len(relative_hidden_path.parts) < 2 or relative_hidden_path.parts[0] != "hidden_tests":
            raise EvalBuildError(f"hidden test must be under hidden_tests/: {relative_path}")
        hidden_path = spec_dir / relative_hidden_path
        if not hidden_path.is_file():
            raise EvalBuildError(f"hidden test not found: {hidden_path}")

    forbidden_roots = {"tests", "evals", "solution"}
    for relative_path in spec.solution_paths:
        if Path(relative_path).parts[0] in forbidden_roots:
            raise EvalBuildError(f"solution path exposes eval-only material: {relative_path}")


def _load_contract() -> dict[str, Any]:
    with CONTRACT_PATH.open("rb") as contract_file:
        contract = tomllib.load(contract_file)
    if contract.get("contract_version") != 2:
        raise EvalBuildError("unsupported image contract version")
    if contract.get("network") != {
        "harbor_mode": "public",
        "docker_main_network_mode": "none",
    }:
        raise EvalBuildError("unsupported image network contract")
    return contract


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _toml_array(values: tuple[str, ...]) -> str:
    return "[" + ", ".join(_toml_string(value) for value in values) + "]"


def _task_toml(
    spec: EvalSpec,
    *,
    base_commit: str,
    solution_commit: str,
    image_ref: str,
    contract: dict[str, Any],
) -> str:
    return f'''schema_version = "{contract["harbor_schema_version"]}"

[task]
name = {_toml_string(spec.task_name)}
version = {_toml_string(spec.task_version)}
description = {_toml_string(spec.description)}
authors = [{{ name = {_toml_string(spec.author_name)}, email = {_toml_string(spec.author_email)} }}]
keywords = {_toml_array(spec.keywords)}

[metadata]
category = {_toml_string(spec.category)}
difficulty = {_toml_string(spec.difficulty)}
base_commit = {_toml_string(base_commit)}
solution_commit = {_toml_string(solution_commit)}
image_contract_version = {contract["contract_version"]}

[agent]
timeout_sec = {spec.agent_timeout_sec:.1f}
user = {_toml_string(contract["workspace"]["agent_user"])}

[verifier]
timeout_sec = {spec.verifier_timeout_sec:.1f}
user = "root"

[environment]
network_mode = {_toml_string(contract["network"]["harbor_mode"])}
docker_image = {_toml_string(image_ref)}
workdir = {_toml_string(contract["workspace"]["path"])}
cpus = {spec.cpus}
memory_mb = {spec.memory_mb}
storage_mb = {spec.storage_mb}
gpus = 0

[[steps]]
name = "maintain"
'''


def _write_bytes(path: Path, content: bytes, *, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    if executable:
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _copy_file(source: Path, destination: Path, *, executable: bool = False) -> None:
    _write_bytes(destination, source.read_bytes(), executable=executable)


def _file_manifest(task_dir: Path) -> dict[str, dict[str, Any]]:
    files: dict[str, dict[str, Any]] = {}
    for path in sorted(task_dir.rglob("*")):
        if not path.is_file() or path.name == "manifest.json":
            continue
        relative_path = path.relative_to(task_dir).as_posix()
        files[relative_path] = {
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "executable": bool(path.stat().st_mode & stat.S_IXUSR),
        }
    return files


def materialize_eval(
    slug: str,
    *,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    image_ref: str | None = None,
) -> Path:
    spec, spec_dir = load_spec(slug)
    _validate_spec_paths(spec, spec_dir)
    contract = _load_contract()

    base_commit = _resolve_commit(spec.base_ref)
    solution_commit = _resolve_commit(spec.solution_ref)
    ancestry_check = subprocess.run(
        ["git", "merge-base", "--is-ancestor", base_commit, solution_commit],
        cwd=REPO_ROOT,
        check=False,
    )
    if ancestry_check.returncode != 0:
        raise EvalBuildError("base_ref must be an ancestor of solution_ref")
    for solution_path in spec.solution_paths:
        path_diff = subprocess.run(
            ["git", "diff", "--quiet", base_commit, solution_commit, "--", solution_path],
            cwd=REPO_ROOT,
            check=False,
        )
        if path_diff.returncode == 0:
            raise EvalBuildError(f"solution path is unchanged across refs: {solution_path}")
        if path_diff.returncode != 1:
            raise EvalBuildError(f"could not compare solution path: {solution_path}")

    effective_image_ref = image_ref or str(contract["local_image"])
    instruction_path = spec_dir / "instruction.md"
    if not instruction_path.is_file():
        raise EvalBuildError(f"instruction not found: {instruction_path}")

    output_root = output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    temporary_dir = Path(tempfile.mkdtemp(prefix=f".{slug}.", dir=output_root))
    target_dir = output_root / slug

    try:
        step_dir = temporary_dir / "steps" / "maintain"
        (temporary_dir / "environment").mkdir(parents=True)
        _write_bytes(
            temporary_dir / "environment" / "docker-compose.yaml",
            DOCKER_COMPOSE.encode(),
        )
        _write_bytes(
            temporary_dir / "task.toml",
            _task_toml(
                spec,
                base_commit=base_commit,
                solution_commit=solution_commit,
                image_ref=effective_image_ref,
                contract=contract,
            ).encode(),
        )
        _copy_file(instruction_path, step_dir / "instruction.md")

        repository_archive = _run_git("archive", "--format=tar", base_commit, text=False)
        if not isinstance(repository_archive, bytes):  # pragma: no cover
            raise EvalBuildError("git archive returned text instead of bytes")
        _write_bytes(step_dir / "workdir" / "repository.tar", repository_archive)
        _copy_file(
            FRAMEWORK_ROOT / "bootstrap-repository.sh",
            step_dir / "workdir" / "setup.sh",
            executable=True,
        )

        hidden_root = step_dir / "tests" / "hidden_tests"
        for relative_path in spec.hidden_test_files:
            source = spec_dir / relative_path
            destination = hidden_root / Path(relative_path).relative_to("hidden_tests")
            _copy_file(source, destination)
        _copy_file(FRAMEWORK_ROOT / "verifier.sh", step_dir / "tests" / "test.sh", executable=True)

        gold_patch = _run_git(
            "diff",
            "--binary",
            base_commit,
            solution_commit,
            "--",
            *spec.solution_paths,
            text=False,
        )
        if not isinstance(gold_patch, bytes) or not gold_patch.strip():
            raise EvalBuildError("curated oracle patch is empty")
        _write_bytes(step_dir / "solution" / "gold.patch", gold_patch)
        _write_bytes(
            step_dir / "solution" / "solve.sh",
            b"#!/usr/bin/env bash\nset -euo pipefail\ngit apply /solution/gold.patch\n",
            executable=True,
        )

        files = _file_manifest(temporary_dir)
        manifest = {
            "manifest_version": 1,
            "slug": slug,
            "base_commit": base_commit,
            "solution_commit": solution_commit,
            "image_ref": effective_image_ref,
            "image_contract_version": contract["contract_version"],
            "files": files,
        }
        _write_bytes(
            temporary_dir / "manifest.json",
            (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode(),
        )

        if target_dir.exists():
            shutil.rmtree(target_dir)
        os.replace(temporary_dir, target_dir)
    except Exception:
        shutil.rmtree(temporary_dir, ignore_errors=True)
        raise

    return target_dir


def tree_digest(task_dir: Path) -> str:
    digest = hashlib.sha256()
    for relative_path, metadata in _file_manifest(task_dir).items():
        digest.update(relative_path.encode())
        digest.update(b"\0")
        digest.update(str(metadata["executable"]).encode())
        digest.update(b"\0")
        digest.update(str(metadata["sha256"]).encode())
        digest.update(b"\n")
    return digest.hexdigest()

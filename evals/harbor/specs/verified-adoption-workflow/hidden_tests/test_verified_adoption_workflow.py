import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


WORKSPACE = Path.cwd().resolve()
EXPECTED_DESCRIPTION = "A LibCST codemod and CLI for normalizing None-related Python type annotations."


@dataclass(frozen=True)
class CandidateTools:
    python: Path
    typewriter: Path
    pre_commit: Path
    hook_repository: Path
    environment: dict[str, str]


def _run(*command: str, cwd: Path, check: bool = True, env=None):
    return subprocess.run(
        command,
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
        env=env,
    )


def _init_repository(path: Path) -> None:
    path.mkdir(parents=True)
    _run("git", "init", "-q", "-b", "main", cwd=path)
    _run("git", "config", "user.name", "Typewriter Adoption Eval", cwd=path)
    _run("git", "config", "user.email", "adoption-eval@typewriter.invalid", cwd=path)


def _commit_all(path: Path, message: str) -> None:
    _run("git", "add", "-A", cwd=path)
    _run("git", "commit", "-q", "-m", message, cwd=path)


def _build_hook_repository(path: Path) -> None:
    _init_repository(path)
    for filename in ("LICENSE", "README.md", "pyproject.toml", ".pre-commit-hooks.yaml"):
        shutil.copy2(WORKSPACE / filename, path / filename)
    shutil.copytree(WORKSPACE / "typewriter", path / "typewriter")
    _commit_all(path, "candidate hook source")


def _offline_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["PIP_NO_INDEX"] = "1"
    environment["UV_OFFLINE"] = "1"
    return environment


@pytest.fixture(scope="session")
def candidate_tools(tmp_path_factory) -> CandidateTools:
    root = tmp_path_factory.mktemp("candidate-tools")
    environment = _offline_environment()
    venv = root / "venv"
    _run(sys.executable, "-m", "venv", str(venv), cwd=WORKSPACE, env=environment)

    python = venv / "bin" / "python"
    typewriter = venv / "bin" / "typewriter"
    pre_commit = venv / "bin" / "pre-commit"
    install = _run(
        str(python),
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        str(WORKSPACE),
        "pre-commit==4.6.2",
        cwd=WORKSPACE,
        check=False,
        env=environment,
    )
    assert install.returncode == 0, install.stdout + install.stderr

    metadata = _run(
        str(python),
        "-c",
        (
            "import importlib.metadata as m, json; "
            "d = m.metadata('py-typewriter-cli'); "
            "print(json.dumps({'version': m.version('py-typewriter-cli'), 'summary': d['Summary']}))"
        ),
        cwd=root,
        env=environment,
    )
    assert json.loads(metadata.stdout) == {
        "version": "1.2.0",
        "summary": EXPECTED_DESCRIPTION,
    }

    hook_repository = root / "hook-repository"
    _build_hook_repository(hook_repository)
    return CandidateTools(
        python=python,
        typewriter=typewriter,
        pre_commit=pre_commit,
        hook_repository=hook_repository,
        environment=environment,
    )


def test_candidate_install_and_real_hook_complete_the_clean_offline_adoption_path(tmp_path, candidate_tools):
    assert candidate_tools.environment["PIP_NO_INDEX"] == "1"
    assert candidate_tools.environment["UV_OFFLINE"] == "1"
    wheelhouse = Path(candidate_tools.environment["PIP_FIND_LINKS"])
    assert wheelhouse.is_dir()
    assert next(wheelhouse.glob("*.whl"), None) is not None
    assert sys.version_info[:2] == (3, 10)

    sample = tmp_path / "repo"
    pre_commit_home = tmp_path / "pre-commit-home"
    _init_repository(sample)
    original = b"value: int = None\n"
    (sample / "example.py").write_bytes(original)

    default_preview = _run(
        str(candidate_tools.typewriter),
        "run",
        "example.py",
        "--check",
        cwd=sample,
        check=False,
        env=candidate_tools.environment,
    )
    assert default_preview.returncode == 1
    assert "Optional[int]" in default_preview.stdout + default_preview.stderr
    assert (sample / "example.py").read_bytes() == original

    policy = sample / "pyproject.toml"
    policy.write_text(
        '[tool.typewriter]\ntarget-version = "3.10"\nrespect-gitignore = false\nignore = ["generated"]\n',
        encoding="utf-8",
    )
    generated = sample / "generated" / "ignored.py"
    generated.parent.mkdir()
    generated_original = b"generated: int = None\n"
    generated.write_bytes(generated_original)

    config_result = _run(
        str(candidate_tools.typewriter),
        "config",
        "--output-format",
        "json",
        cwd=sample,
        env=candidate_tools.environment,
    )
    assert json.loads(config_result.stdout) == {
        "type": "config",
        "config_file": str(policy.resolve()),
        "values": {
            "target_version": {"value": "3.10", "source": "config"},
            "respect_gitignore": {"value": False, "source": "config"},
            "ignore": [{"pattern": "generated", "source": "config"}],
        },
    }

    policy_preview = _run(
        str(candidate_tools.typewriter),
        "run",
        ".",
        "--check",
        cwd=sample,
        check=False,
        env=candidate_tools.environment,
    )
    assert policy_preview.returncode == 1
    assert "int | None" in policy_preview.stdout + policy_preview.stderr
    assert (sample / "example.py").read_bytes() == original
    assert generated.read_bytes() == generated_original

    _run(str(candidate_tools.typewriter), "run", ".", cwd=sample, env=candidate_tools.environment)
    assert (sample / "example.py").read_bytes() == b"value: int | None = None\n"
    assert generated.read_bytes() == generated_original

    (sample / ".pre-commit-config.yaml").write_text(
        "repos:\n"
        "  - repo: https://github.com/danphenderson/python-typewriter\n"
        "    rev: v1.2.0\n"
        "    hooks:\n"
        "      - id: typewriter\n",
        encoding="utf-8",
    )
    hook_only = sample / "hook_only.py"
    hook_only.write_bytes(b"hook_only: int = None\n")
    _commit_all(sample, "pre-hook adoption sample")

    hook_environment = candidate_tools.environment.copy()
    hook_environment["PRE_COMMIT_HOME"] = str(pre_commit_home)
    hook_command = (
        str(candidate_tools.pre_commit),
        "try-repo",
        str(candidate_tools.hook_repository),
        "typewriter",
        "--files",
        "hook_only.py",
    )
    first_hook = _run(*hook_command, cwd=sample, check=False, env=hook_environment)
    assert first_hook.returncode != 0
    assert "files were modified by this hook" in first_hook.stdout + first_hook.stderr
    assert hook_only.read_bytes() == b"hook_only: int | None = None\n"

    _run("git", "add", "hook_only.py", cwd=sample)
    clean_hook = _run(*hook_command, cwd=sample, check=False, env=hook_environment)
    assert clean_hook.returncode == 0, clean_hook.stdout + clean_hook.stderr
    assert "Passed" in clean_hook.stdout

    final_ci = _run(
        str(candidate_tools.typewriter),
        "run",
        ".",
        "--check",
        cwd=sample,
        check=False,
        env=candidate_tools.environment,
    )
    assert final_ci.returncode == 0, final_ci.stdout + final_ci.stderr
    assert "No files need changes" in final_ci.stdout


def test_version_description_policy_docs_and_unreleased_changelog_are_consistent():
    project = tomllib.loads((WORKSPACE / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["version"] == "1.2.0"
    assert project["project"]["description"] == EXPECTED_DESCRIPTION

    changelog = (WORKSPACE / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [1.2.0] - Unreleased" in changelog
    assert "does not indicate that a tag" in changelog
    assert "GitHub release, PyPI publication, or downstream adoption baseline exists" in changelog

    policy = '[tool.typewriter]\ntarget-version = "3.10"\nrespect-gitignore = true\n' 'ignore = ["generated", "src/vendor/*"]'
    readme = (WORKSPACE / "README.md").read_text(encoding="utf-8")
    adoption = (WORKSPACE / "docs" / "adoption.md").read_text(encoding="utf-8")
    usage = (WORKSPACE / "docs" / "usage.md").read_text(encoding="utf-8")
    assert policy in readme
    assert policy in adoption
    assert 'python -m pip install "py-typewriter-cli==1.2.0"' in readme
    assert 'python -m pip install "py-typewriter-cli==1.2.0"' in adoption
    for document in (readme, adoption, usage):
        assert "rev: v1.2.0" in document
        assert "only after" in document.lower()
    assert "prepared in source but is not yet tagged or published" in readme
    assert "prepared in source but unreleased" in adoption

    headings = re.findall(r"^## ([1-6])\. ", adoption, flags=re.MULTILINE)
    assert headings == ["1", "2", "3", "4", "5", "6"]


def test_release_runbook_keeps_six_independent_unpassed_gates():
    release = (WORKSPACE / "docs" / "release.md").read_text(encoding="utf-8")
    normalized_release = " ".join(release.split())
    gates = re.findall(r"^## Gate ([1-6]): (.+)$", release, flags=re.MULTILINE)
    assert gates == [
        ("1", "build and package verification"),
        ("2", "all Harbor maintenance controls"),
        ("3", "hosted CI"),
        ("4", "tag and GitHub release"),
        ("5", "PyPI publication"),
        ("6", "downstream adoption baseline"),
    ]
    assert "release is not complete" in normalized_release
    assert "Local results do not substitute for hosted checks" in normalized_release
    assert "A GitHub release alone is not PyPI evidence" in normalized_release
    assert "No tag, GitHub release, PyPI upload, or downstream mutation is authorized" in normalized_release


def test_adoption_ci_is_one_non_matrix_strict_docs_and_rehearsal_job():
    workflow_path = WORKSPACE / ".github" / "workflows" / "adoption-workflow.yml"
    workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    assert set(workflow["jobs"]) == {"clean-sample"}
    job = workflow["jobs"]["clean-sample"]
    assert "strategy" not in job
    run_commands = [step["run"] for step in job["steps"] if "run" in step]
    assert any('python -m pip install build ".[docs]"' in command for command in run_commands)
    assert any("python -m mkdocs build --strict --clean" in command for command in run_commands)
    assert any("tools/test_adoption_workflow.sh" in command for command in run_commands)
    assert os.access(WORKSPACE / "tools" / "test_adoption_workflow.sh", os.X_OK)

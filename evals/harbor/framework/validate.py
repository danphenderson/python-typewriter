from __future__ import annotations

import json
import posixpath
import stat
import tarfile
from pathlib import Path, PurePosixPath

try:
    import tomllib  # type: ignore[import-not-found]
except ModuleNotFoundError:  # pragma: no cover - Python 3.10
    import tomli as tomllib

from evals.harbor.framework.generate import (
    DOCKER_COMPOSE,
    EvalBuildError,
    _file_manifest,
)


def validate_task(task_dir: Path) -> None:
    task_dir = task_dir.resolve()
    manifest_path = task_dir / "manifest.json"
    task_config_path = task_dir / "task.toml"
    archive_path = task_dir / "steps" / "maintain" / "workdir" / "repository.tar"

    if not manifest_path.is_file():
        raise EvalBuildError(f"missing manifest: {manifest_path}")
    if not task_config_path.is_file():
        raise EvalBuildError(f"missing task config: {task_config_path}")

    manifest = json.loads(manifest_path.read_text())
    if manifest.get("manifest_version") != 1:
        raise EvalBuildError("unsupported task manifest version")
    actual_files = _file_manifest(task_dir)
    if manifest.get("files") != actual_files:
        raise EvalBuildError("task files do not match manifest hashes or modes")

    with task_config_path.open("rb") as task_config_file:
        task_config = tomllib.load(task_config_file)
    if task_config.get("schema_version") != "1.4":
        raise EvalBuildError("generated task must use Harbor schema 1.4")
    if task_config.get("environment", {}).get("network_mode") != "public":
        raise EvalBuildError("generated task must use the Docker-compatible Harbor network mode")
    if not task_config.get("environment", {}).get("docker_image"):
        raise EvalBuildError("generated task must reference a prebuilt image")
    if manifest.get("image_ref") != task_config["environment"]["docker_image"]:
        raise EvalBuildError("manifest and task image references differ")
    if (task_dir / "environment" / "Dockerfile").exists():
        raise EvalBuildError("generated tasks must not define task-specific images")
    compose_path = task_dir / "environment" / "docker-compose.yaml"
    if not compose_path.is_file() or compose_path.read_text() != DOCKER_COMPOSE:
        raise EvalBuildError("generated task must disable main-container networking through Docker Compose")

    expected_executables = (
        task_dir / "steps" / "maintain" / "workdir" / "setup.sh",
        task_dir / "steps" / "maintain" / "tests" / "test.sh",
        task_dir / "steps" / "maintain" / "solution" / "solve.sh",
    )
    for executable in expected_executables:
        if not executable.is_file() or not executable.stat().st_mode & stat.S_IXUSR:
            raise EvalBuildError(f"required script is not executable: {executable}")

    with tarfile.open(archive_path) as repository_archive:
        for member in repository_archive.getmembers():
            member_path = PurePosixPath(member.name)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise EvalBuildError(f"unsafe repository archive member: {member.name}")
            if ".git" in member_path.parts:
                raise EvalBuildError("repository snapshot must not contain Git object history")
            if member.issym() or member.islnk():
                link_base = member_path.parent if member.issym() else PurePosixPath()
                resolved_link = PurePosixPath(posixpath.normpath(str(link_base / member.linkname)))
                if resolved_link.is_absolute() or ".." in resolved_link.parts:
                    raise EvalBuildError(f"unsafe repository archive link: {member.name}")

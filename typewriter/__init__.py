from __future__ import annotations

import importlib.metadata as metadata
from pathlib import Path

import tomllib

_DISTRIBUTION_NAME = "py-typewriter-cli"
_PYPROJECT_PATH = Path(__file__).resolve().parent.parent / "pyproject.toml"


def _read_pyproject_version() -> str | None:
    try:
        with _PYPROJECT_PATH.open("rb") as pyproject_file:
            pyproject = tomllib.load(pyproject_file)
    except OSError:  # pragma: no cover
        return None

    project = pyproject.get("project")
    if not isinstance(project, dict):  # pragma: no cover
        return None

    version = project.get("version")
    if not isinstance(version, str):  # pragma: no cover
        return None
    return version


def _resolve_version() -> str:
    try:
        return metadata.version(_DISTRIBUTION_NAME)
    except metadata.PackageNotFoundError:  # pragma: no cover
        return _read_pyproject_version() or "0.0.0"


__version__ = _resolve_version()

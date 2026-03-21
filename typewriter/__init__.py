from __future__ import annotations

import importlib.metadata as importlib_metadata
from pathlib import Path
from typing import Any

_DISTRIBUTION_NAME = "py-typewriter-cli"
_PYPROJECT_PATH = Path(__file__).resolve().parent.parent / "pyproject.toml"


def _load_toml_parser() -> Any:
    try:
        import tomllib

        return tomllib
    except ModuleNotFoundError:  # pragma: no cover
        import tomli

        return tomli


def _read_pyproject_version() -> str | None:
    try:
        toml_parser = _load_toml_parser()
        with _PYPROJECT_PATH.open("rb") as pyproject_file:
            pyproject = toml_parser.load(pyproject_file)
    except OSError:  # pragma: no cover
        return None

    project = pyproject.get("project")
    if not isinstance(project, dict):  # pragma: no cover
        return None

    project_version = project.get("version")
    if not isinstance(project_version, str):  # pragma: no cover
        return None
    return project_version


def _resolve_version() -> str:
    try:
        return importlib_metadata.version(_DISTRIBUTION_NAME)
    except importlib_metadata.PackageNotFoundError:  # pragma: no cover
        return _read_pyproject_version() or "0.0.0"


__version__ = _resolve_version()

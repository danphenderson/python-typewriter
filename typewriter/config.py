from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Sequence, Tuple

try:
    import tomllib  # type: ignore[import-not-found]
except ModuleNotFoundError:  # pragma: no cover - Python 3.10
    import tomli as tomllib


_CONFIG_KEYS = {"ignore", "respect-gitignore", "target-version"}


class ConfigSource(str, Enum):
    """Origin of an effective Typewriter policy value."""

    DEFAULT = "default"
    CONFIG = "config"
    CLI = "cli"
    API = "api"


@dataclass(frozen=True)
class ConfigProvenance:
    """Internal source metadata retained for effective-config reporting."""

    config_path: Optional[Path] = None
    target_version: ConfigSource = ConfigSource.DEFAULT
    respect_gitignore: ConfigSource = ConfigSource.DEFAULT
    ignore: Tuple[ConfigSource, ...] = ()


@dataclass(frozen=True)
class TypewriterConfig:
    """Immutable effective project policy for a Typewriter run."""

    target_version: Optional[str] = None
    respect_gitignore: bool = False
    ignore: Tuple[str, ...] = ()
    ignore_roots: Tuple[Optional[Path], ...] = field(default=(), repr=False)
    provenance: ConfigProvenance = field(default_factory=ConfigProvenance, repr=False)

    def __post_init__(self) -> None:
        ignore = tuple(self.ignore)
        ignore_roots = tuple(self.ignore_roots) if self.ignore_roots else (None,) * len(ignore)
        provenance_ignore = tuple(self.provenance.ignore)
        if not provenance_ignore and ignore:
            provenance_ignore = (ConfigSource.DEFAULT,) * len(ignore)

        if not isinstance(self.respect_gitignore, bool):
            raise TypeError("respect-gitignore must be a boolean")
        if self.target_version is not None:
            if not isinstance(self.target_version, str):
                raise TypeError("target-version must be a string")
            target_version_uses_pep604(self.target_version)
        if not all(isinstance(pattern, str) and pattern for pattern in ignore):
            raise TypeError("ignore must be an array of non-empty strings")
        if len(ignore_roots) != len(ignore):
            raise ValueError("ignore roots must correspond one-to-one with ignore patterns")
        if len(provenance_ignore) != len(ignore):
            raise ValueError("ignore provenance must correspond one-to-one with ignore patterns")

        object.__setattr__(self, "ignore", ignore)
        object.__setattr__(self, "ignore_roots", ignore_roots)
        if provenance_ignore != self.provenance.ignore:
            object.__setattr__(
                self,
                "provenance",
                ConfigProvenance(
                    config_path=self.provenance.config_path,
                    target_version=self.provenance.target_version,
                    respect_gitignore=self.provenance.respect_gitignore,
                    ignore=provenance_ignore,
                ),
            )

    @property
    def config_root(self) -> Optional[Path]:
        config_path = self.provenance.config_path
        return config_path.parent if config_path is not None else None


def target_version_uses_pep604(value: Optional[str]) -> bool:
    """Return whether a target version selects PEP 604 union syntax."""
    if value is None:
        return False
    try:
        parts = value.replace("py", "").split(".")
        if len(parts) == 1 and len(parts[0]) >= 3:
            major = int(parts[0][0])
            minor = int(parts[0][1:])
        else:
            major, minor = int(parts[0]), int(parts[1])
        return (major, minor) >= (3, 10)
    except (ValueError, IndexError) as exc:
        raise ValueError(f"Invalid target version: {value!r}. Use e.g. '3.10' or '3.9'.") from exc


def _config_path(path: Path, *, cwd: Path) -> Path:
    candidate = path.expanduser()
    if not candidate.is_absolute():
        candidate = cwd / candidate
    return candidate.resolve()


def _find_nearest_pyproject(cwd: Path) -> Optional[Path]:
    for directory in (cwd, *cwd.parents):
        candidate = directory / "pyproject.toml"
        if candidate.is_file():
            return candidate.resolve()
    return None


def _read_config_table(config_path: Path) -> dict[str, Any]:
    if not config_path.is_file() or not os.access(config_path, os.R_OK):
        raise ValueError(f"Config path is not a readable file: {config_path}")

    try:
        with config_path.open("rb") as config_file:
            document = tomllib.load(config_file)
    except OSError as exc:
        raise ValueError(f"Could not read config file {config_path}: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"Could not parse config file {config_path}: {exc}") from exc

    tool = document.get("tool")
    if tool is None:
        return {}
    if not isinstance(tool, dict):
        raise ValueError(f"tool must be a table in config file {config_path}")
    table = tool.get("typewriter")
    if table is None:
        return {}
    if not isinstance(table, dict):
        raise ValueError(f"tool.typewriter must be a table in config file {config_path}")
    return table


def load_typewriter_config(
    *,
    config_path: Optional[Path] = None,
    cwd: Optional[Path] = None,
) -> TypewriterConfig:
    """Load ``[tool.typewriter]`` from an explicit file or nearest pyproject."""
    invocation_cwd = (cwd or Path.cwd()).resolve()
    selected_path = _config_path(config_path, cwd=invocation_cwd) if config_path is not None else _find_nearest_pyproject(invocation_cwd)
    if selected_path is None:
        return TypewriterConfig()

    table = _read_config_table(selected_path)
    unknown_keys = sorted(set(table) - _CONFIG_KEYS)
    if unknown_keys:
        rendered_keys = ", ".join(unknown_keys)
        raise ValueError(f"Unknown tool.typewriter config key(s) in {selected_path}: {rendered_keys}")

    target_version = table.get("target-version")
    if target_version is not None and not isinstance(target_version, str):
        raise ValueError(f"target-version must be a string in {selected_path}")
    if target_version is not None:
        target_version_uses_pep604(target_version)

    respect_gitignore = table.get("respect-gitignore", False)
    if not isinstance(respect_gitignore, bool):
        raise ValueError(f"respect-gitignore must be a boolean in {selected_path}")

    raw_ignore = table.get("ignore", [])
    if not isinstance(raw_ignore, list) or not all(isinstance(pattern, str) and pattern for pattern in raw_ignore):
        raise ValueError(f"ignore must be an array of non-empty strings in {selected_path}")
    ignore = tuple(dict.fromkeys(raw_ignore))

    return TypewriterConfig(
        target_version=target_version,
        respect_gitignore=respect_gitignore,
        ignore=ignore,
        ignore_roots=(selected_path.parent,) * len(ignore),
        provenance=ConfigProvenance(
            config_path=selected_path,
            target_version=ConfigSource.CONFIG if "target-version" in table else ConfigSource.DEFAULT,
            respect_gitignore=ConfigSource.CONFIG if "respect-gitignore" in table else ConfigSource.DEFAULT,
            ignore=(ConfigSource.CONFIG,) * len(ignore),
        ),
    )


def apply_cli_overrides(
    config: TypewriterConfig,
    *,
    target_version: Optional[str] = None,
    respect_gitignore: Optional[bool] = None,
    ignore: Optional[Sequence[str]] = None,
) -> TypewriterConfig:
    """Apply CLI values using stable, field-specific precedence rules."""
    if target_version is not None:
        target_version_uses_pep604(target_version)
    if respect_gitignore is not None and not isinstance(respect_gitignore, bool):
        raise TypeError("respect-gitignore CLI override must be a boolean")

    effective_ignore = list(config.ignore)
    effective_roots = list(config.ignore_roots)
    effective_sources = list(config.provenance.ignore)
    seen = set(effective_ignore)
    for pattern in ignore or ():
        if not isinstance(pattern, str) or not pattern:
            raise ValueError("--ignore values must be non-empty strings")
        if pattern in seen:
            continue
        seen.add(pattern)
        effective_ignore.append(pattern)
        effective_roots.append(None)
        effective_sources.append(ConfigSource.CLI)

    return TypewriterConfig(
        target_version=target_version if target_version is not None else config.target_version,
        respect_gitignore=respect_gitignore if respect_gitignore is not None else config.respect_gitignore,
        ignore=tuple(effective_ignore),
        ignore_roots=tuple(effective_roots),
        provenance=ConfigProvenance(
            config_path=config.provenance.config_path,
            target_version=ConfigSource.CLI if target_version is not None else config.provenance.target_version,
            respect_gitignore=(ConfigSource.CLI if respect_gitignore is not None else config.provenance.respect_gitignore),
            ignore=tuple(effective_sources),
        ),
    )

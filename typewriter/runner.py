from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence

from typewriter.codemod import (
    CodemodContext,
    ProcessResult,
    ProcessStringResult,
    process_code,
    process_file,
    process_files_in_directory,
)


def _supports_pep604(value: Optional[str]) -> bool:
    """Return *True* when *value* indicates Python 3.10+ (PEP 604 unions)."""
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


def _resolve_use_pep604(*, target_version: Optional[str], use_pep604: Optional[bool]) -> bool:
    derived_use_pep604 = None if target_version is None else _supports_pep604(target_version)
    if use_pep604 is None:
        return derived_use_pep604 if derived_use_pep604 is not None else False
    if derived_use_pep604 is not None and derived_use_pep604 != use_pep604:
        raise ValueError("target_version and use_pep604 must agree when both are provided.")
    return use_pep604


class TypewriterRunner:
    """High-level API for embedding Typewriter in other tools."""

    def __init__(
        self,
        *,
        target_version: Optional[str] = None,
        use_pep604: Optional[bool] = None,
        ignore: Optional[Sequence[str]] = None,
        respect_gitignore: bool = False,
    ) -> None:
        self.target_version = target_version
        self.use_pep604 = _resolve_use_pep604(target_version=target_version, use_pep604=use_pep604)
        self.ignore = list(ignore or [])
        self.respect_gitignore = respect_gitignore

    def process_code(self, code: str) -> ProcessStringResult:
        return process_code(code, context=self._context())

    def process_file(self, path: Path, *, write: bool = True, include_diff: bool = False) -> ProcessResult:
        return process_file(path, write=write, include_diff=include_diff, context=self._context())

    def process_directory(self, path: Path, *, write: bool = True, include_diff: bool = False) -> ProcessResult:
        return process_files_in_directory(
            path,
            write=write,
            include_diff=include_diff,
            context=self._context(),
            extra_ignore_patterns=self.ignore or None,
            respect_gitignore=self.respect_gitignore,
        )

    def _context(self) -> CodemodContext:
        return CodemodContext(use_pep604=self.use_pep604)

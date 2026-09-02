from __future__ import annotations

import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

from typewriter.codemod import (
    CodemodContext,
    ProcessResult,
    ProcessStringResult,
    _is_gitignored,
    _iter_python_files,
    _load_gitignore_spec,
    _matches_any_pattern,
    _unified_diff_text,
    process_code,
    process_file,
)
from typewriter.config import (
    ConfigProvenance,
    ConfigSource,
    TypewriterConfig,
    target_version_uses_pep604,
)


def _supports_pep604(value: Optional[str]) -> bool:
    """Return *True* when *value* indicates Python 3.10+ (PEP 604 unions)."""
    return target_version_uses_pep604(value)


def _resolve_use_pep604(*, target_version: Optional[str], use_pep604: Optional[bool]) -> bool:
    derived_use_pep604 = None if target_version is None else _supports_pep604(target_version)
    if use_pep604 is None:
        return derived_use_pep604 if derived_use_pep604 is not None else False
    if derived_use_pep604 is not None and derived_use_pep604 != use_pep604:
        raise ValueError("target_version and use_pep604 must agree when both are provided.")
    return use_pep604


@dataclass(frozen=True)
class _ValidatedInput:
    path: Path
    resolved_path: Path

    @property
    def is_directory(self) -> bool:
        return self.resolved_path.is_dir()


@dataclass(frozen=True)
class _PreparedFile:
    path: Path
    resolved_path: Path
    original_bytes: bytes
    transformed_bytes: bytes
    mode: int


def _write_temporary_file(destination: Path, content: bytes, mode: int) -> Path:
    """Create a durable same-directory temporary file for an atomic replace."""
    descriptor, temporary_name = tempfile.mkstemp(
        dir=str(destination.parent),
        prefix=f".{destination.name}.typewriter-",
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as temporary_file:
            temporary_file.write(content)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.chmod(temporary_path, mode)
    except Exception:
        try:
            os.close(descriptor)
        except OSError:
            pass
        temporary_path.unlink(missing_ok=True)
        raise
    return temporary_path


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
        self._ignore_roots: Tuple[Optional[Path], ...] = (None,) * len(self.ignore)
        self.respect_gitignore = respect_gitignore
        self.config = TypewriterConfig(
            target_version=target_version,
            respect_gitignore=respect_gitignore,
            ignore=tuple(self.ignore),
            ignore_roots=self._ignore_roots,
            provenance=ConfigProvenance(
                target_version=ConfigSource.API if target_version is not None else ConfigSource.DEFAULT,
                respect_gitignore=ConfigSource.API,
                ignore=(ConfigSource.API,) * len(self.ignore),
            ),
        )

    @classmethod
    def from_config(cls, config: TypewriterConfig) -> TypewriterRunner:
        """Construct a runner from an immutable effective project policy."""
        runner = cls(
            target_version=config.target_version,
            ignore=(),
            respect_gitignore=config.respect_gitignore,
        )
        runner.ignore = list(config.ignore)
        runner._ignore_roots = config.ignore_roots
        runner.config = config
        return runner

    def process_code(self, code: str) -> ProcessStringResult:
        return process_code(code, context=self._context())

    def process_file(self, path: Path, *, write: bool = True, include_diff: bool = False) -> ProcessResult:
        # Preserve the lower-level helper's established no-op result for a
        # non-Python path. ``process_paths`` intentionally rejects that input.
        if path.suffix != ".py":
            return process_file(path, write=write, include_diff=include_diff, context=self._context())
        return self.process_paths([path], write=write, include_diff=include_diff)

    def process_directory(self, path: Path, *, write: bool = True, include_diff: bool = False) -> ProcessResult:
        return self.process_paths([path], write=write, include_diff=include_diff)

    def process_paths(
        self,
        paths: Sequence[Path],
        *,
        write: bool = True,
        include_diff: bool = False,
    ) -> ProcessResult:
        """Transform an ordered collection of files and directories atomically.

        Every explicit input and discovered source is validated, read, parsed,
        and transformed before write mode replaces any file. Overlapping inputs
        are deduplicated by resolved path, with the first eligible occurrence
        determining result order.
        """
        validated_inputs = self._validate_inputs(paths)
        discovered_files = self._discover_files(validated_inputs)

        prepared_files: List[_PreparedFile] = []
        changed_files: List[Path] = []
        diffs: Dict[Path, str] = {}
        for path, resolved_path in discovered_files:
            original_bytes = resolved_path.read_bytes()
            try:
                original_code = original_bytes.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError(f"Python source is not valid UTF-8: {path}") from exc

            # CodemodContext contains mutable scratch state. A fresh instance per
            # source prevents one file's rewrite decisions from leaking into the
            # next file.
            string_result = process_code(original_code, context=self._context())
            if not string_result.changed:
                continue

            transformed_bytes = string_result.transformed_code.encode("utf-8")
            changed_files.append(path)
            if include_diff:
                diffs[path] = _unified_diff_text(
                    original_code,
                    string_result.transformed_code,
                    fromfile=str(path),
                    tofile=str(path),
                )
            prepared_files.append(
                _PreparedFile(
                    path=path,
                    resolved_path=resolved_path,
                    original_bytes=original_bytes,
                    transformed_bytes=transformed_bytes,
                    mode=stat.S_IMODE(resolved_path.stat().st_mode),
                )
            )

        if write and prepared_files:
            self._replace_files(prepared_files)

        return ProcessResult(
            processed_files=len(discovered_files),
            changed_files=changed_files,
            diffs=diffs,
        )

    def _validate_inputs(self, paths: Sequence[Path]) -> List[_ValidatedInput]:
        if not paths:
            raise ValueError("At least one path must be provided.")

        validated_inputs: List[_ValidatedInput] = []
        for provided_path in paths:
            path = Path(provided_path)
            if not path.exists():
                raise ValueError(f"Path does not exist: {path}")

            resolved_path = path.resolve()
            if not resolved_path.is_file() and not resolved_path.is_dir():
                raise ValueError(f"Path is not a regular file or directory: {path}")
            if resolved_path.is_file() and resolved_path.suffix != ".py":
                raise ValueError(f"Only '.py' files are supported. Invalid path: {path}")

            required_access = os.R_OK | (os.X_OK if resolved_path.is_dir() else 0)
            if not os.access(resolved_path, required_access):
                raise ValueError(f"Path is not readable: {path}")
            validated_inputs.append(_ValidatedInput(path=path, resolved_path=resolved_path))
        return validated_inputs

    def _discover_files(self, inputs: Sequence[_ValidatedInput]) -> List[Tuple[Path, Path]]:
        discovered_files: List[Tuple[Path, Path]] = []
        seen: Set[Path] = set()
        for validated_input in inputs:
            if validated_input.is_directory:
                candidates = _iter_python_files(
                    validated_input.path,
                    extra_ignore_patterns=self._scan_ignore_patterns or None,
                    respect_gitignore=self.respect_gitignore,
                    path_is_ignored=self._rooted_ignore_matches,
                )
            elif self._explicit_file_is_ignored(validated_input.resolved_path):
                candidates = []
            else:
                candidates = [validated_input.path]

            for candidate in candidates:
                if self._rooted_ignore_matches(candidate):
                    continue
                resolved_candidate = candidate.resolve()
                if resolved_candidate in seen:
                    continue
                seen.add(resolved_candidate)
                discovered_files.append((candidate, resolved_candidate))
        return discovered_files

    def _explicit_file_is_ignored(self, path: Path) -> bool:
        scan_root = path.parent
        if self._scan_ignore_patterns:
            relative_path = path.relative_to(scan_root).as_posix()
            if _matches_any_pattern(path.name, self._scan_ignore_patterns) or _matches_any_pattern(
                relative_path, self._scan_ignore_patterns
            ):
                return True
        if self._rooted_ignore_matches(path):
            return True

        gitignore = _load_gitignore_spec(scan_root) if self.respect_gitignore else None
        return _is_gitignored(
            path,
            directory_path=scan_root,
            gitignore=gitignore,
            is_directory=False,
        )

    @property
    def _scan_ignore_patterns(self) -> List[str]:
        return [pattern for pattern, root in zip(self.ignore, self._ignore_roots) if root is None]

    def _rooted_ignore_matches(self, path: Path) -> bool:
        resolved_path = path.resolve()
        for pattern, root in zip(self.ignore, self._ignore_roots):
            if root is None:
                continue
            resolved_root = root.resolve()
            if not resolved_path.is_relative_to(resolved_root):
                continue
            relative_parts = resolved_path.relative_to(resolved_root).parts
            for length in range(1, len(relative_parts) + 1):
                relative_candidate = Path(*relative_parts[:length]).as_posix()
                if _matches_any_pattern(relative_parts[length - 1], [pattern]) or _matches_any_pattern(relative_candidate, [pattern]):
                    return True
        return False

    def _replace_files(self, prepared_files: Sequence[_PreparedFile]) -> None:
        staged: List[Tuple[_PreparedFile, Path, Path]] = []
        replaced: List[Tuple[_PreparedFile, Path]] = []
        preserved_backups: Set[Path] = set()
        try:
            # Stage every transformed file and rollback copy before changing any
            # destination. Both live beside the destination so os.replace is
            # atomic on the target filesystem.
            for prepared_file in prepared_files:
                if prepared_file.resolved_path.read_bytes() != prepared_file.original_bytes:
                    raise RuntimeError(f"File changed while Typewriter was running: {prepared_file.path}")
                transformed_path = _write_temporary_file(
                    prepared_file.resolved_path,
                    prepared_file.transformed_bytes,
                    prepared_file.mode,
                )
                try:
                    backup_path = _write_temporary_file(
                        prepared_file.resolved_path,
                        prepared_file.original_bytes,
                        prepared_file.mode,
                    )
                except Exception:
                    transformed_path.unlink(missing_ok=True)
                    raise
                staged.append((prepared_file, transformed_path, backup_path))

            for prepared_file, transformed_path, backup_path in staged:
                if prepared_file.resolved_path.read_bytes() != prepared_file.original_bytes:
                    raise RuntimeError(f"File changed while Typewriter was running: {prepared_file.path}")
                os.replace(transformed_path, prepared_file.resolved_path)
                replaced.append((prepared_file, backup_path))
        except Exception as write_error:
            rollback_errors: List[str] = []
            for prepared_file, backup_path in reversed(replaced):
                try:
                    os.replace(backup_path, prepared_file.resolved_path)
                except Exception as rollback_error:
                    preserved_backups.add(backup_path)
                    rollback_errors.append(f"{prepared_file.path}: {rollback_error}")
            if rollback_errors:
                details = "; ".join(rollback_errors)
                raise RuntimeError(f"Atomic write failed ({write_error}); rollback also failed ({details}).") from write_error
            raise RuntimeError(f"Atomic write failed; all replaced files were restored: {write_error}") from write_error
        finally:
            for _, transformed_path, backup_path in staged:
                transformed_path.unlink(missing_ok=True)
                if backup_path not in preserved_backups:
                    backup_path.unlink(missing_ok=True)

    def _context(self) -> CodemodContext:
        return CodemodContext(use_pep604=self.use_pep604)

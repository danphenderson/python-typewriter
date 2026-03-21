import fnmatch
import os
import warnings
from dataclasses import dataclass, field
from difflib import unified_diff
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple, Union

from libcst import (
    AnnAssign,
    Annotation,
    Attribute,
    BaseExpression,
    BinaryOperation,
    BitOr,
    CSTNode,
    CSTTransformer,
    CSTVisitor,
    ImportFrom,
    ImportStar,
    Index,
    MaybeSentinel,
    Name,
    Param,
    RemovalSentinel,
    RemoveFromParent,
    Subscript,
    SubscriptElement,
    ensure_type,
    parse_module,
)
from libcst.codemod import CodemodContext as _CodemodContext
from libcst.codemod import ContextAwareTransformer as _Codemod
from libcst.codemod.visitors import AddImportsVisitor
from libcst.matchers import Name as mName
from libcst.matchers import matches
from pathspec import GitIgnoreSpec


class CodemodContext(_CodemodContext):
    """Shared state for codemod runs.

    This extends LibCST's `CodemodContext` with a few flags and collections used
    by Typewriter's transformers.
    """

    def __init__(self, *, use_pep604: bool = False):
        super().__init__()
        self.code_modifications: List = []
        self.made_changes: bool = False
        self.rewrote_union_annotation: bool = False
        self.use_pep604: bool = use_pep604


class Codemod(_Codemod):
    """Base class for Typewriter codemods.

    Provides small conveniences over LibCST's `ContextAwareTransformer`, such as
    tracking whether a transformation made changes.
    """

    def __init__(self, context: Optional[CodemodContext] = None) -> None:
        context = context or CodemodContext()
        super().__init__(context)

    @property
    def code_modifications(self) -> List:
        return getattr(self.context, "code_modifications", [])

    @property
    def made_changes(self) -> bool:
        return getattr(self.context, "made_changes", False)

    def report_changes(self, original_node: CSTNode, updated_node: CSTNode, *, print_changes: bool = False) -> None:
        if original_node.deep_equals(updated_node):
            return
        original_code = getattr(original_node, "code", "")
        updated_code = getattr(updated_node, "code", "")
        code_diff = unified_diff(original_code.splitlines(), updated_code.splitlines(), lineterm="")
        self.code_modifications.append(code_diff)


class EnforceOptionalNoneTypes(Codemod):
    """Rewrite optional-style annotations into a normalized form.

    Default mode (Python 3.9-compatible) only rewrites ``Union[..., None]`` forms:

    - `Union[T, None]` -> `Optional[T]`
    - `Union[T1, T2, None]` -> `Optional[Union[T1, T2]]`

    PEP 604 mode (Python 3.10+) normalizes both ``Optional[...]`` and ``Union[...]``:

    - `Union[T, None]` -> `T | None`
    - `Optional[T]` -> `T | None`
    - `Union[T1, T2]` -> `T1 | T2`
    - `Union[T1, T2, None]` -> `T1 | T2 | None`
    """

    def leave_Subscript(self, original_node: Subscript, updated_node: Subscript) -> BaseExpression:
        if getattr(self.context, "use_pep604", False):
            rewritten_node = self._rewrite_pep604_annotation(updated_node)
            if rewritten_node is not None:
                setattr(self.context, "made_changes", True)
                if self._is_union_reference(updated_node.value):
                    setattr(self.context, "rewrote_union_annotation", True)
                return rewritten_node

        if not self._is_union_reference(updated_node.value):
            return updated_node

        remaining_union_elements = [element for element in updated_node.slice if not self._is_none_union_element(element)]
        if len(remaining_union_elements) == len(updated_node.slice):
            return updated_node
        if not remaining_union_elements:
            return updated_node
        remaining_union_elements = self._normalize_union_elements(remaining_union_elements)

        setattr(self.context, "made_changes", True)
        setattr(self.context, "rewrote_union_annotation", True)

        optional_reference = self._optional_reference_from_union_reference(updated_node.value)
        if len(remaining_union_elements) == 1:
            optional_inner_value = ensure_type(remaining_union_elements[0].slice, Index).value
        else:
            optional_inner_value = Subscript(
                value=updated_node.value,
                slice=list(remaining_union_elements),
            )

        return Subscript(
            value=optional_reference,
            slice=[SubscriptElement(slice=Index(value=optional_inner_value))],
        )

    def _rewrite_pep604_annotation(self, updated_node: Subscript) -> Optional[BaseExpression]:
        if self._is_union_reference(updated_node.value):
            inner_values = [ensure_type(el.slice, Index).value for el in self._normalize_union_elements(updated_node.slice)]
            return self._build_pep604_union(inner_values)

        if self._is_optional_reference(updated_node.value):
            if len(updated_node.slice) != 1:
                return None
            optional_inner_value = ensure_type(updated_node.slice[0].slice, Index).value
            return self._build_pep604_union([optional_inner_value, Name("None")])

        return None

    def _build_pep604_union(self, values: Sequence[BaseExpression]) -> BaseExpression:
        """Build a PEP 604 union expression from the provided values."""
        flattened_values = self._flatten_pep604_values(values)
        result: BaseExpression = flattened_values[0]
        for value in flattened_values[1:]:
            result = BinaryOperation(left=result, operator=BitOr(), right=value)
        return result

    def _flatten_pep604_values(self, values: Sequence[BaseExpression]) -> List[BaseExpression]:
        flattened_values: List[BaseExpression] = []
        saw_none = False

        def visit(value: BaseExpression) -> None:
            nonlocal saw_none
            if isinstance(value, BinaryOperation) and isinstance(value.operator, BitOr):
                visit(value.left)
                visit(value.right)
                return
            if isinstance(value, Name) and value.value == "None":
                # Avoid emitting ``... | None | None`` when an Optional wraps an
                # annotation that already contains ``None``.
                if saw_none:
                    return
                saw_none = True
            flattened_values.append(value)

        for value in values:
            visit(value)

        return flattened_values

    def _is_union_reference(self, node: BaseExpression) -> bool:
        if isinstance(node, Name):
            return node.value == "Union"
        if isinstance(node, Attribute):
            return node.attr.value == "Union"
        return False

    def _is_optional_reference(self, node: BaseExpression) -> bool:
        if isinstance(node, Name):
            return node.value == "Optional"
        if isinstance(node, Attribute):
            return node.attr.value == "Optional"
        return False

    def _is_none_union_element(self, union_element: SubscriptElement) -> bool:
        element_index = ensure_type(union_element.slice, Index)
        return isinstance(element_index.value, Name) and element_index.value.value == "None"

    def _optional_reference_from_union_reference(self, union_reference: BaseExpression) -> BaseExpression:
        if isinstance(union_reference, Attribute):
            return union_reference.with_changes(attr=Name("Optional"))

        AddImportsVisitor.add_needed_import(self.context, "typing", "Optional")
        return Name("Optional")

    def _normalize_union_elements(self, union_elements: Sequence[SubscriptElement]) -> List[SubscriptElement]:
        normalized_elements = list(union_elements)
        normalized_elements[-1] = normalized_elements[-1].with_changes(comma=MaybeSentinel.DEFAULT)
        return normalized_elements


class InferOptionalNoneTypes(Codemod):
    """Infer `Optional[...]` (or PEP 604 union) when an annotated value defaults to `None`.

    - Annotated assignments like `x: T = None` become `x: Optional[T] = None`.
    - Parameters like `def f(x: T = None)` become `def f(x: Optional[T] = None)`.

    When PEP 604 mode is enabled, `T | None` is emitted instead of `Optional[T]`.

    If the annotation is already `Optional[...]`, `Any`, or a PEP 604 None union, it
    is left unchanged.
    """

    def leave_AnnAssign(self, original_node: AnnAssign, updated_node: AnnAssign) -> AnnAssign:
        if matches(getattr(updated_node, "value"), mName("None")):
            if not self._is_optional_annotation(updated_node.annotation):
                new_annotation = self._wrap_with_optional(updated_node.annotation)
                new_node = updated_node.with_changes(annotation=new_annotation)
                setattr(self.context, "made_changes", True)
                return new_node
        return updated_node

    def leave_Param(self, original_node: Param, updated_node: Param) -> Param:
        if updated_node.default is not None and matches(updated_node.default, mName("None")):
            if updated_node.annotation is not None and not self._is_optional_annotation(updated_node.annotation):
                new_annotation = self._wrap_with_optional(updated_node.annotation)
                new_node = updated_node.with_changes(annotation=new_annotation)
                setattr(self.context, "made_changes", True)
                return new_node
        return updated_node

    def _is_optional_annotation(self, annotation: Annotation) -> bool:
        if self._is_any_annotation(annotation.annotation):
            return True
        if isinstance(annotation.annotation, Subscript):
            return self._is_optional_reference(annotation.annotation.value)
        if _is_pep604_none_union(annotation.annotation):
            return True
        return False

    def _is_any_annotation(self, annotation: BaseExpression) -> bool:
        if isinstance(annotation, Name):
            return annotation.value == "Any"
        if isinstance(annotation, Attribute):
            return annotation.attr.value == "Any"
        return False

    def _is_optional_reference(self, annotation_reference: BaseExpression) -> bool:
        if isinstance(annotation_reference, Name):
            return annotation_reference.value == "Optional"
        if isinstance(annotation_reference, Attribute):
            return annotation_reference.attr.value == "Optional"
        return False

    def _optional_reference_for_annotation(self, annotation_value: BaseExpression) -> BaseExpression:
        if isinstance(annotation_value, Attribute):
            return annotation_value.with_changes(attr=Name("Optional"))
        if isinstance(annotation_value, Subscript) and isinstance(annotation_value.value, Attribute):
            return annotation_value.value.with_changes(attr=Name("Optional"))

        AddImportsVisitor.add_needed_import(self.context, "typing", "Optional")
        return Name("Optional")

    def _wrap_with_optional(self, annotation: Annotation) -> Annotation:
        if getattr(self.context, "use_pep604", False):
            return Annotation(
                annotation=BinaryOperation(
                    left=annotation.annotation,
                    operator=BitOr(),
                    right=Name("None"),
                )
            )

        optional_reference = self._optional_reference_for_annotation(annotation.annotation)
        optional_annotation = Annotation(
            annotation=Subscript(
                value=optional_reference,
                slice=[SubscriptElement(slice=Index(value=annotation.annotation))],
            )
        )
        return optional_annotation


def _is_pep604_none_union(node: BaseExpression) -> bool:
    """Return True if *node* is a PEP 604 union that contains ``None``.

    Handles both ``T | None`` and nested chains such as ``T1 | T2 | None``.
    """
    if not isinstance(node, BinaryOperation) or not isinstance(node.operator, BitOr):
        return False
    if isinstance(node.right, Name) and node.right.value == "None":
        return True
    if isinstance(node.left, Name) and node.left.value == "None":
        return True
    return _is_pep604_none_union(node.left) or _is_pep604_none_union(node.right)


SKIP_DIRECTORY_NAMES: Set[str] = {
    ".eggs",
    ".git",
    ".hg",
    ".mypy_cache",
    ".nox",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "site-packages",
    "venv",
}


def _matches_any_pattern(path: str, patterns: Sequence[str]) -> bool:
    """Return True if *path* matches any of the given glob *patterns*."""
    return any(fnmatch.fnmatch(path, pat) for pat in patterns)


def _load_gitignore_spec(directory_path: Path) -> Optional[Tuple[Path, GitIgnoreSpec]]:
    for candidate in (directory_path, *directory_path.parents):
        gitignore_path = candidate / ".gitignore"
        if gitignore_path.is_file():
            lines = gitignore_path.read_text(encoding="utf-8").splitlines()
            return candidate, GitIgnoreSpec.from_lines(lines)
    return None


def _is_gitignored(
    path: Path,
    *,
    directory_path: Path,
    gitignore: Optional[Tuple[Path, GitIgnoreSpec]],
    is_directory: bool,
) -> bool:
    if gitignore is None:
        return False

    gitignore_root, gitignore_spec = gitignore
    if not path.is_relative_to(gitignore_root):
        return False

    relative_path = path.relative_to(gitignore_root).as_posix()
    # Git ignore patterns treat the scanned root as ``.`` when the path being
    # checked is exactly the directory we started from.
    if path == directory_path:
        relative_path = "."
    if is_directory and relative_path != ".":
        relative_path = f"{relative_path}/"
    return gitignore_spec.match_file(relative_path)


def _iter_python_files(
    directory_path: Path,
    extra_ignore_patterns: Optional[Sequence[str]] = None,
    *,
    respect_gitignore: bool = False,
) -> Sequence[Path]:
    """Walk *directory_path* and yield all ``*.py`` files.

    Directories in :data:`SKIP_DIRECTORY_NAMES` are always skipped.  When
    *extra_ignore_patterns* is provided, each entry is treated as a glob pattern
    (via :func:`fnmatch.fnmatch`) matched against both the bare directory/file
    name **and** the path relative to *directory_path*.  For example,
    ``"generated_*"`` skips any directory or file whose name starts with
    ``generated_``, and ``"src/vendor/*"`` skips everything under
    ``src/vendor/``.  Use forward slashes in patterns; ``fnmatch`` treats them as
    literal characters, which matches how :class:`pathlib.Path` serializes on all
    platforms.
    When *respect_gitignore* is true, the nearest ``.gitignore`` at or above the
    scanned directory is also applied.
    """
    ignore_patterns: Sequence[str] = list(extra_ignore_patterns) if extra_ignore_patterns else []
    gitignore = _load_gitignore_spec(directory_path) if respect_gitignore else None
    python_files: List[Path] = []
    for root, dirs, files in os.walk(directory_path):
        filtered_dirs: List[str] = []
        for directory_name in sorted(dirs):
            directory_candidate = Path(root) / directory_name
            if directory_name in SKIP_DIRECTORY_NAMES:
                continue
            if _is_gitignored(
                directory_candidate,
                directory_path=directory_path,
                gitignore=gitignore,
                is_directory=True,
            ):
                continue
            if ignore_patterns:
                rel_dir = str(directory_candidate.relative_to(directory_path))
                if _matches_any_pattern(directory_name, ignore_patterns) or _matches_any_pattern(rel_dir, ignore_patterns):
                    continue
            filtered_dirs.append(directory_name)
        dirs[:] = filtered_dirs
        for file_name in sorted(files):
            file_path = Path(root) / file_name
            if not file_name.endswith(".py"):
                continue
            if _is_gitignored(
                file_path,
                directory_path=directory_path,
                gitignore=gitignore,
                is_directory=False,
            ):
                continue
            if ignore_patterns:
                rel_file = str(file_path.relative_to(directory_path))
                if _matches_any_pattern(file_name, ignore_patterns) or _matches_any_pattern(rel_file, ignore_patterns):
                    continue
            python_files.append(file_path)
    return python_files


def _parse_context(context: Optional[Union[CodemodContext, Dict[str, Union[bool, List]]]]) -> CodemodContext:
    if context is None:
        return CodemodContext()
    if isinstance(context, Dict):
        parsed_context = CodemodContext()
        for key, value in context.items():
            setattr(parsed_context, key, value)
        return parsed_context
    return context


def apply(code: str, codemod: _Codemod) -> str:
    """Apply a single LibCST transformer to `code` and return the transformed source."""
    module = parse_module(code)
    modified_tree = module.visit(codemod)
    return modified_tree.code


def apply_all(code: str, context: Optional[Union[CodemodContext, Dict[str, Union[bool, List]]]] = None) -> str:
    """Apply all Typewriter codemods to `code`.

    Normalizes `None`-related annotations and ensures required imports are present.
    When the context has ``use_pep604`` set, PEP 604 union syntax is emitted instead
    of ``Optional[...]``.
    """
    context = _parse_context(context)
    code = apply(code, EnforceOptionalNoneTypes(context))
    code = apply(code, InferOptionalNoneTypes(context))
    code = apply(code, AddImportsVisitor(context))
    return _cleanup_typing_imports(code, context)


def _cleanup_typing_imports(code: str, context: CodemodContext) -> str:
    """Remove ``typing`` imports that are now unused after rewrites."""
    if getattr(context, "rewrote_union_annotation", False):
        code = _remove_typing_import_if_unused(code, "Union")
    # In PEP 604 mode, inference-only rewrites can make an existing Optional import
    # unused even when no Union[...] annotation was rewritten. Gate this on actual
    # codemod changes so we do not clean up unrelated imports in otherwise-untouched files.
    if getattr(context, "use_pep604", False) and getattr(context, "made_changes", False):
        code = _remove_typing_import_if_unused(code, "Optional")
    return code


class _TypingReferenceCollector(CSTVisitor):
    """Check whether a specific ``typing`` name is referenced outside of import statements."""

    def __init__(self, name: str) -> None:
        super().__init__()
        self.name = name
        self.has_reference = False

    def visit_ImportFrom(self, node: ImportFrom) -> bool:
        return False

    def visit_Name(self, node: Name) -> None:
        if node.value == self.name:
            self.has_reference = True

    def visit_Attribute(self, node: Attribute) -> None:
        if node.attr.value == self.name:
            self.has_reference = True


class _TypingNameImportRemover(CSTTransformer):
    """Remove a specific name from ``from typing import ...`` statements."""

    def __init__(self, name: str) -> None:
        super().__init__()
        self._name = name

    def leave_ImportFrom(
        self,
        original_node: ImportFrom,
        updated_node: ImportFrom,
    ) -> Union[ImportFrom, RemovalSentinel]:
        module = updated_node.module
        if not isinstance(module, Name) or module.value != "typing":
            return updated_node

        if isinstance(updated_node.names, ImportStar):
            return updated_node

        names_to_keep = []
        removed = False
        for import_alias in updated_node.names:
            should_remove = import_alias.evaluated_name == self._name and import_alias.evaluated_alias is None
            if should_remove:
                removed = True
                continue
            names_to_keep.append(import_alias)

        if not removed:
            return updated_node
        if not names_to_keep:
            return RemoveFromParent()

        names_to_keep[-1] = names_to_keep[-1].with_changes(comma=MaybeSentinel.DEFAULT)
        return updated_node.with_changes(names=names_to_keep)


def _remove_typing_import_if_unused(code: str, name: str) -> str:
    """Remove *name* from ``from typing import ...`` if no longer referenced."""
    module = parse_module(code)
    collector = _TypingReferenceCollector(name)
    module.visit(collector)

    if collector.has_reference:
        return code

    return module.visit(_TypingNameImportRemover(name)).code


class EnforceOptionallNoneTypes(EnforceOptionalNoneTypes):
    """Deprecated compatibility wrapper for the misspelled class name."""

    def __init__(self, context: Optional[CodemodContext] = None) -> None:
        warnings.warn(
            "EnforceOptionallNoneTypes is deprecated; use EnforceOptionalNoneTypes instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(context)


@dataclass(frozen=True)
class ProcessResult:
    """File-based transformation result."""

    processed_files: int
    changed_files: List[Path]
    diffs: Dict[Path, str] = field(default_factory=dict)

    @property
    def changed_count(self) -> int:
        return len(self.changed_files)


@dataclass(frozen=True)
class ProcessStringResult:
    """In-memory transformation result."""

    original_code: str
    transformed_code: str

    @property
    def changed(self) -> bool:
        return self.original_code != self.transformed_code


def _unified_diff_text(original: str, transformed: str, *, fromfile: str, tofile: str) -> str:
    diff_lines = unified_diff(
        original.splitlines(),
        transformed.splitlines(),
        fromfile=fromfile,
        tofile=tofile,
        lineterm="",
    )
    return "\n".join(diff_lines) + "\n"


def process_code(code: str, context: Optional[Union[CodemodContext, Dict[str, Union[bool, List]]]] = None) -> ProcessStringResult:
    """Transform a Python source string.

    Returns both the original and transformed source.
    """
    transformed_code = apply_all(code, context=context)
    return ProcessStringResult(original_code=code, transformed_code=transformed_code)


def process_file(
    file_path: Path,
    *,
    write: bool = True,
    include_diff: bool = False,
    context: Optional[Union[CodemodContext, Dict[str, Union[bool, List]]]] = None,
) -> ProcessResult:
    """Transform a single Python file.

    When `write` is true, writes changes back to disk. When `include_diff` is true,
    includes a unified diff for each changed file in the result.
    """
    if file_path.suffix != ".py":
        return ProcessResult(processed_files=0, changed_files=[])

    original_content = file_path.read_text(encoding="utf-8")
    transformed_content = apply_all(original_content, context=context)

    if original_content == transformed_content:
        return ProcessResult(processed_files=1, changed_files=[])

    diffs: Dict[Path, str] = {}
    if include_diff:
        diffs[file_path] = _unified_diff_text(
            original_content,
            transformed_content,
            fromfile=str(file_path),
            tofile=str(file_path),
        )

    if write:
        file_path.write_text(transformed_content, encoding="utf-8")

    return ProcessResult(processed_files=1, changed_files=[file_path], diffs=diffs)


def process_files_in_directory(
    directory_path: Path,
    *,
    write: bool = True,
    include_diff: bool = False,
    context: Optional[Union[CodemodContext, Dict[str, Union[bool, List]]]] = None,
    extra_ignore_patterns: Optional[Sequence[str]] = None,
    respect_gitignore: bool = False,
) -> ProcessResult:
    """Transform all Python files under a directory.

    Recursively walks the directory, skipping common virtualenv/cache/build folders.
    Additional skip patterns can be supplied via *extra_ignore_patterns*.
    When *respect_gitignore* is true, the nearest ``.gitignore`` at or above the
    scanned directory is also applied.
    """
    changed_files: List[Path] = []
    processed_files = 0
    diffs: Dict[Path, str] = {}

    for file_path in _iter_python_files(
        directory_path,
        extra_ignore_patterns=extra_ignore_patterns,
        respect_gitignore=respect_gitignore,
    ):
        result = process_file(file_path, write=write, include_diff=include_diff, context=context)
        processed_files += result.processed_files
        changed_files.extend(result.changed_files)
        diffs.update(result.diffs)

    return ProcessResult(processed_files=processed_files, changed_files=changed_files, diffs=diffs)

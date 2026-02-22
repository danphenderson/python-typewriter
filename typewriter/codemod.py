import os
from dataclasses import dataclass, field
from difflib import unified_diff
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Union

from libcst import (
    AnnAssign,
    Annotation,
    Attribute,
    BaseExpression,
    CSTNode,
    CSTTransformer,
    CSTVisitor,
    ImportFrom,
    ImportStar,
    Index,
    MaybeSentinel,
    Name,
    Param,
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


class CodemodContext(_CodemodContext):
    """Shared state for codemod runs.

    This extends LibCST's `CodemodContext` with a few flags and collections used
    by Typewriter's transformers.
    """

    def __init__(self):
        super().__init__()
        self.code_modifications: List = []
        self.made_changes: bool = False
        self.rewrote_union_none_annotation: bool = False


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


class EnforceOptionallNoneTypes(Codemod):
    """Rewrite `Union[..., None]` annotations into `Optional[...]`.

    For a union containing `None`, this transformation removes `None` and wraps the
    remaining type(s) with `Optional`:

    - `Union[T, None]` -> `Optional[T]`
    - `Union[T1, T2, None]` -> `Optional[Union[T1, T2]]`

    Qualified references are preserved (for example, `typing.Union` -> `typing.Optional`).
    """

    def leave_Subscript(self, original_node: Subscript, updated_node: Subscript) -> Subscript:
        if not self._is_union_reference(updated_node.value):
            return updated_node

        remaining_union_elements = [element for element in updated_node.slice if not self._is_none_union_element(element)]
        if len(remaining_union_elements) == len(updated_node.slice):
            return updated_node
        if not remaining_union_elements:
            return updated_node
        remaining_union_elements = self._normalize_union_elements(remaining_union_elements)

        optional_reference = self._optional_reference_from_union_reference(updated_node.value)
        if len(remaining_union_elements) == 1:
            optional_inner_value = ensure_type(remaining_union_elements[0].slice, Index).value
        else:
            optional_inner_value = Subscript(
                value=updated_node.value,
                slice=list(remaining_union_elements),
            )

        setattr(self.context, "made_changes", True)
        setattr(self.context, "rewrote_union_none_annotation", True)
        return Subscript(
            value=optional_reference,
            slice=[SubscriptElement(slice=Index(value=optional_inner_value))],
        )

    def _is_union_reference(self, node: BaseExpression) -> bool:
        if isinstance(node, Name):
            return node.value == "Union"
        if isinstance(node, Attribute):
            return node.attr.value == "Union"
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
    """Infer `Optional[...]` when an annotated value defaults to `None`.

    - Annotated assignments like `x: T = None` become `x: Optional[T] = None`.
    - Parameters like `def f(x: T = None)` become `def f(x: Optional[T] = None)`.

    If the annotation is already `Optional[...]` or is `Any`, it is left unchanged.
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
        optional_reference = self._optional_reference_for_annotation(annotation.annotation)
        optional_annotation = Annotation(
            annotation=Subscript(
                value=optional_reference,
                slice=[SubscriptElement(slice=Index(value=annotation.annotation))],
            )
        )
        return optional_annotation


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


def _iter_python_files(directory_path: Path) -> Sequence[Path]:
    python_files: List[Path] = []
    for root, dirs, files in os.walk(directory_path):
        dirs[:] = sorted([directory_name for directory_name in dirs if directory_name not in SKIP_DIRECTORY_NAMES])
        for file_name in sorted(files):
            if not file_name.endswith(".py"):
                continue
            python_files.append(Path(root) / file_name)
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
    """
    context = _parse_context(context)
    code = apply(code, EnforceOptionallNoneTypes(context))
    code = apply(code, InferOptionalNoneTypes(context))
    code = apply(code, AddImportsVisitor(context))
    if getattr(context, "rewrote_union_none_annotation", False):
        code = _remove_typing_union_import_if_unused(code)
    return code


class _UnionReferenceCollector(CSTVisitor):
    def __init__(self) -> None:
        super().__init__()
        self.has_union_reference = False

    def visit_ImportFrom(self, node: ImportFrom) -> bool:
        return False

    def visit_Name(self, node: Name) -> None:
        if node.value == "Union":
            self.has_union_reference = True

    def visit_Attribute(self, node: Attribute) -> None:
        if node.attr.value == "Union":
            self.has_union_reference = True


class _TypingUnionImportRemover(CSTTransformer):
    def leave_ImportFrom(
        self,
        original_node: ImportFrom,
        updated_node: ImportFrom,
    ) -> Union[ImportFrom, RemoveFromParent]:
        module = updated_node.module
        if not isinstance(module, Name) or module.value != "typing":
            return updated_node

        if isinstance(updated_node.names, ImportStar):
            return updated_node

        names_to_keep = []
        removed_union = False
        for import_alias in updated_node.names:
            should_remove = import_alias.evaluated_name == "Union" and import_alias.evaluated_alias is None
            if should_remove:
                removed_union = True
                continue
            names_to_keep.append(import_alias)

        if not removed_union:
            return updated_node
        if not names_to_keep:
            return RemoveFromParent()

        names_to_keep[-1] = names_to_keep[-1].with_changes(comma=MaybeSentinel.DEFAULT)
        return updated_node.with_changes(names=names_to_keep)


def _remove_typing_union_import_if_unused(code: str) -> str:
    module = parse_module(code)
    union_reference_collector = _UnionReferenceCollector()
    module.visit(union_reference_collector)

    if union_reference_collector.has_union_reference:
        return code

    return module.visit(_TypingUnionImportRemover()).code


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


def process_file(file_path: Path, *, write: bool = True, include_diff: bool = False) -> ProcessResult:
    """Transform a single Python file.

    When `write` is true, writes changes back to disk. When `include_diff` is true,
    includes a unified diff for each changed file in the result.
    """
    if file_path.suffix != ".py":
        return ProcessResult(processed_files=0, changed_files=[])

    original_content = file_path.read_text(encoding="utf-8")
    transformed_content = apply_all(original_content)

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


def process_files_in_directory(directory_path: Path, *, write: bool = True, include_diff: bool = False) -> ProcessResult:
    """Transform all Python files under a directory.

    Recursively walks the directory, skipping common virtualenv/cache/build folders.
    """
    changed_files: List[Path] = []
    processed_files = 0
    diffs: Dict[Path, str] = {}

    for file_path in _iter_python_files(directory_path):
        result = process_file(file_path, write=write, include_diff=include_diff)
        processed_files += result.processed_files
        changed_files.extend(result.changed_files)
        diffs.update(result.diffs)

    return ProcessResult(processed_files=processed_files, changed_files=changed_files, diffs=diffs)

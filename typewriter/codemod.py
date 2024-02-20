from difflib import unified_diff
from typing import List, Sequence

from libcst import (
    AnnAssign,
    Annotation,
    Attribute,
    CSTNode,
    Index,
    Name,
    Param,
    Subscript,
    SubscriptElement,
    parse_expression,
    parse_statement,
)
from libcst.codemod import Codemod as _Codemod
from libcst.codemod import CodemodContext as _CodemodContext
from rich import print

# TODO: Add duck typing to the codemod classes, e.g. enforce, print_changes, etc.


class CodemodContext(_CodemodContext):
    def __init__(self):
        super().__init__()
        self.code_modifications: List = []
        self.made_changes: bool = False


class Codemod(_Codemod):
    """
    TypeWriter codemods should inherit from this class.

    This class provides a `report_changes` method to log changes and update's the
    `made_changes` flag if changes are detected.
    """

    def transform_module_impl(self, tree: CSTNode) -> CSTNode:
        return tree

    def __init__(self, context: CodemodContext) -> None:
        super().__init__(context)

    @property
    def context(self) -> CodemodContext:
        return getattr(self, "context")

    @property
    def code_modifications(self) -> List:
        return self.context.code_modifications

    @property
    def made_changes(self) -> bool:
        return self.context.made_changes

    def report_changes(self, original_node: CSTNode, updated_node: CSTNode, *, print_changes: bool = False) -> None:
        if original_node.deep_equals(updated_node):
            return
        print(f"Changes detected from {original_node} to {updated_node}")
        origonal_code = getattr(original_node, "code", "")
        updated_code = getattr(updated_node, "code", "")
        code_diff = unified_diff(origonal_code.splitlines(), updated_code.splitlines(), lineterm="")
        self.code_modifications.append(code_diff)


class EncforceOptionallNoneTypes(Codemod):
    """
    Enforce the use of 'Optional' in all 'NoneType' annotated assignments.


    The transformation will remove None from the Union and wrap the remaining type(s)
    with Optional. If there's only one other type besides None, it will be Optional[Type].
    If there are multiple types besides None, it will be Optional[Union[Type1, Type2, ...]].
    """

    def leave_Subscript(self, original_node: Subscript, updated_node: Subscript) -> Subscript:
        # Check if it's a Union type
        if isinstance(updated_node.value, Name) and updated_node.value.value == "Union":
            union_element = updated_node.slice

            # Extract the types in the Union
            union_types = self._extract_union_types(union_element)

            # Check if None is one of the types in the Union
            if "None" in union_types:
                # Remove 'None' and handle single or multiple remaining types
                remaining_types = [t for t in union_types if t != "None"]
                if len(remaining_types) == 1:
                    # Single type + None becomes Optional[SingleType]
                    new_node = parse_expression(f"Optional[{remaining_types[0]}]")
                else:
                    # Multiple types + None becomes Optional[Union[Types...]]
                    new_node = parse_expression(f"Optional[Union[{', '.join(remaining_types)}]]")
                return new_node  # type: ignore

        return updated_node

    def _extract_union_types(self, subscript_slice: Sequence[SubscriptElement]):
        """
        Extract the elements from a subscript slice, handling both simple and subscripted types.
        """
        types = []
        for element in subscript_slice:
            if not isinstance(element, SubscriptElement):
                raise ValueError(f"Unsupported subscript element type: {type(element)}")
            element_index = element.slice
            if isinstance(element_index, Index):
                types.append(self._node_to_string(element_index.value))
        return types

    def _node_to_string(self, node: CSTNode) -> str:
        """
        Convert a CSTNode to its string representation, handling different node types.
        """
        if isinstance(node, Name):
            return node.value
        elif isinstance(node, Subscript):
            value = self._node_to_string(node.value)
            # Handle subscript slices (e.g., List[int])
            slice_parts = [self._node_to_string(s.slice.value) for s in node.slice]  # type: ignore
            return f"{value}[{', '.join(slice_parts)}]"
        elif isinstance(node, Attribute):
            value = self._node_to_string(node.value)
            attr = self._node_to_string(node.attr)
            return f"{value}.{attr}"
        else:
            # This might need to be extended to handle other node types as necessary
            raise ValueError(f"Unsupported node type: {type(node)}")


def enforce_optional_none_types(file_path: str) -> str:
    """
    Apply the EncforceOptionallNoneTypes codemod to the provided file.

    This function will read the file at the provided path, apply the codemod, and return the
    modified code as a string.
    """
    with open(file_path, "r") as file:
        code = file.read()

    module = parse_statement(code)
    context = CodemodContext()
    codemod = EncforceOptionallNoneTypes(context)
    module.visit(codemod)  # type: ignore
    for original_node, updated_node in codemod.code_modifications:
        codemod.report_changes(original_node, updated_node)

    return getattr(module, "code", "")


class EnforceNoneTypesOptional(Codemod):
    """
    Enforce the use of 'Optional' in annotated assignments to None.

    This transformer will wrap the type annotation with Optional if the variable is assigned to None
    or if a function parameter has a default value of None. Note, if the annotation is already Optional, or Any,
    it will remain unchanged.
    """

    def leave_AnnAssign(self, original_node: AnnAssign, updated_node: AnnAssign) -> AnnAssign:
        if isinstance(updated_node.value, Name) and updated_node.value.value == "None":
            if not self._is_optional_annotation(updated_node.annotation):
                new_annotation = self._wrap_with_optional(updated_node.annotation)
                new_node = updated_node.with_changes(annotation=new_annotation)
                return new_node
        return updated_node

    def leave_Param(self, original_node: Param, updated_node: Param) -> Param:
        if updated_node.default is not None and isinstance(updated_node.default, Name) and updated_node.default.value == "None":
            if updated_node.annotation is not None and not self._is_optional_annotation(updated_node.annotation):
                new_annotation = self._wrap_with_optional(updated_node.annotation)
                new_node = updated_node.with_changes(annotation=new_annotation)
                return new_node
        return updated_node

    def _is_optional_annotation(self, annotation: Annotation) -> bool:
        if (
            isinstance(annotation.annotation, Subscript)
            and isinstance(annotation.annotation.value, Name)
            and annotation.annotation.value.value == "Optional"
        ):
            return True
        elif isinstance(annotation.annotation, Name) and annotation.annotation.value == "Any":
            return True
        return False

    def _wrap_with_optional(self, annotation: Annotation) -> Annotation:
        optional_annotation = Annotation(
            annotation=Subscript(value=Name(value="Optional"), slice=[SubscriptElement(slice=Index(value=annotation.annotation))])
        )
        return optional_annotation


def enforce_none_types_optional(file_path: str) -> str:
    """
    Apply the EnforceNoneTypesOptional codemod to the provided file.

    This function will read the file at the provided path, apply the codemod, and return the
    modified code as a string.
    """
    with open(file_path, "r") as file:
        code = file.read()

    module = parse_statement(code)
    context = CodemodContext()
    codemod = EnforceNoneTypesOptional(context)
    module.visit(codemod)  # type: ignore
    for original_node, updated_node in codemod.code_modifications:
        codemod.report_changes(original_node, updated_node)
    return getattr(module, "code", "")

from difflib import unified_diff
from typing import List, Optional, Sequence

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
    ensure_type,
    parse_expression,
    parse_module,
)
from libcst.codemod import CodemodContext as _CodemodContext
from libcst.codemod import ContextAwareTransformer as _Codemod
from libcst.matchers import Name as mName
from libcst.matchers import matches


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

    def __init__(self, context: CodemodContext) -> None:
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
        origonal_code = getattr(original_node, "code", "")
        updated_code = getattr(updated_node, "code", "")
        code_diff = unified_diff(origonal_code.splitlines(), updated_code.splitlines(), lineterm="")
        self.code_modifications.append(code_diff)


class EnforceOptionallNoneTypes(Codemod):
    """
    Enforce the use of 'Optional' in all 'NoneType' annotated assignments.


    The transformation will remove None from the Union and wrap the remaining type(s)
    with Optional. If there's only one other type besides None, it will be Optional[Type].
    If there are multiple types besides None, it will be Optional[Union[Type1, Type2, ...]].
    """

    def leave_Subscript(self, original_node: Subscript, updated_node: Subscript) -> Subscript:
        # Check if it's a Union type
        if matches(updated_node.value, mName("Union")):
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
                    # Multiple types + None becomes Optional[Union[{', '.join(remaining_types)}]]"
                    new_node = parse_expression(f"Optional[Union[{', '.join(remaining_types)}]]")
                setattr(self.context, "made_changes", True)
                return new_node  # type: ignore

        return updated_node

    def _extract_union_types(self, subscript_slice: Sequence[SubscriptElement]):
        """
        Extract the elements from a subscript slice, handling both simple and subscripted types.
        """
        types = []
        for element in subscript_slice:
            element_index = ensure_type(element.slice, Index)
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


class InferOptionalNonTypes(Codemod):
    """
    Infer that a type is 'Optional' in annotated assignments to None.

    This transformer will wrap the type annotation with Optional if the variable is assigned to None
    or if a function parameter has a default value of None. Note, if the annotation is already Optional, or Any,
    it will remain unchanged.
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
        if isinstance(annotation.annotation, Subscript) and matches(annotation.annotation.value, mName("Optional")):
            return True
        elif isinstance(annotation.annotation, Name) and matches(annotation.annotation, mName("Any")):
            return True
        return False

    def _wrap_with_optional(self, annotation: Annotation) -> Annotation:
        optional_annotation = Annotation(
            annotation=Subscript(value=Name(value="Optional"), slice=[SubscriptElement(slice=Index(value=annotation.annotation))])
        )
        return optional_annotation


def enforce_optional_none_types(code: str, context: Optional[CodemodContext] = None) -> str:
    """
    Apply the EncforceOptionallNoneTypes codemod to the provided code.
    """
    context = context or CodemodContext()
    module = parse_module(code)  # Parse the entire code as a module
    codemod = EnforceOptionallNoneTypes(context)
    modified_tree = module.visit(codemod)
    return modified_tree.code


def infer_optional_none_types(code: str, context: Optional[CodemodContext] = None) -> str:
    """
    Apply the EnforceNoneTypesOptional codemod to the provided code.
    """
    context = context or CodemodContext()
    module = parse_module(code)  # Parse the entire code as a module
    codemod = InferOptionalNonTypes(context)
    modified_tree = module.visit(codemod)
    codemod.report_changes(module, modified_tree)
    return modified_tree.code


def apply(code: str) -> str:
    """
    Apply the EnforceOptionalNoneTypes and EnforceNoneTypesOptional codemods to the provided code.
    """
    context = CodemodContext()
    code = enforce_optional_none_types(code, context)
    code = infer_optional_none_types(code, context)
    return code

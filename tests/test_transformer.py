import pytest

from typewriter.codemod import enforce_none_types_optional, enforce_optional_none_types


# Test cases for the UnionToOptionalTransformer
@pytest.mark.parametrize(
    "source_code, expected_code",
    [
        # Test single type with None
        ("a: Union[int, None]", "a: Optional[int]"),
        # Test subscripted single type with None
        ("a: Union[Dict[str, int], None]", "a: Optional[Dict[str, int]]"),
        # Test multiple types including None
        ("a: Union[str, int, None]", "a: Optional[Union[str, int]]"),
        # Test multiple subscripted types with None
        ("a: Union[Dict[str, int], List[int], None]", "a: Optional[Union[Dict[str, int], List[int]]]"),
        # Test Union without None should remain unchanged
        ("a: Union[str, int]", "a: Union[str, int]"),
        # Test Union without None and multiple types should remain unchanged
        ("a: Union[str, int, float]", "a: Union[str, int, float]"),
        # Test nested Unions with None
        ("a: Union[str, Union[int, None]]", "a: Union[str, Optional[int]]"),
        # Test nested Unions without None should remain unchanged
        ("a: Union[str, Union[int, float]]", "a: Union[str, Union[int, float]]"),
        # Test really nested Unions with None
        ("a: Union[str, Union[int, Union[Dict[str, int], None]]]", "a: Union[str, Union[int, Optional[Dict[str, int]]]]"),
        # Test really nested Unions without None should remain unchanged
        ("a: Union[str, Union[int, Union[float, bool]]]", "a: Union[str, Union[int, Union[float, bool]]]"),
        # Test function parameter and return type annotations
        ("def func(a: Union[str, None]) -> Union[int, None]: pass", "def func(a: Optional[str]) -> Optional[int]: pass"),
        # Test async function parameter and return type annotations
        ("async def func(a: Union[str, None]) -> Union[int, None]: pass", "async def func(a: Optional[str]) -> Optional[int]: pass"),
        # Test variable annotations
        ("var: Union[str, None] = 'hello'", "var: Optional[str] = 'hello'"),
        # Test class attribute annotations
        ("class A: a: Union[str, None] = 'hello'", "class A: a: Optional[str] = 'hello'"),
        # Test variable annotations within a function
        ("def func(): var: Union[str, None] = 'hello'", "def func(): var: Optional[str] = 'hello'"),
    ],
)
def test_union_to_optional_transform(source_code, expected_code):
    assert enforce_none_types_optional(source_code) == expected_code


@pytest.mark.parametrize(
    "source_code, expected_code",
    [
        # Test cases specifically for EnforceOptionalTypeHints
        # Single type, should be wrapped with Optional
        ("var: int = None", "var: Optional[int] = None"),
        # Single type with existing Optional, should remain unchanged
        ("var: Optional[int] = None", "var: Optional[int] = None"),
        # Type hint is Any, should remain unchanged
        ("var: Any = None", "var: Any = None"),
        # Nested Optional, inner type should not be wrapped again
        ("var: Optional[Dict[str, int]] = None", "var: Optional[Dict[str, int]] = None"),
        # Without initial annotation, should remain unchanged (though not a common use case for this transformer)
        ("var = None", "var = None"),
        # Ensure complex types are correctly handled
        ("var: Dict[str, List[int]] = None", "var: Optional[Dict[str, List[int]]] = None"),
        # Test annotations within a function param
        ("def func(var: int = None): pass", "def func(var: Optional[int] = None): pass"),
        # Test annotations within a class
        ("class A: var: int = None", "class A: var: Optional[int] = None"),
        # Test annotations within an async function
        ("async def func(var: int = None): pass", "async def func(var: Optional[int] = None): pass"),
        # Test ensure_typing_imports is not applied if no changes were made
        ("from typing import Union", "from typing import Union"),
    ],
)
def test_enforce_optional_transform(source_code, expected_code):
    assert enforce_optional_none_types(source_code) == expected_code


@pytest.mark.parametrize(
    "source_code, expected_code",
    [
        # Test cases for both UnionToOptionalTransformer and EnforceOptionalTransformer
        # Test Union with None and assignment to None
        ("var: Union[int, None] = None", "var: Optional[int] = None"),
        # Test Union with None and function parameter with default value of None
        ("def func(var: Union[int, None] = None): pass", "def func(var: Optional[int] = None): pass"),
    ],
)
def test_union_to_optional_transforms(source_code, expected_code):
    transformed_code = enforce_none_types_optional(source_code)
    transformed_code = enforce_optional_none_types(transformed_code)
    assert transformed_code == expected_code

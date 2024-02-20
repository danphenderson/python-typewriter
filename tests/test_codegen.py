import pytest

from typewriter.codemod import (
    enforce_none_types_optional,
    enforce_optional,
    enforce_optional_none_types,
)


# Test cases for the UnionToOptionalTransformer
@pytest.mark.parametrize(
    "source_code, expected_code",
    [
        ("a: Union[int, None]", "a: Optional[int]"),
        ("a: Union[Dict[str, int], None]", "a: Optional[Dict[str, int]]"),
        ("a: Union[str, int, None]", "a: Optional[Union[str, int]]"),
        ("a: Union[Dict[str, int], List[int], None]", "a: Optional[Union[Dict[str, int], List[int]]]"),
        ("a: Union[str, int]", "a: Union[str, int]"),
        ("a: Union[str, int, float]", "a: Union[str, int, float]"),
        ("a: Union[str, Union[int, None]]", "a: Union[str, Optional[int]]"),
        ("a: Union[str, Union[int, float]]", "a: Union[str, Union[int, float]]"),
        ("a: Union[str, Union[int, Union[Dict[str, int], None]]]", "a: Union[str, Union[int, Optional[Dict[str, int]]]]"),
        ("a: Union[str, Union[int, Union[float, bool]]]", "a: Union[str, Union[int, Union[float, bool]]]"),
        ("def func(a: Union[str, None]) -> Union[int, None]: pass", "def func(a: Optional[str]) -> Optional[int]: pass"),
        ("async def func(a: Union[str, None]) -> Union[int, None]: pass", "async def func(a: Optional[str]) -> Optional[int]: pass"),
        ("var: Union[str, None] = 'hello'", "var: Optional[str] = 'hello'"),
        ("class A: a: Union[str, None] = 'hello'", "class A: a: Optional[str] = 'hello'"),
        ("def func(): var: Union[str, None] = 'hello'", "def func(): var: Optional[str] = 'hello'"),
    ],
)
def test_union_to_optional_transform(source_code, expected_code):
    assert enforce_optional_none_types(source_code) == expected_code


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
    assert enforce_none_types_optional(source_code) == expected_code


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
def test_enforce_optional(source_code, expected_code):
    assert enforce_optional(source_code) == expected_code


def test_inline_comments_are_presserved():
    source_code = "var: Union[int, None] = None  # comment"
    expected_code = "var: Optional[int] = None  # comment"
    assert enforce_optional(source_code) == expected_code


def test_docstrings_are_preserved():
    source_code = '"""docstring"""\nvar: Union[int, None] = None'
    expected_code = '"""docstring"""\nvar: Optional[int] = None'
    assert enforce_optional(source_code) == expected_code


def test_multiline_docstrings_are_preserved():
    source_code = '"""docstring\nmultiline"""\nvar: Union[int, None] = None'
    expected_code = '"""docstring\nmultiline"""\nvar: Optional[int] = None'
    assert enforce_optional(source_code) == expected_code


def test_multiline_comments_are_preserved():
    source_code = '"""docstring"""\nvar: Union[int, None] = None\n# comment\n# comment'
    expected_code = '"""docstring"""\nvar: Optional[int] = None\n# comment\n# comment'
    assert enforce_optional(source_code) == expected_code

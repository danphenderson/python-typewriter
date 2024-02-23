import pytest

from typewriter.codemod import EnforceOptionallNoneTypes, InferOptionalNoneTypes, apply


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
    assert apply(source_code, EnforceOptionallNoneTypes()) == expected_code


@pytest.mark.parametrize(
    "source_code, expected_code",
    [
        ("var: int = None", "var: Optional[int] = None"),
        ("var: Optional[int] = None", "var: Optional[int] = None"),
        ("var: Any = None", "var: Any = None"),
        ("var: Optional[Dict[str, int]] = None", "var: Optional[Dict[str, int]] = None"),
        ("var = None", "var = None"),
        ("var: Dict[str, List[int]] = None", "var: Optional[Dict[str, List[int]]] = None"),
        ("def func(var: int = None): pass", "def func(var: Optional[int] = None): pass"),
        ("class A: var: int = None", "class A: var: Optional[int] = None"),
        ("async def func(var: int = None): pass", "async def func(var: Optional[int] = None): pass"),
        ("from typing import Union", "from typing import Union"),
    ],
)
def test_enforce_optional_transform(source_code, expected_code):
    assert apply(source_code, InferOptionalNoneTypes()) == expected_code

import pytest

from typewriter.codemod import (
    EnforceOptionallNoneTypes,
    InferOptionalNoneTypes,
    apply,
    process_code,
    process_files_in_directory,
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
        ("a: Union[Literal['a'], None]", "a: Optional[Literal['a']]"),
        ("a: Union[Dict[str, Literal['a']], None]", "a: Optional[Dict[str, Literal['a']]]"),
        ("a: typing.Union[int, None]", "a: typing.Optional[int]"),
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
        ("var: typing.Any = None", "var: typing.Any = None"),
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


def test_process_code_transforms_string_and_sets_changed_flag():
    result = process_code("var: int = None\n")
    assert result.changed is True
    assert "Optional[int]" in result.transformed_code
    assert "from typing import Optional" in result.transformed_code


def test_process_code_does_not_duplicate_existing_optional_import():
    source_code = "from typing import Optional\n\nvar: int = None\n"
    result = process_code(source_code)

    assert result.changed is True
    assert result.transformed_code.count("from typing import Optional") == 1


def test_process_code_reuses_typing_namespace_for_qualified_union():
    source_code = "import typing\nx: typing.Union[int, None] = None\n"
    result = process_code(source_code)

    assert result.changed is True
    assert "x: typing.Optional[int] = None" in result.transformed_code
    assert "from typing import Optional" not in result.transformed_code


def test_process_code_removes_unused_union_import_when_fully_rewritten():
    source_code = "from typing import Union\nx: Union[int, None] = None\n"
    result = process_code(source_code)

    assert result.changed is True
    assert "x: Optional[int] = None" in result.transformed_code
    assert "from typing import Union" not in result.transformed_code
    assert "from typing import Optional" in result.transformed_code


def test_process_code_keeps_union_import_when_union_is_still_used():
    source_code = "from typing import Union\n" "x: Union[int, None] = None\n" "y: Union[str, int]\n"
    result = process_code(source_code)

    assert result.changed is True
    assert "x: Optional[int] = None" in result.transformed_code
    assert "y: Union[str, int]" in result.transformed_code
    assert "from typing import Optional, Union" in result.transformed_code


def test_process_code_removes_from_typing_union_even_when_rewrite_is_qualified():
    source_code = "from typing import Union\n" "import typing\n" "x: typing.Union[int, None] = None\n"
    result = process_code(source_code)

    assert result.changed is True
    assert "x: typing.Optional[int] = None" in result.transformed_code
    assert "from typing import Union" not in result.transformed_code


def test_process_files_in_directory_skips_virtualenv_and_cache_folders(tmp_path):
    source_file = tmp_path / "pkg" / "a.py"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("x: int = None\n", encoding="utf-8")

    ignored_file = tmp_path / ".venv" / "ignored.py"
    ignored_file.parent.mkdir(parents=True)
    ignored_file.write_text("y: int = None\n", encoding="utf-8")

    cache_file = tmp_path / "__pycache__" / "ignored.py"
    cache_file.parent.mkdir(parents=True)
    cache_file.write_text("z: int = None\n", encoding="utf-8")

    result = process_files_in_directory(tmp_path, write=False)

    assert result.processed_files == 1
    assert result.changed_files == [source_file]

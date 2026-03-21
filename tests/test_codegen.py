import pytest

from typewriter.codemod import (
    CodemodContext,
    EnforceOptionalNoneTypes,
    InferOptionalNoneTypes,
    _iter_python_files,
    apply,
    process_code,
    process_files_in_directory,
)


# ---------------------------------------------------------------------------
# Union → Optional (default mode)
# ---------------------------------------------------------------------------
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
    assert apply(source_code, EnforceOptionalNoneTypes()) == expected_code


# ---------------------------------------------------------------------------
# Infer Optional (default mode)
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# PEP 604 mode – Union → T | None
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "source_code, expected_code",
    [
        ("a: Union[int, None]", "a: int | None"),
        ("a: Union[str, int, None]", "a: str | int | None"),
        ("a: Union[Dict[str, int], None]", "a: Dict[str, int] | None"),
        ("a: typing.Union[int, None]", "a: int | None"),
        ("a: Union[str, int]", "a: str | int"),
        ("a: Optional[int]", "a: int | None"),
        ("def func(a: Union[str, None]) -> Union[int, None]: pass", "def func(a: str | None) -> int | None: pass"),
        ("def func(a: Optional[str]) -> Optional[int]: pass", "def func(a: str | None) -> int | None: pass"),
        ("var: Union[str, None] = 'hello'", "var: str | None = 'hello'"),
    ],
)
def test_union_to_pep604_transform(source_code, expected_code):
    ctx = CodemodContext(use_pep604=True)
    assert apply(source_code, EnforceOptionalNoneTypes(ctx)) == expected_code


# ---------------------------------------------------------------------------
# PEP 604 mode – Infer T | None
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "source_code, expected_code",
    [
        ("var: int = None", "var: int | None = None"),
        ("def func(var: int = None): pass", "def func(var: int | None = None): pass"),
        ("var: Any = None", "var: Any = None"),
        ("var: int | None = None", "var: int | None = None"),
    ],
)
def test_infer_pep604_optional(source_code, expected_code):
    ctx = CodemodContext(use_pep604=True)
    assert apply(source_code, InferOptionalNoneTypes(ctx)) == expected_code


# ---------------------------------------------------------------------------
# PEP 604 – already-PEP604 input is not double-wrapped (regression guard)
# ---------------------------------------------------------------------------
def test_pep604_already_optional_not_rewrapped():
    ctx = CodemodContext(use_pep604=True)
    source = "var: int | None = None"
    assert apply(source, InferOptionalNoneTypes(ctx)) == source


# ---------------------------------------------------------------------------
# process_code – existing behaviour preserved
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# PEP 604 – import cleanup
# ---------------------------------------------------------------------------
def test_pep604_removes_union_import_when_fully_rewritten():
    source_code = "from typing import Union\nx: Union[int, None] = None\n"
    ctx = CodemodContext(use_pep604=True)
    result = process_code(source_code, context=ctx)

    assert result.changed is True
    assert "x: int | None = None" in result.transformed_code
    assert "from typing import Union" not in result.transformed_code
    assert "from typing import Optional" not in result.transformed_code


def test_pep604_rewrites_plain_union_and_removes_union_import():
    source_code = "from typing import Union\n" "x: Union[int, None] = None\n" "y: Union[str, int]\n"
    ctx = CodemodContext(use_pep604=True)
    result = process_code(source_code, context=ctx)

    assert result.changed is True
    assert "x: int | None = None" in result.transformed_code
    assert "y: str | int" in result.transformed_code
    assert "from typing import Union" not in result.transformed_code


def test_pep604_process_code_infer():
    """In PEP 604 mode, inferred None defaults use ``T | None`` syntax."""
    ctx = CodemodContext(use_pep604=True)
    result = process_code("var: int = None\n", context=ctx)

    assert result.changed is True
    assert "var: int | None = None" in result.transformed_code
    assert "Optional" not in result.transformed_code


def test_pep604_infer_removes_unused_optional_import():
    """Inference-only PEP 604 rewrites should drop now-unused Optional imports."""
    source = "from typing import Optional\nx: int = None\n"
    ctx = CodemodContext(use_pep604=True)
    result = process_code(source, context=ctx)

    assert result.changed is True
    assert result.transformed_code == "x: int | None = None\n"


def test_pep604_combined_union_and_infer():
    """Both transformers chain correctly in PEP 604 mode."""
    source = "from typing import Union\nx: Union[int, None] = None\ny: str = None\n"
    ctx = CodemodContext(use_pep604=True)
    result = process_code(source, context=ctx)

    assert result.changed is True
    assert "x: int | None = None" in result.transformed_code
    assert "y: str | None = None" in result.transformed_code
    assert "Optional" not in result.transformed_code


# ---------------------------------------------------------------------------
# Import normalization – mixed scenarios
# ---------------------------------------------------------------------------
def test_import_cleanup_preserves_aliased_union():
    """An aliased Union import should not be removed."""
    source = "from typing import Union as U\nx: U[int, None] = None\n"
    result = process_code(source)
    # The alias prevents our remover from touching it (evaluated_alias != None)
    assert "Union as U" in result.transformed_code


def test_import_cleanup_preserves_star_import():
    """Star imports from typing are never modified."""
    source = "from typing import *\nx: Union[int, None] = None\n"
    result = process_code(source)
    assert "from typing import *" in result.transformed_code


def test_import_cleanup_removes_optional_import_in_pep604_mode_when_unused():
    """If Optional was imported only for the now-rewritten annotation, remove it."""
    source = "from typing import Optional, Union\nx: Union[int, None] = None\n"
    ctx = CodemodContext(use_pep604=True)
    result = process_code(source, context=ctx)

    assert "x: int | None = None" in result.transformed_code
    assert "Union" not in result.transformed_code
    assert "Optional" not in result.transformed_code


def test_import_cleanup_keeps_aliased_optional_import_in_pep604_mode():
    """Aliased Optional imports stay if they remain referenced after rewrites."""
    source = "from typing import Optional as Opt, Union\nx: Union[int, None] = None\ny: Opt[str]\n"
    ctx = CodemodContext(use_pep604=True)
    result = process_code(source, context=ctx)

    assert "x: int | None = None" in result.transformed_code
    assert "y: Opt[str]" in result.transformed_code
    assert "Optional as Opt" in result.transformed_code


# ---------------------------------------------------------------------------
# Default skip directories
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Configurable skip patterns
# ---------------------------------------------------------------------------
def test_extra_ignore_patterns_skips_matching_directories(tmp_path):
    kept = tmp_path / "src" / "a.py"
    kept.parent.mkdir(parents=True)
    kept.write_text("x: int = None\n", encoding="utf-8")

    skipped = tmp_path / "generated" / "b.py"
    skipped.parent.mkdir(parents=True)
    skipped.write_text("y: int = None\n", encoding="utf-8")

    result = process_files_in_directory(tmp_path, write=False, extra_ignore_patterns=["generated"])

    assert result.processed_files == 1
    assert result.changed_files == [kept]


def test_extra_ignore_patterns_skips_matching_files(tmp_path):
    kept = tmp_path / "module.py"
    kept.write_text("x: int = None\n", encoding="utf-8")

    skipped = tmp_path / "test_module.py"
    skipped.write_text("y: int = None\n", encoding="utf-8")

    result = process_files_in_directory(tmp_path, write=False, extra_ignore_patterns=["test_*"])

    assert result.processed_files == 1
    assert result.changed_files == [kept]


def test_extra_ignore_patterns_works_with_relative_paths(tmp_path):
    kept = tmp_path / "src" / "app.py"
    kept.parent.mkdir(parents=True)
    kept.write_text("x: int = None\n", encoding="utf-8")

    skipped = tmp_path / "src" / "vendor" / "lib.py"
    skipped.parent.mkdir(parents=True)
    skipped.write_text("y: int = None\n", encoding="utf-8")

    result = process_files_in_directory(tmp_path, write=False, extra_ignore_patterns=["src/vendor/*"])

    assert result.processed_files == 1
    assert result.changed_files == [kept]


def test_default_skips_still_apply_with_extra_patterns(tmp_path):
    """Default skip set is not overridden by extra ignore patterns."""
    kept = tmp_path / "a.py"
    kept.write_text("x: int = None\n", encoding="utf-8")

    venv_file = tmp_path / ".venv" / "ignored.py"
    venv_file.parent.mkdir(parents=True)
    venv_file.write_text("y: int = None\n", encoding="utf-8")

    custom_file = tmp_path / "custom_skip" / "ignored.py"
    custom_file.parent.mkdir(parents=True)
    custom_file.write_text("z: int = None\n", encoding="utf-8")

    result = process_files_in_directory(tmp_path, write=False, extra_ignore_patterns=["custom_skip"])

    assert result.processed_files == 1
    assert result.changed_files == [kept]


def test_iter_python_files_empty_extra_patterns_same_as_none(tmp_path):
    f = tmp_path / "a.py"
    f.write_text("pass\n", encoding="utf-8")

    assert list(_iter_python_files(tmp_path)) == list(_iter_python_files(tmp_path, extra_ignore_patterns=[]))


def test_iter_python_files_respects_gitignore(tmp_path):
    kept = tmp_path / "src" / "a.py"
    kept.parent.mkdir(parents=True)
    kept.write_text("x: int = None\n", encoding="utf-8")

    ignored = tmp_path / "generated" / "b.py"
    ignored.parent.mkdir(parents=True)
    ignored.write_text("y: int = None\n", encoding="utf-8")

    (tmp_path / ".gitignore").write_text("generated/\n", encoding="utf-8")

    assert list(_iter_python_files(tmp_path, respect_gitignore=True)) == [kept]


def test_process_files_in_directory_respects_parent_gitignore(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / ".gitignore").write_text("ignored.py\n", encoding="utf-8")

    scanned_dir = project / "pkg"
    scanned_dir.mkdir()

    kept = scanned_dir / "kept.py"
    kept.write_text("x: int = None\n", encoding="utf-8")

    ignored = scanned_dir / "ignored.py"
    ignored.write_text("y: int = None\n", encoding="utf-8")

    result = process_files_in_directory(scanned_dir, write=False, respect_gitignore=True)

    assert result.processed_files == 1
    assert result.changed_files == [kept]


# ---------------------------------------------------------------------------
# Version lookup
# ---------------------------------------------------------------------------
def test_version_lookup_uses_correct_distribution_name():
    from typewriter import _DISTRIBUTION_NAME, __version__

    assert _DISTRIBUTION_NAME == "py-typewriter-cli"
    # When installed, __version__ should be a non-empty string.
    assert isinstance(__version__, str)
    assert __version__ != ""


def test_version_is_not_fallback_when_installed():
    """When the package is installed, __version__ should not be the fallback."""
    from typewriter import __version__

    # The fallback is "0.0.0"; an installed package must report a real version.
    assert __version__ != "0.0.0"


def test_version_falls_back_to_pyproject_when_distribution_metadata_is_unavailable(monkeypatch):
    import typewriter

    def raise_missing_distribution(_: str) -> str:
        raise typewriter.importlib_metadata.PackageNotFoundError("missing")

    monkeypatch.setattr(typewriter.importlib_metadata, "version", raise_missing_distribution)

    assert typewriter._resolve_version() == "1.0.0"


def test_version_falls_back_to_zero_when_metadata_and_pyproject_are_unavailable(monkeypatch):
    import typewriter

    def raise_missing_distribution(_: str) -> str:
        raise typewriter.importlib_metadata.PackageNotFoundError("missing")

    monkeypatch.setattr(typewriter.importlib_metadata, "version", raise_missing_distribution)
    monkeypatch.setattr(typewriter, "_read_pyproject_version", lambda: None)

    assert typewriter._resolve_version() == "0.0.0"


# ---------------------------------------------------------------------------
# Docs version sourcing
# ---------------------------------------------------------------------------
def test_docs_conf_version_matches_package_version():
    """The Sphinx conf.py version must equal the package version."""
    import re
    from pathlib import Path as _Path

    conf_path = _Path(__file__).resolve().parent.parent / "docs" / "source" / "conf.py"
    conf_text = conf_path.read_text(encoding="utf-8")

    # The conf.py should import version from typewriter (not hard-code it)
    assert "from typewriter import __version__" in conf_text or "from typewriter import" in conf_text
    assert "version = release = _pkg_version" in conf_text
    # It should NOT contain a hard-coded version string assignment like version = '0.1.0'
    hard_coded = re.search(r"^version\s*=\s*release\s*=\s*['\"][\d.]+['\"]", conf_text, re.MULTILINE)
    assert hard_coded is None, f"Docs conf.py has hard-coded version: {hard_coded.group()}"

import pytest

from typewriter import TypewriterRunner


def test_runner_process_code_uses_target_version_for_pep604_output():
    result = TypewriterRunner(target_version="3.10").process_code("value: int = None\n")

    assert result.changed is True
    assert "value: int | None = None" in result.transformed_code


def test_runner_process_file_can_collect_diff_without_writing(tmp_path):
    file_path = tmp_path / "example.py"
    original_code = "value: int = None\n"
    file_path.write_text(original_code, encoding="utf-8")

    result = TypewriterRunner().process_file(file_path, write=False, include_diff=True)

    assert result.changed_files == [file_path]
    assert file_path.read_text(encoding="utf-8") == original_code
    assert result.diffs[file_path].startswith(f"--- {file_path}")


def test_runner_process_directory_uses_ignore_and_gitignore(tmp_path):
    kept = tmp_path / "pkg" / "keep.py"
    kept.parent.mkdir(parents=True)
    kept.write_text("value: int = None\n", encoding="utf-8")

    ignored_by_pattern = tmp_path / "generated" / "skip.py"
    ignored_by_pattern.parent.mkdir(parents=True)
    ignored_by_pattern.write_text("value: int = None\n", encoding="utf-8")

    ignored_by_git = tmp_path / "ignored.py"
    ignored_by_git.write_text("value: int = None\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("ignored.py\n", encoding="utf-8")

    result = TypewriterRunner(ignore=["generated"], respect_gitignore=True).process_directory(tmp_path, write=False)

    assert result.processed_files == 1
    assert result.changed_files == [kept]


def test_runner_rejects_conflicting_target_version_and_use_pep604():
    with pytest.raises(ValueError, match="must agree"):
        TypewriterRunner(target_version="3.9", use_pep604=True)

import json

from typer.testing import CliRunner

from typewriter.cli import app

runner = CliRunner()


def test_run_requires_path_argument():
    result = runner.invoke(app, ["run"])

    assert result.exit_code != 0
    assert "either PATH or --code must be provided" in result.output


def test_root_invocation_without_subcommand_is_rejected(tmp_path):
    result = runner.invoke(app, [str(tmp_path)])

    assert result.exit_code != 0
    assert "No such command" in result.output


def test_run_rejects_missing_directory():
    result = runner.invoke(app, ["run", "does-not-exist"])

    assert result.exit_code != 0
    assert "does not exist" in result.output


def test_run_writes_changes_in_place(tmp_path):
    file_path = tmp_path / "example.py"
    file_path.write_text("var: int = None\n", encoding="utf-8")

    result = runner.invoke(app, ["run", str(tmp_path)])

    assert result.exit_code == 0
    updated_content = file_path.read_text(encoding="utf-8")
    assert "Optional[int]" in updated_content
    assert "var: int = None" not in updated_content
    assert "Transformed " in result.output


def test_run_check_does_not_write_and_returns_one(tmp_path):
    file_path = tmp_path / "example.py"
    original_content = "var: int = None\n"
    file_path.write_text(original_content, encoding="utf-8")

    result = runner.invoke(app, ["run", str(tmp_path), "--check"])

    assert result.exit_code == 1
    assert file_path.read_text(encoding="utf-8") == original_content
    assert "Would transform " in result.output
    assert "would be transformed" in result.output
    assert "--- " in result.output
    assert "+++ " in result.output
    assert "-var: int = None" in result.output
    assert "+var: Optional[int] = None" in result.output


def test_run_check_clean_directory_returns_zero(tmp_path):
    file_path = tmp_path / "example.py"
    file_path.write_text("var: Optional[int] = None\n", encoding="utf-8")

    result = runner.invoke(app, ["run", str(tmp_path), "--check"])

    assert result.exit_code == 0
    assert "No files need changes." in result.output


def test_run_check_skips_virtualenv_files(tmp_path):
    source_file = tmp_path / "example.py"
    source_file.write_text("var: int = None\n", encoding="utf-8")

    ignored_file = tmp_path / ".venv" / "ignored.py"
    ignored_file.parent.mkdir(parents=True)
    ignored_file.write_text("ignored: int = None\n", encoding="utf-8")

    result = runner.invoke(app, ["run", str(tmp_path), "--check"])

    assert result.exit_code == 1
    assert "1 file(s) would be transformed." in result.output
    assert ".venv" not in result.output


def test_run_accepts_single_file_and_writes_changes(tmp_path):
    file_path = tmp_path / "example.py"
    file_path.write_text("var: int = None\n", encoding="utf-8")

    result = runner.invoke(app, ["run", str(file_path)])

    assert result.exit_code == 0
    updated_content = file_path.read_text(encoding="utf-8")
    assert "Optional[int]" in updated_content
    assert "Transformed " in result.output


def test_run_accepts_single_file_check_does_not_write_and_returns_one(tmp_path):
    file_path = tmp_path / "example.py"
    original_content = "var: int = None\n"
    file_path.write_text(original_content, encoding="utf-8")

    result = runner.invoke(app, ["run", str(file_path), "--check"])

    assert result.exit_code == 1
    assert file_path.read_text(encoding="utf-8") == original_content
    assert "Would transform " in result.output
    assert "--- " in result.output
    assert "+++ " in result.output
    assert "-var: int = None" in result.output
    assert "+var: Optional[int] = None" in result.output


def test_run_code_transforms_and_prints_to_stdout():
    result = runner.invoke(app, ["run", "--code", "var: int = None\n"])

    assert result.exit_code == 0
    assert "Optional[int]" in result.output


def test_run_code_accepts_literal_backslash_n_sequence():
    result = runner.invoke(app, ["run", "--code", "var: int = None\\n"])

    assert result.exit_code == 0
    assert "Optional[int]" in result.output


def test_run_code_check_returns_one_when_changes_needed():
    result = runner.invoke(app, ["run", "--code", "var: int = None\n", "--check"])

    assert result.exit_code == 1
    assert "Would transform provided code." in result.output
    assert "--- provided" in result.output
    assert "+++ provided" in result.output
    assert "-var: int = None" in result.output
    assert "+var: Optional[int] = None" in result.output


def test_run_code_check_returns_zero_when_no_changes_needed():
    result = runner.invoke(app, ["run", "--code", "var: Optional[int] = None\n", "--check"])

    assert result.exit_code == 0
    assert "No changes." in result.output


def test_run_code_json_output_contains_transformed_code():
    result = runner.invoke(app, ["run", "--code", "var: int = None\n", "--output-format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["type"] == "code"
    assert payload["changed"] is True
    assert "Optional[int]" in payload["transformed_code"]


def test_run_code_json_check_output_contains_diff_and_preserves_exit_code():
    result = runner.invoke(app, ["run", "--code", "var: int = None\n", "--check", "--output-format", "json"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["type"] == "code"
    assert payload["changed"] is True
    assert "--- provided" in payload["diff"]
    assert "transformed_code" not in payload


# ---------------------------------------------------------------------------
# --target-version
# ---------------------------------------------------------------------------
def test_run_code_with_target_version_310_uses_pep604():
    result = runner.invoke(app, ["run", "--code", "var: int = None\n", "--target-version", "3.10"])

    assert result.exit_code == 0
    assert "int | None" in result.output
    assert "Optional" not in result.output


def test_run_code_with_target_version_39_uses_optional():
    result = runner.invoke(app, ["run", "--code", "var: int = None\n", "--target-version", "3.9"])

    assert result.exit_code == 0
    assert "Optional[int]" in result.output


def test_run_code_default_target_version_uses_optional():
    result = runner.invoke(app, ["run", "--code", "var: int = None\n"])

    assert result.exit_code == 0
    assert "Optional[int]" in result.output


def test_run_code_target_version_invalid_is_rejected():
    result = runner.invoke(app, ["run", "--code", "var: int = None\n", "--target-version", "abc"])

    assert result.exit_code != 0


def test_run_directory_with_target_version_310(tmp_path):
    file_path = tmp_path / "example.py"
    file_path.write_text("var: int = None\n", encoding="utf-8")

    result = runner.invoke(app, ["run", str(tmp_path), "--target-version", "3.10"])

    assert result.exit_code == 0
    updated = file_path.read_text(encoding="utf-8")
    assert "int | None" in updated


def test_run_code_with_target_version_310_normalizes_optional_and_union():
    result = runner.invoke(
        app,
        ["run", "--code", "from typing import Optional, Union\nx: Optional[int]\ny: Union[str, int]\n", "--target-version", "3.10"],
    )

    assert result.exit_code == 0
    assert "x: int | None" in result.output
    assert "y: str | int" in result.output
    assert "Optional" not in result.output
    assert "Union" not in result.output


def test_run_directory_json_output_contains_changed_files_and_diffs(tmp_path):
    file_path = tmp_path / "example.py"
    file_path.write_text("var: int = None\n", encoding="utf-8")

    result = runner.invoke(app, ["run", str(tmp_path), "--check", "--output-format", "json"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["type"] == "directory"
    assert payload["changed_count"] == 1
    assert payload["changed_files"] == [str(file_path)]
    assert file_path.as_posix() in payload["diffs"]


# ---------------------------------------------------------------------------
# --ignore
# ---------------------------------------------------------------------------
def test_run_ignore_skips_matching_directories(tmp_path):
    source = tmp_path / "src" / "a.py"
    source.parent.mkdir(parents=True)
    source.write_text("var: int = None\n", encoding="utf-8")

    skipped = tmp_path / "generated" / "b.py"
    skipped.parent.mkdir(parents=True)
    skipped.write_text("var: int = None\n", encoding="utf-8")

    result = runner.invoke(app, ["run", str(tmp_path), "--check", "--ignore", "generated"])

    assert result.exit_code == 1
    assert "1 file(s) would be transformed." in result.output
    assert "generated" not in result.output


def test_run_ignore_skips_matching_files(tmp_path):
    source = tmp_path / "module.py"
    source.write_text("var: int = None\n", encoding="utf-8")

    skipped = tmp_path / "test_module.py"
    skipped.write_text("var: int = None\n", encoding="utf-8")

    result = runner.invoke(app, ["run", str(tmp_path), "--check", "--ignore", "test_*"])

    assert result.exit_code == 1
    assert "1 file(s) would be transformed." in result.output


def test_run_multiple_ignore_patterns(tmp_path):
    source = tmp_path / "good.py"
    source.write_text("var: int = None\n", encoding="utf-8")

    skip1 = tmp_path / "test_x.py"
    skip1.write_text("var: int = None\n", encoding="utf-8")

    skip2 = tmp_path / "generated" / "y.py"
    skip2.parent.mkdir(parents=True)
    skip2.write_text("var: int = None\n", encoding="utf-8")

    result = runner.invoke(app, ["run", str(tmp_path), "--check", "--ignore", "test_*", "--ignore", "generated"])

    assert result.exit_code == 1
    assert "1 file(s) would be transformed." in result.output


def test_run_respect_gitignore_skips_ignored_files(tmp_path):
    source = tmp_path / "module.py"
    source.write_text("var: int = None\n", encoding="utf-8")

    skipped = tmp_path / "generated.py"
    skipped.write_text("var: int = None\n", encoding="utf-8")

    (tmp_path / ".gitignore").write_text("generated.py\n", encoding="utf-8")

    result = runner.invoke(app, ["run", str(tmp_path), "--check", "--respect-gitignore"])

    assert result.exit_code == 1
    assert "1 file(s) would be transformed." in result.output
    assert "generated.py" not in result.output


def test_run_json_errors_are_emitted_to_stderr():
    result = runner.invoke(app, ["run", "--code", "var: int = None\n", "--target-version", "abc", "--output-format", "json"])

    assert result.exit_code == 2
    payload = json.loads(result.stderr)
    assert payload["type"] == "error"
    assert "Invalid target version" in payload["error"]

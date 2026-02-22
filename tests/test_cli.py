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

import json
import subprocess
import sys
from pathlib import Path

import click
import pytest
from typer.testing import CliRunner

import typewriter.config as config_module
from typewriter import cli as cli_module
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


def test_run_code_json_check_output_clean_returns_zero_without_diff():
    result = runner.invoke(app, ["run", "--code", "var: Optional[int] = None\n", "--check", "--output-format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["type"] == "code"
    assert payload["changed"] is False
    assert "diff" not in payload


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


def test_run_directory_json_output_clean_returns_zero_without_diffs(tmp_path):
    file_path = tmp_path / "example.py"
    file_path.write_text("var: Optional[int] = None\n", encoding="utf-8")

    result = runner.invoke(app, ["run", str(tmp_path), "--check", "--output-format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["type"] == "directory"
    assert payload["changed_count"] == 0
    assert "diffs" not in payload


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


def test_run_json_error_is_emitted_when_path_and_code_are_both_provided(tmp_path):
    file_path = tmp_path / "example.py"
    file_path.write_text("var: int = None\n", encoding="utf-8")

    result = runner.invoke(app, ["run", str(file_path), "--code", "var: int = None\n", "--output-format", "json"])

    assert result.exit_code == 2
    payload = json.loads(result.stderr)
    assert payload["type"] == "error"
    assert "Provide either PATH or --code" in payload["error"]


def test_run_json_error_is_emitted_when_path_or_code_is_missing():
    result = runner.invoke(app, ["run", "--output-format", "json"])

    assert result.exit_code == 2
    payload = json.loads(result.stderr)
    assert payload == {"error": "either PATH or --code must be provided.", "type": "error"}


def test_run_json_error_is_emitted_for_non_python_files(tmp_path):
    file_path = tmp_path / "example.txt"
    file_path.write_text("var: int = None\n", encoding="utf-8")

    result = runner.invoke(app, ["run", str(file_path), "--output-format", "json"])

    assert result.exit_code == 2
    payload = json.loads(result.stderr)
    assert payload["type"] == "error"
    assert "Only '.py' files are supported." in payload["error"]


def test_run_json_error_is_emitted_for_click_exceptions(monkeypatch):
    def raise_click_exception(*args, **kwargs):
        raise click.ClickException("boom")

    monkeypatch.setattr(cli_module.TypewriterRunner, "process_code", raise_click_exception)

    result = runner.invoke(app, ["run", "--code", "var: int = None\n", "--output-format", "json"])

    assert result.exit_code == 1
    payload = json.loads(result.stderr)
    assert payload == {"error": "boom", "type": "error"}


def test_run_multiple_paths_json_check_preserves_order_and_deduplicates(tmp_path):
    first = tmp_path / "b.py"
    first.write_text("b: int = None\n", encoding="utf-8")
    second = tmp_path / "a.py"
    second.write_text("a: int = None\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["run", str(first), str(tmp_path), "--check", "--output-format", "json"],
    )

    assert result.exit_code == 1
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["type"] == "paths"
    assert payload["paths"] == [str(first), str(tmp_path)]
    assert payload["processed_files"] == 2
    assert payload["changed_count"] == 2
    assert payload["changed_files"] == [str(first), str(second)]
    assert set(payload["diffs"]) == {str(first), str(second)}
    assert first.read_text(encoding="utf-8") == "b: int = None\n"
    assert second.read_text(encoding="utf-8") == "a: int = None\n"


def test_run_multiple_paths_apply_is_atomic_when_later_file_is_malformed(tmp_path):
    first = tmp_path / "a.py"
    original = b"a: int = None\n"
    first.write_bytes(original)
    malformed = tmp_path / "b.py"
    malformed.write_text("def broken(:\n", encoding="utf-8")

    result = runner.invoke(app, ["run", str(first), str(malformed), "--output-format", "json"])

    assert result.exit_code == 2
    assert result.stdout == ""
    assert json.loads(result.stderr)["type"] == "error"
    assert first.read_bytes() == original


def test_run_invalid_later_path_does_not_modify_an_earlier_file(tmp_path):
    first = tmp_path / "a.py"
    original = b"a: int = None\n"
    first.write_bytes(original)
    unsupported = tmp_path / "notes.txt"
    unsupported.write_text("not Python\n", encoding="utf-8")

    result = runner.invoke(app, ["run", str(first), str(unsupported)])

    assert result.exit_code == 2
    assert "Only '.py' files are supported" in result.output
    assert first.read_bytes() == original


def test_run_missing_later_path_emits_one_json_error_without_writing(tmp_path):
    first = tmp_path / "a.py"
    original = b"a: int = None\n"
    first.write_bytes(original)
    missing = tmp_path / "missing.py"

    result = runner.invoke(app, ["run", str(first), str(missing), "--output-format", "json"])

    assert result.exit_code == 2
    assert result.stdout == ""
    payload = json.loads(result.stderr)
    assert payload["type"] == "error"
    assert "does not exist" in payload["error"]
    assert first.read_bytes() == original


def test_run_code_rejects_multiple_paths(tmp_path):
    first = tmp_path / "a.py"
    first.write_text("a: int = None\n", encoding="utf-8")
    second = tmp_path / "b.py"
    second.write_text("b: int = None\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["run", str(first), str(second), "--code", "value: int = None\n", "--output-format", "json"],
    )

    assert result.exit_code == 2
    assert result.stdout == ""
    payload = json.loads(result.stderr)
    assert payload["type"] == "error"
    assert "Provide either PATH" in payload["error"]


def test_run_single_path_json_schema_remains_singular(tmp_path):
    file_path = tmp_path / "example.py"
    file_path.write_text("value: Optional[int] = None\n", encoding="utf-8")

    result = runner.invoke(app, ["run", str(file_path), "--check", "--output-format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["type"] == "file"
    assert payload["path"] == str(file_path)
    assert "paths" not in payload
    assert "config" not in payload
    assert "provenance" not in payload


def test_run_discovers_project_config_from_invocation_cwd(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / "pyproject.toml").write_text(
        '[tool.typewriter]\ntarget-version = "3.10"\n',
        encoding="utf-8",
    )
    invocation_cwd = project / "src" / "package"
    invocation_cwd.mkdir(parents=True)
    monkeypatch.chdir(invocation_cwd)

    result = runner.invoke(
        app,
        ["run", "--code", "value: int = None\n", "--output-format", "json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["target_version"] == "3.10"
    assert payload["use_pep604"] is True
    assert "int | None" in payload["transformed_code"]


def test_run_explicit_config_bypasses_discovery_and_cli_target_wins(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / "pyproject.toml").write_text(
        '[tool.typewriter]\ntarget-version = "3.9"\n',
        encoding="utf-8",
    )
    explicit = tmp_path / "policy.toml"
    explicit.write_text(
        '[tool.typewriter]\ntarget-version = "3.10"\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(project)

    explicit_result = runner.invoke(
        app,
        [
            "run",
            "--code",
            "value: int = None\n",
            "--config",
            str(explicit),
            "--output-format",
            "json",
        ],
    )
    overridden_result = runner.invoke(
        app,
        [
            "run",
            "--code",
            "value: int = None\n",
            "--config",
            str(explicit),
            "--target-version",
            "3.9",
            "--output-format",
            "json",
        ],
    )

    assert explicit_result.exit_code == overridden_result.exit_code == 0
    explicit_payload = json.loads(explicit_result.stdout)
    overridden_payload = json.loads(overridden_result.stdout)
    assert explicit_payload["target_version"] == "3.10"
    assert "int | None" in explicit_payload["transformed_code"]
    assert overridden_payload["target_version"] == "3.9"
    assert "Optional[int]" in overridden_payload["transformed_code"]


def test_run_gitignore_cli_tristate_overrides_project_config(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / "pyproject.toml").write_text(
        "[tool.typewriter]\nrespect-gitignore = true\n",
        encoding="utf-8",
    )
    ignored = project / "ignored.py"
    ignored.write_text("value: int = None\n", encoding="utf-8")
    (project / ".gitignore").write_text("ignored.py\n", encoding="utf-8")
    monkeypatch.chdir(project)

    inherited = runner.invoke(app, ["run", str(project), "--check", "--output-format", "json"])
    disabled = runner.invoke(
        app,
        ["run", str(project), "--check", "--no-respect-gitignore", "--output-format", "json"],
    )

    assert inherited.exit_code == 0
    assert json.loads(inherited.stdout)["processed_files"] == 0
    assert disabled.exit_code == 1
    assert json.loads(disabled.stdout)["changed_files"] == [str(ignored)]


def test_run_gitignore_true_flag_overrides_configured_false(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / "pyproject.toml").write_text(
        "[tool.typewriter]\nrespect-gitignore = false\n",
        encoding="utf-8",
    )
    ignored = project / "ignored.py"
    ignored.write_text("value: int = None\n", encoding="utf-8")
    (project / ".gitignore").write_text("ignored.py\n", encoding="utf-8")
    monkeypatch.chdir(project)

    inherited = runner.invoke(app, ["run", str(project), "--check", "--output-format", "json"])
    enabled = runner.invoke(
        app,
        ["run", str(project), "--check", "--respect-gitignore", "--output-format", "json"],
    )

    assert inherited.exit_code == 1
    assert json.loads(inherited.stdout)["changed_files"] == [str(ignored)]
    assert enabled.exit_code == 0
    assert json.loads(enabled.stdout)["processed_files"] == 0


def test_run_merges_config_and_cli_ignores_with_config_root_anchoring(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / "pyproject.toml").write_text(
        '[tool.typewriter]\nignore = ["src/generated/*", "shared.py"]\n',
        encoding="utf-8",
    )
    kept = project / "src" / "kept.py"
    kept.parent.mkdir()
    kept.write_text("kept: int = None\n", encoding="utf-8")
    config_ignored = project / "src" / "generated" / "ignored.py"
    config_ignored.parent.mkdir()
    config_ignored.write_text("ignored: int = None\n", encoding="utf-8")
    shared = project / "src" / "shared.py"
    shared.write_text("shared: int = None\n", encoding="utf-8")
    cli_ignored = project / "src" / "cli.py"
    cli_ignored.write_text("cli: int = None\n", encoding="utf-8")
    monkeypatch.chdir(project)

    result = runner.invoke(
        app,
        [
            "run",
            str(project / "src"),
            "--check",
            "--ignore",
            "src/generated/*",
            "--ignore",
            "cli.py",
            "--output-format",
            "json",
        ],
    )

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["processed_files"] == 1
    assert payload["changed_files"] == [str(kept)]


def test_run_config_errors_are_structured_json(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / "pyproject.toml").write_text(
        "[tool.typewriter]\nunknown = true\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(project)

    result = runner.invoke(
        app,
        ["run", "--code", "value: int = None\n", "--output-format", "json"],
    )

    assert result.exit_code == 2
    assert result.stdout == ""
    payload = json.loads(result.stderr)
    assert payload["type"] == "error"
    assert "Unknown tool.typewriter config key" in payload["error"]


def test_run_config_error_occurs_before_source_writes(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / "pyproject.toml").write_text(
        "[tool.typewriter]\nunknown = true\n",
        encoding="utf-8",
    )
    source = project / "example.py"
    original = b"value: int = None\n"
    source.write_bytes(original)
    monkeypatch.chdir(project)

    result = runner.invoke(app, ["run", str(source), "--output-format", "json"])

    assert result.exit_code == 2
    assert result.stdout == ""
    assert json.loads(result.stderr)["type"] == "error"
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("[tool.typewriter\n", "Could not parse config file"),
        ('[tool.typewriter]\ntarget-version = 310\n', "target-version must be a string"),
        ('[tool.typewriter]\ntarget-version = "abc"\n', "Invalid target version"),
        ('[tool.typewriter]\nrespect-gitignore = "yes"\n', "respect-gitignore must be a boolean"),
        ('[tool.typewriter]\nignore = "generated"\n', "ignore must be an array"),
    ],
)
def test_run_malformed_config_is_a_structured_json_error(tmp_path, content, message):
    config_path = tmp_path / "policy.toml"
    config_path.write_text(content, encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "run",
            "--code",
            "value: int = None\n",
            "--config",
            str(config_path),
            "--output-format",
            "json",
        ],
    )

    assert result.exit_code == 2
    assert result.stdout == ""
    payload = json.loads(result.stderr)
    assert payload["type"] == "error"
    assert message in payload["error"]


def test_run_explicit_missing_config_is_a_structured_json_error(tmp_path):
    missing = tmp_path / "missing.toml"

    result = runner.invoke(
        app,
        [
            "run",
            "--code",
            "value: int = None\n",
            "--config",
            str(missing),
            "--output-format",
            "json",
        ],
    )

    assert result.exit_code == 2
    assert result.stdout == ""
    payload = json.loads(result.stderr)
    assert payload["type"] == "error"
    assert "not a readable file" in payload["error"]


def test_run_explicit_config_directory_is_a_structured_json_error(tmp_path):
    config_directory = tmp_path / "policy"
    config_directory.mkdir()

    result = runner.invoke(
        app,
        [
            "run",
            "--code",
            "value: int = None\n",
            "--config",
            str(config_directory),
            "--output-format",
            "json",
        ],
    )

    assert result.exit_code == 2
    assert result.stdout == ""
    payload = json.loads(result.stderr)
    assert payload["type"] == "error"
    assert "not a readable file" in payload["error"]


def test_run_explicit_unreadable_config_is_a_structured_json_error(tmp_path, monkeypatch):
    config_path = tmp_path / "policy.toml"
    config_path.write_text('[tool.typewriter]\ntarget-version = "3.10"\n', encoding="utf-8")
    real_access = config_module.os.access

    def reject_config(path, mode):
        if Path(path) == config_path.resolve():
            return False
        return real_access(path, mode)

    monkeypatch.setattr(config_module.os, "access", reject_config)

    result = runner.invoke(
        app,
        [
            "run",
            "--code",
            "value: int = None\n",
            "--config",
            str(config_path),
            "--output-format",
            "json",
        ],
    )

    assert result.exit_code == 2
    assert result.stdout == ""
    payload = json.loads(result.stderr)
    assert payload["type"] == "error"
    assert "not a readable file" in payload["error"]


def test_run_text_error_is_emitted_for_click_exceptions(monkeypatch):
    def raise_click_exception(*args, **kwargs):
        raise click.ClickException("boom")

    monkeypatch.setattr(cli_module.TypewriterRunner, "process_code", raise_click_exception)

    result = runner.invoke(app, ["run", "--code", "var: int = None\n"])

    assert result.exit_code == 1
    assert "boom" in result.output


def test_run_json_error_is_emitted_for_unexpected_exceptions(monkeypatch):
    def raise_runtime_error(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(cli_module.TypewriterRunner, "process_code", raise_runtime_error)

    result = runner.invoke(app, ["run", "--code", "var: int = None\n", "--output-format", "json"])

    assert result.exit_code == 2
    payload = json.loads(result.stderr)
    assert payload == {"error": "boom", "type": "error"}


def test_run_text_error_is_emitted_for_unexpected_exceptions(monkeypatch):
    def raise_runtime_error(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(cli_module.TypewriterRunner, "process_code", raise_runtime_error)

    result = runner.invoke(app, ["run", "--code", "var: int = None\n"])

    assert result.exit_code == 2
    assert "Error: boom" in result.output


def test_cli_module_supports_python_dash_m_invocation():
    result = subprocess.run(
        [sys.executable, "-m", "typewriter.cli", "run", "--code", "var: int = None\n"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Optional[int]" in result.stdout

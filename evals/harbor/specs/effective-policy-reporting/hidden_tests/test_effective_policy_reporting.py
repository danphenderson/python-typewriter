import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from typewriter.cli import app

cli_runner = CliRunner()


def _write_policy(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"[tool.typewriter]\n{body}", encoding="utf-8")
    return path


def test_config_json_default_schema_is_exact(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = cli_runner.invoke(app, ["config", "--output-format", "json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "type": "config",
        "config_file": None,
        "values": {
            "target_version": {"value": None, "source": "default"},
            "respect_gitignore": {"value": False, "source": "default"},
            "ignore": [],
        },
    }


def test_json_reports_config_and_cli_sources_with_ordered_ignore_provenance(tmp_path, monkeypatch):
    project = tmp_path / "project"
    policy_path = _write_policy(
        project / "pyproject.toml",
        'target-version = "3.9"\nrespect-gitignore = true\nignore = ["generated", "shared"]\n',
    )
    invocation_cwd = project / "src" / "package"
    invocation_cwd.mkdir(parents=True)
    monkeypatch.chdir(invocation_cwd)

    result = cli_runner.invoke(
        app,
        [
            "config",
            "--target-version",
            "3.10",
            "--no-respect-gitignore",
            "--ignore",
            "shared",
            "--ignore",
            "cli-only",
            "--ignore",
            "cli-only",
            "--output-format",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "type": "config",
        "config_file": str(policy_path.resolve()),
        "values": {
            "target_version": {"value": "3.10", "source": "cli"},
            "respect_gitignore": {"value": False, "source": "cli"},
            "ignore": [
                {"pattern": "generated", "source": "config"},
                {"pattern": "shared", "source": "config"},
                {"pattern": "cli-only", "source": "cli"},
            ],
        },
    }


def test_text_and_json_reports_have_value_source_parity(tmp_path):
    policy_path = _write_policy(
        tmp_path / "policy.toml",
        'target-version = "3.10"\nrespect-gitignore = true\nignore = ["vendor"]\n',
    )
    options = [
        "--config",
        str(policy_path),
        "--no-respect-gitignore",
        "--ignore",
        "local-only",
    ]

    text_result = cli_runner.invoke(app, ["config", *options])
    json_result = cli_runner.invoke(app, ["config", *options, "--output-format", "json"])

    assert text_result.exit_code == json_result.exit_code == 0
    assert text_result.stdout == (
        f"Config file: {policy_path.resolve()}\n"
        "target_version: 3.10 (config)\n"
        "respect_gitignore: false (cli)\n"
        "ignore:\n"
        "  - vendor (config)\n"
        "  - local-only (cli)\n"
    )
    payload = json.loads(json_result.stdout)
    assert payload["values"] == {
        "target_version": {"value": "3.10", "source": "config"},
        "respect_gitignore": {"value": False, "source": "cli"},
        "ignore": [
            {"pattern": "vendor", "source": "config"},
            {"pattern": "local-only", "source": "cli"},
        ],
    }


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("[tool.typewriter\n", "Could not parse config file"),
        ("[tool.typewriter]\nunknown = true\n", "Unknown tool.typewriter config key"),
        ('[tool.typewriter]\ntarget-version = 310\n', "target-version must be a string"),
    ],
)
def test_config_errors_remain_structured(tmp_path, content, message):
    policy_path = tmp_path / "policy.toml"
    policy_path.write_text(content, encoding="utf-8")

    result = cli_runner.invoke(
        app,
        ["config", "--config", str(policy_path), "--output-format", "json"],
    )

    assert result.exit_code == 2
    assert result.stdout == ""
    payload = json.loads(result.stderr)
    assert payload["type"] == "error"
    assert message in payload["error"]


def test_missing_explicit_config_error_is_structured(tmp_path):
    result = cli_runner.invoke(
        app,
        [
            "config",
            "--config",
            str(tmp_path / "missing.toml"),
            "--output-format",
            "json",
        ],
    )

    assert result.exit_code == 2
    assert result.stdout == ""
    payload = json.loads(result.stderr)
    assert payload["type"] == "error"
    assert "not a readable file" in payload["error"]


def test_config_reporting_never_scans_transforms_or_writes_python(tmp_path, monkeypatch):
    transformable = tmp_path / "transformable.py"
    original = b"value: int = None\n"
    transformable.write_bytes(original)
    malformed = tmp_path / "malformed.py"
    malformed_original = b"def broken(:\n"
    malformed.write_bytes(malformed_original)
    monkeypatch.chdir(tmp_path)

    result = cli_runner.invoke(app, ["config", "--output-format", "json"])

    assert result.exit_code == 0
    assert transformable.read_bytes() == original
    assert malformed.read_bytes() == malformed_original


def test_run_json_does_not_leak_reporting_fields(tmp_path, monkeypatch):
    _write_policy(tmp_path / "pyproject.toml", 'target-version = "3.10"\n')
    monkeypatch.chdir(tmp_path)

    result = cli_runner.invoke(
        app,
        ["run", "--code", "value: int = None\n", "--output-format", "json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["type"] == "code"
    assert "int | None" in payload["transformed_code"]
    assert {"config", "config_file", "provenance", "values"}.isdisjoint(payload)

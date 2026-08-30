import json
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from typewriter import TypewriterRunner, load_typewriter_config
from typewriter.cli import app

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


cli_runner = CliRunner()


def _write_policy(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"[tool.typewriter]\n{body}", encoding="utf-8")
    return path


def test_cli_discovers_policy_and_explicit_config_bypasses_it(tmp_path, monkeypatch):
    project = tmp_path / "project"
    _write_policy(project / "pyproject.toml", 'target-version = "3.9"\n')
    invocation_cwd = project / "src" / "package"
    invocation_cwd.mkdir(parents=True)
    explicit = _write_policy(tmp_path / "policy.toml", 'target-version = "3.10"\n')
    monkeypatch.chdir(invocation_cwd)

    discovered = cli_runner.invoke(
        app,
        ["run", "--code", "value: int = None\n", "--output-format", "json"],
    )
    explicit_result = cli_runner.invoke(
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
    cli_override = cli_runner.invoke(
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

    assert discovered.exit_code == explicit_result.exit_code == cli_override.exit_code == 0
    discovered_payload = json.loads(discovered.stdout)
    explicit_payload = json.loads(explicit_result.stdout)
    override_payload = json.loads(cli_override.stdout)
    assert discovered_payload["target_version"] == "3.9"
    assert "Optional[int]" in discovered_payload["transformed_code"]
    assert explicit_payload["target_version"] == "3.10"
    assert "int | None" in explicit_payload["transformed_code"]
    assert override_payload["target_version"] == "3.9"
    assert "Optional[int]" in override_payload["transformed_code"]
    assert "config" not in explicit_payload
    assert "provenance" not in explicit_payload


def test_nearest_pyproject_is_the_boundary_even_without_a_policy(tmp_path, monkeypatch):
    project = tmp_path / "project"
    _write_policy(project / "pyproject.toml", 'target-version = "3.10"\n')
    nested = project / "packages" / "nested"
    nested.mkdir(parents=True)
    (project / "packages" / "pyproject.toml").write_text(
        "[project]\nname = \"boundary\"\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(nested)

    result = cli_runner.invoke(
        app,
        ["run", "--code", "value: int = None\n", "--output-format", "json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["target_version"] is None
    assert "Optional[int]" in payload["transformed_code"]


def test_gitignore_policy_has_true_false_and_cli_override_states(tmp_path, monkeypatch):
    project = tmp_path / "project"
    policy_path = _write_policy(project / "pyproject.toml", "respect-gitignore = true\n")
    source = project / "ignored.py"
    source.write_text("value: int = None\n", encoding="utf-8")
    (project / ".gitignore").write_text("ignored.py\n", encoding="utf-8")
    monkeypatch.chdir(project)

    configured_true = cli_runner.invoke(
        app,
        ["run", str(project), "--check", "--output-format", "json"],
    )
    forced_false = cli_runner.invoke(
        app,
        ["run", str(project), "--check", "--no-respect-gitignore", "--output-format", "json"],
    )
    policy_path.write_text("[tool.typewriter]\nrespect-gitignore = false\n", encoding="utf-8")
    configured_false = cli_runner.invoke(
        app,
        ["run", str(project), "--check", "--output-format", "json"],
    )
    forced_true = cli_runner.invoke(
        app,
        ["run", str(project), "--check", "--respect-gitignore", "--output-format", "json"],
    )

    assert configured_true.exit_code == forced_true.exit_code == 0
    assert json.loads(configured_true.stdout)["processed_files"] == 0
    assert json.loads(forced_true.stdout)["processed_files"] == 0
    assert forced_false.exit_code == configured_false.exit_code == 1
    assert json.loads(forced_false.stdout)["changed_files"] == [str(source)]
    assert json.loads(configured_false.stdout)["changed_files"] == [str(source)]


def test_config_ignores_are_rooted_for_recursive_and_explicit_inputs(tmp_path, monkeypatch):
    project = tmp_path / "project"
    _write_policy(
        project / "pyproject.toml",
        'ignore = ["src/generated/*", "explicit.py"]\n',
    )
    kept = project / "src" / "kept.py"
    kept.parent.mkdir(parents=True)
    kept.write_text("kept: int = None\n", encoding="utf-8")
    nested_ignored = project / "src" / "generated" / "ignored.py"
    nested_ignored.parent.mkdir()
    nested_ignored.write_text("ignored: int = None\n", encoding="utf-8")
    explicit_ignored = project / "explicit.py"
    explicit_ignored.write_text("ignored: int = None\n", encoding="utf-8")
    outside = tmp_path / "outside" / "explicit.py"
    outside.parent.mkdir()
    outside.write_text("outside: int = None\n", encoding="utf-8")
    monkeypatch.chdir(project)

    result = cli_runner.invoke(
        app,
        [
            "run",
            str(project / "src"),
            str(explicit_ignored),
            str(outside),
            "--check",
            "--ignore",
            "src/generated/*",
            "--output-format",
            "json",
        ],
    )

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["processed_files"] == 2
    assert payload["changed_files"] == [str(kept), str(outside)]
    assert nested_ignored.read_text(encoding="utf-8") == "ignored: int = None\n"
    assert explicit_ignored.read_text(encoding="utf-8") == "ignored: int = None\n"


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("[tool.typewriter]\nunknown = true\n", "Unknown tool.typewriter config key"),
        ("[tool.typewriter\n", "Could not parse config file"),
        ('[tool.typewriter]\ntarget-version = 310\n', "target-version must be a string"),
        ('[tool.typewriter]\nrespect-gitignore = "yes"\n', "respect-gitignore must be a boolean"),
        ('[tool.typewriter]\nignore = ["generated", 1]\n', "ignore must be an array"),
    ],
)
def test_config_errors_are_structured_and_occur_before_writes(tmp_path, content, message):
    config_path = tmp_path / "policy.toml"
    config_path.write_text(content, encoding="utf-8")
    source = tmp_path / "example.py"
    original = b"value: int = None\n"
    source.write_bytes(original)

    result = cli_runner.invoke(
        app,
        [
            "run",
            str(source),
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
    assert source.read_bytes() == original


@pytest.mark.parametrize("config_kind", ["missing", "directory"])
def test_invalid_explicit_config_paths_are_structured_and_do_not_write(tmp_path, config_kind):
    config_path = tmp_path / "policy.toml"
    if config_kind == "directory":
        config_path.mkdir()
    source = tmp_path / "example.py"
    original = b"value: int = None\n"
    source.write_bytes(original)

    result = cli_runner.invoke(
        app,
        [
            "run",
            str(source),
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
    assert "Config path is not a readable file" in payload["error"]
    assert source.read_bytes() == original


def test_python310_uses_runtime_tomli_policy_support(tmp_path):
    assert sys.version_info[:2] == (3, 10)
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    assert "tomli>=2.0; python_version < '3.11'" in pyproject["project"]["dependencies"]

    policy_path = _write_policy(tmp_path / "pyproject.toml", 'target-version = "3.10"\n')
    config = load_typewriter_config(config_path=policy_path)
    runner = TypewriterRunner.from_config(config)

    assert config.target_version == "3.10"
    assert "int | None" in runner.process_code("value: int = None\n").transformed_code

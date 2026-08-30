from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from typewriter import TypewriterConfig, TypewriterRunner, load_typewriter_config
from typewriter.config import ConfigSource, apply_cli_overrides

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10
    import tomli as tomllib


def _write_config(path: Path, table: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"[tool.typewriter]\n{table}", encoding="utf-8")
    return path


def test_typewriter_config_is_immutable_and_normalizes_sequences():
    config = TypewriterConfig(ignore=["generated"])  # type: ignore[arg-type]

    assert config.ignore == ("generated",)
    assert config.ignore_roots == (None,)
    with pytest.raises(FrozenInstanceError):
        config.target_version = "3.10"  # type: ignore[misc]


def test_loader_discovers_the_nearest_ancestor_pyproject(tmp_path):
    outer = tmp_path / "pyproject.toml"
    _write_config(outer, 'target-version = "3.10"\n')
    inner = tmp_path / "packages" / "demo" / "pyproject.toml"
    inner.parent.mkdir(parents=True)
    inner.write_text("[project]\nname = \"demo\"\n", encoding="utf-8")
    invocation_cwd = inner.parent / "src"
    invocation_cwd.mkdir()

    config = load_typewriter_config(cwd=invocation_cwd)

    assert config.target_version is None
    assert config.provenance.config_path == inner.resolve()


def test_explicit_config_bypasses_ancestor_discovery(tmp_path):
    project = tmp_path / "project"
    _write_config(project / "pyproject.toml", 'target-version = "3.9"\n')
    explicit = _write_config(tmp_path / "policy.toml", 'target-version = "3.10"\n')

    config = load_typewriter_config(config_path=Path("../policy.toml"), cwd=project)

    assert config.target_version == "3.10"
    assert config.provenance.config_path == explicit.resolve()


def test_cli_overrides_use_field_precedence_and_stable_ignore_deduplication(tmp_path):
    config_path = _write_config(
        tmp_path / "pyproject.toml",
        'target-version = "3.9"\nrespect-gitignore = true\nignore = ["generated", "shared", "generated"]\n',
    )
    loaded = load_typewriter_config(config_path=config_path)

    effective = apply_cli_overrides(
        loaded,
        target_version="3.10",
        respect_gitignore=False,
        ignore=["shared", "cli-only", "cli-only"],
    )

    assert effective.target_version == "3.10"
    assert effective.respect_gitignore is False
    assert effective.ignore == ("generated", "shared", "cli-only")
    assert effective.ignore_roots == (tmp_path.resolve(), tmp_path.resolve(), None)
    assert effective.provenance.target_version is ConfigSource.CLI
    assert effective.provenance.respect_gitignore is ConfigSource.CLI
    assert effective.provenance.ignore == (ConfigSource.CONFIG, ConfigSource.CONFIG, ConfigSource.CLI)


@pytest.mark.parametrize(
    ("table", "message"),
    [
        ('unknown = true\n', "Unknown tool.typewriter config key"),
        ('target-version = 310\n', "target-version must be a string"),
        ('target-version = "abc"\n', "Invalid target version"),
        ('respect-gitignore = "yes"\n', "respect-gitignore must be a boolean"),
        ('ignore = "generated"\n', "ignore must be an array"),
        ('ignore = ["generated", 1]\n', "ignore must be an array"),
    ],
)
def test_loader_rejects_unknown_keys_and_malformed_types(tmp_path, table, message):
    config_path = _write_config(tmp_path / "pyproject.toml", table)

    with pytest.raises(ValueError, match=message):
        load_typewriter_config(config_path=config_path)


def test_loader_rejects_malformed_toml(tmp_path):
    config_path = tmp_path / "pyproject.toml"
    config_path.write_text("[tool.typewriter\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Could not parse config file"):
        load_typewriter_config(config_path=config_path)


def test_loader_rejects_an_explicit_unreadable_config(tmp_path, monkeypatch):
    config_path = _write_config(tmp_path / "policy.toml", 'target-version = "3.10"\n')
    monkeypatch.setattr("typewriter.config.os.access", lambda path, mode: False)

    with pytest.raises(ValueError, match="not a readable file"):
        load_typewriter_config(config_path=config_path)


def test_runner_from_config_uses_target_version_and_config_rooted_ignores(tmp_path):
    project = tmp_path / "project"
    config_path = _write_config(
        project / "pyproject.toml",
        'target-version = "3.10"\nignore = ["src/vendor/*", "generated.py"]\n',
    )
    kept = project / "src" / "kept.py"
    kept.parent.mkdir(parents=True)
    kept.write_text("kept: int = None\n", encoding="utf-8")
    ignored_nested = project / "src" / "vendor" / "ignored.py"
    ignored_nested.parent.mkdir()
    ignored_nested.write_text("ignored: int = None\n", encoding="utf-8")
    ignored_explicit = project / "generated.py"
    ignored_explicit.write_text("ignored: int = None\n", encoding="utf-8")
    outside = tmp_path / "outside" / "generated.py"
    outside.parent.mkdir()
    outside.write_text("outside: int = None\n", encoding="utf-8")

    runner = TypewriterRunner.from_config(load_typewriter_config(config_path=config_path))
    result = runner.process_paths([project / "src", ignored_explicit, outside], write=False)
    explicit_nested_result = runner.process_paths([ignored_nested], write=False)

    assert result.processed_files == 2
    assert result.changed_files == [kept, outside]
    assert explicit_nested_result.processed_files == 0
    assert "int | None" in runner.process_code("value: int = None\n").transformed_code
    assert runner.config.provenance.config_path == config_path.resolve()


def test_python310_runtime_dependencies_include_tomli_marker():
    pyproject = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8"))

    assert "tomli>=2.0; python_version < '3.11'" in pyproject["project"]["dependencies"]

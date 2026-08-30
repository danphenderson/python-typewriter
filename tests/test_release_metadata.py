from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


EXPECTED_DESCRIPTION = "A LibCST codemod and CLI for normalizing None-related Python type annotations."


def test_source_metadata_is_prepared_for_unreleased_1_2_0():
    pyproject = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["version"] == "1.2.0"
    assert pyproject["project"]["description"] == EXPECTED_DESCRIPTION


def test_changelog_keeps_1_2_0_unreleased():
    changelog = (Path(__file__).parents[1] / "CHANGELOG.md").read_text(encoding="utf-8")

    assert "## [1.2.0] - Unreleased" in changelog
    assert "does not indicate that a tag" in changelog

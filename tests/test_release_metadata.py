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


def test_release_contract_uses_exact_main_head_and_oidc_trusted_publishing():
    root = Path(__file__).parents[1]
    release = (root / "docs" / "release.md").read_text(encoding="utf-8")
    workflow = (root / ".github" / "workflows" / "pypi_upload.yml").read_text(encoding="utf-8")
    normalized_release = " ".join(release.split())

    assert "exact `main` head" in normalized_release
    assert "protected branch head" not in normalized_release
    assert "id-token: write" in workflow
    assert "name: pypi" in workflow
    assert "url: https://pypi.org/p/py-typewriter-cli" in workflow
    assert "PYPI_TOKEN" not in workflow
    assert "password:" not in workflow

from pathlib import Path

import pytest

from evals.harbor.framework.generate import EvalBuildError
from tools import harbor_eval


def _write_spec(root: Path, slug: str) -> None:
    spec_dir = root / slug
    spec_dir.mkdir()
    (spec_dir / "spec.toml").write_text(f'slug = "{slug}"\n', encoding="utf-8")


def test_eval_slugs_fail_closed_when_no_specs_exist(tmp_path, monkeypatch):
    monkeypatch.setattr(harbor_eval, "SPECS_ROOT", tmp_path)

    with pytest.raises(EvalBuildError, match="^no Harbor eval specs were found$"):
        harbor_eval._eval_slugs()


def test_eval_slugs_are_sorted(tmp_path, monkeypatch):
    _write_spec(tmp_path, "zeta-task")
    _write_spec(tmp_path, "alpha-task")
    monkeypatch.setattr(harbor_eval, "SPECS_ROOT", tmp_path)

    assert harbor_eval._eval_slugs() == ("alpha-task", "zeta-task")


def test_verifier_receipts_use_the_persisted_verifier_tree():
    verifier = (Path(__file__).parents[1] / "evals" / "harbor" / "framework" / "verifier.sh").read_text(encoding="utf-8")

    assert "receipts=${verifier_logs}/receipts" in verifier
    for receipt in (
        '"${receipts}/${name}.log"',
        '"${receipts}/dist"',
        '"${receipts}/agent.patch"',
        '"${receipts}/git-status.txt"',
        '"${receipts}/gate-results.json"',
    ):
        assert receipt in verifier
    assert "artifacts=/logs/artifacts" not in verifier

    status_command = 'git -c safe.directory="${workspace}" status --short ' '>"${receipts}/git-status.txt"'
    add_intent_command = 'git -c safe.directory="${workspace}" add -N -- .'
    diff_command = 'git -c safe.directory="${workspace}" diff --binary ' '>"${receipts}/agent.patch"'
    assert verifier.index(status_command) < verifier.index(add_intent_command)
    assert verifier.index(add_intent_command) < verifier.index(diff_command)

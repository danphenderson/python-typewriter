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

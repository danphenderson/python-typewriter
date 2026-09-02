import json
import os
import stat
from pathlib import Path

import pytest
from typer.testing import CliRunner

from typewriter import TypewriterRunner
from typewriter.cli import app

cli_runner = CliRunner()


def test_cli_multi_path_check_is_ordered_deduplicated_and_deterministic(tmp_path):
    first = tmp_path / "b.py"
    first_original = "b: int = None\n"
    first.write_text(first_original, encoding="utf-8")
    second = tmp_path / "a.py"
    second_original = "a: str = None\n"
    second.write_text(second_original, encoding="utf-8")

    arguments = [
        "run",
        str(first),
        str(tmp_path),
        "--check",
        "--output-format",
        "json",
    ]
    first_run = cli_runner.invoke(app, arguments)
    second_run = cli_runner.invoke(app, arguments)

    assert first_run.exit_code == 1
    assert second_run.exit_code == 1
    assert first_run.stderr == second_run.stderr == ""
    assert first_run.stdout == second_run.stdout
    payload = json.loads(first_run.stdout)
    assert payload["type"] == "paths"
    assert payload["paths"] == [str(first), str(tmp_path)]
    assert payload["processed_files"] == 2
    assert payload["changed_count"] == 2
    assert payload["changed_files"] == [str(first), str(second)]
    assert set(payload["diffs"]) == {str(first), str(second)}
    assert first.read_text(encoding="utf-8") == first_original
    assert second.read_text(encoding="utf-8") == second_original


def test_cli_malformed_later_file_leaves_earlier_file_unchanged(tmp_path):
    first = tmp_path / "a.py"
    first_original = b"a: int = None\n"
    first.write_bytes(first_original)
    malformed = tmp_path / "b.py"
    malformed_original = b"def broken(:\n"
    malformed.write_bytes(malformed_original)

    result = cli_runner.invoke(
        app,
        ["run", str(first), str(malformed), "--output-format", "json"],
    )

    assert result.exit_code == 2
    assert result.stdout == ""
    assert json.loads(result.stderr)["type"] == "error"
    assert first.read_bytes() == first_original
    assert malformed.read_bytes() == malformed_original


def test_batch_files_receive_functionally_independent_contexts(tmp_path):
    rewritten = tmp_path / "a.py"
    rewritten.write_text(
        "from typing import Union\nvalue: Union[int, None]\n",
        encoding="utf-8",
    )
    independent = tmp_path / "b.py"
    independent_original = "from typing import Union\nvalue = 1\n"
    independent.write_text(independent_original, encoding="utf-8")

    result = TypewriterRunner().process_paths([tmp_path], write=False)

    assert result.processed_files == 2
    assert result.changed_files == [rewritten]
    assert independent.read_text(encoding="utf-8") == independent_original


def test_later_replace_failure_restores_prior_files_and_modes(tmp_path, monkeypatch):
    first = tmp_path / "a.py"
    first_original = b"a: int = None\n"
    first.write_bytes(first_original)
    first.chmod(0o751)
    second = tmp_path / "b.py"
    second_original = b"b: str = None\n"
    second.write_bytes(second_original)
    second.chmod(0o640)

    real_replace = os.replace
    failed = False

    def fail_second_destination(source, destination):
        nonlocal failed
        if not failed and Path(destination) == second.resolve():
            failed = True
            raise OSError("injected second replace failure")
        real_replace(source, destination)

    monkeypatch.setattr(os, "replace", fail_second_destination)

    with pytest.raises(RuntimeError):
        TypewriterRunner().process_paths([first, second])

    assert first.read_bytes() == first_original
    assert second.read_bytes() == second_original
    assert stat.S_IMODE(first.stat().st_mode) == 0o751
    assert stat.S_IMODE(second.stat().st_mode) == 0o640
    assert list(tmp_path.glob(".*.typewriter-*")) == []

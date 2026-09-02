import os
import stat

import pytest
from libcst import ParserSyntaxError

from typewriter import TypewriterRunner
from typewriter import runner as runner_module


def test_runner_process_code_uses_target_version_for_pep604_output():
    result = TypewriterRunner(target_version="3.10").process_code("value: int = None\n")

    assert result.changed is True
    assert "value: int | None = None" in result.transformed_code


def test_runner_process_code_accepts_compact_target_version_for_pep604_output():
    result = TypewriterRunner(target_version="py310").process_code("value: int = None\n")

    assert result.changed is True
    assert "value: int | None = None" in result.transformed_code


def test_runner_process_file_can_collect_diff_without_writing(tmp_path):
    file_path = tmp_path / "example.py"
    original_code = "value: int = None\n"
    file_path.write_text(original_code, encoding="utf-8")

    result = TypewriterRunner().process_file(file_path, write=False, include_diff=True)

    assert result.changed_files == [file_path]
    assert file_path.read_text(encoding="utf-8") == original_code
    assert result.diffs[file_path].startswith(f"--- {file_path}")


def test_runner_process_directory_uses_ignore_and_gitignore(tmp_path):
    kept = tmp_path / "pkg" / "keep.py"
    kept.parent.mkdir(parents=True)
    kept.write_text("value: int = None\n", encoding="utf-8")

    ignored_by_pattern = tmp_path / "generated" / "skip.py"
    ignored_by_pattern.parent.mkdir(parents=True)
    ignored_by_pattern.write_text("value: int = None\n", encoding="utf-8")

    ignored_by_git = tmp_path / "ignored.py"
    ignored_by_git.write_text("value: int = None\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("ignored.py\n", encoding="utf-8")

    result = TypewriterRunner(ignore=["generated"], respect_gitignore=True).process_directory(tmp_path, write=False)

    assert result.processed_files == 1
    assert result.changed_files == [kept]


def test_runner_rejects_conflicting_target_version_and_use_pep604():
    with pytest.raises(ValueError, match="must agree"):
        TypewriterRunner(target_version="3.9", use_pep604=True)


def test_runner_allows_explicit_use_pep604_without_target_version():
    result = TypewriterRunner(use_pep604=True).process_code("value: int = None\n")

    assert result.changed is True
    assert "value: int | None = None" in result.transformed_code


def test_runner_process_file_preserves_non_python_noop_contract(tmp_path):
    notes = tmp_path / "notes.txt"
    notes.write_text("not Python\n", encoding="utf-8")

    result = TypewriterRunner().process_file(notes)

    assert result.processed_files == 0
    assert result.changed_files == []


def test_runner_process_paths_preserves_input_order_and_deduplicates_overlaps(tmp_path):
    first = tmp_path / "b.py"
    first.write_text("b: int = None\n", encoding="utf-8")
    second = tmp_path / "a.py"
    second.write_text("a: int = None\n", encoding="utf-8")
    nested = tmp_path / "pkg" / "c.py"
    nested.parent.mkdir()
    nested.write_text("c: int = None\n", encoding="utf-8")

    result = TypewriterRunner().process_paths([first, tmp_path, nested], write=False)

    assert result.processed_files == 3
    assert result.changed_files == [first, second, nested]


def test_runner_process_paths_validates_all_inputs_before_writing(tmp_path):
    python_file = tmp_path / "example.py"
    original = b"value: int = None\n"
    python_file.write_bytes(original)
    unsupported_file = tmp_path / "notes.txt"
    unsupported_file.write_text("not Python\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Only '.py' files are supported"):
        TypewriterRunner().process_paths([python_file, unsupported_file])

    assert python_file.read_bytes() == original


def test_runner_process_paths_parses_every_file_before_writing(tmp_path):
    first = tmp_path / "a.py"
    original = b"value: int = None\n"
    first.write_bytes(original)
    malformed = tmp_path / "b.py"
    malformed.write_text("def broken(:\n", encoding="utf-8")

    with pytest.raises(ParserSyntaxError):
        TypewriterRunner().process_paths([first, malformed])

    assert first.read_bytes() == original


def test_runner_process_paths_reads_every_file_before_writing(tmp_path, monkeypatch):
    first = tmp_path / "a.py"
    original = b"value: int = None\n"
    first.write_bytes(original)
    unreadable = tmp_path / "b.py"
    unreadable.write_text("other: str = None\n", encoding="utf-8")
    real_read_bytes = type(unreadable).read_bytes

    def fail_later_read(path):
        if path == unreadable.resolve():
            raise PermissionError("injected unreadable file")
        return real_read_bytes(path)

    monkeypatch.setattr(type(unreadable), "read_bytes", fail_later_read)

    with pytest.raises(PermissionError, match="injected unreadable file"):
        TypewriterRunner().process_paths([first, unreadable])

    assert real_read_bytes(first) == original


def test_runner_process_paths_rejects_non_utf8_python_without_writing(tmp_path):
    first = tmp_path / "a.py"
    original = b"value: int = None\n"
    first.write_bytes(original)
    invalid = tmp_path / "b.py"
    invalid.write_bytes(b"\xff\xfe")

    with pytest.raises(ValueError, match="Python source is not valid UTF-8"):
        TypewriterRunner().process_paths([first, invalid])

    assert first.read_bytes() == original


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="platform does not provide POSIX FIFOs")
def test_runner_process_paths_rejects_non_regular_inputs(tmp_path):
    fifo = tmp_path / "source.py"
    os.mkfifo(fifo)

    with pytest.raises(ValueError, match="not a regular file or directory"):
        TypewriterRunner().process_paths([fifo])


def test_runner_process_paths_rejects_unreadable_inputs_before_reading(tmp_path, monkeypatch):
    source = tmp_path / "source.py"
    source.write_text("value: int = None\n", encoding="utf-8")
    real_access = runner_module.os.access

    def reject_source(path, mode):
        if path == source.resolve():
            return False
        return real_access(path, mode)

    monkeypatch.setattr(runner_module.os, "access", reject_source)

    with pytest.raises(ValueError, match="Path is not readable"):
        TypewriterRunner().process_paths([source])


def test_runner_process_paths_uses_a_fresh_context_per_file(tmp_path, monkeypatch):
    first = tmp_path / "a.py"
    first.write_text("a: int = None\n", encoding="utf-8")
    second = tmp_path / "b.py"
    second.write_text("b: str = None\n", encoding="utf-8")
    contexts = []
    real_process_code = runner_module.process_code

    def record_context(code, context=None):
        contexts.append(context)
        return real_process_code(code, context=context)

    monkeypatch.setattr(runner_module, "process_code", record_context)

    TypewriterRunner().process_paths([tmp_path], write=False)

    assert len(contexts) == 2
    assert contexts[0] is not contexts[1]


def test_runner_rechecks_rooted_ignores_after_directory_discovery(tmp_path, monkeypatch):
    source = tmp_path / "generated" / "source.py"
    source.parent.mkdir()
    source.write_text("value: int = None\n", encoding="utf-8")
    config = runner_module.TypewriterConfig(
        ignore=("generated/*",),
        ignore_roots=(tmp_path,),
        provenance=runner_module.ConfigProvenance(ignore=(runner_module.ConfigSource.CONFIG,)),
    )
    monkeypatch.setattr(runner_module, "_iter_python_files", lambda *args, **kwargs: [source])

    result = TypewriterRunner.from_config(config).process_paths([tmp_path], write=False)

    assert result.processed_files == 0
    assert result.changed_files == []


def test_runner_process_paths_restores_replaced_files_when_a_later_replace_fails(tmp_path, monkeypatch):
    first = tmp_path / "a.py"
    first_original = b"a: int = None\n"
    first.write_bytes(first_original)
    first.chmod(0o751)
    second = tmp_path / "b.py"
    second_original = b"b: str = None\n"
    second.write_bytes(second_original)
    second.chmod(0o640)

    real_replace = runner_module.os.replace
    failed = False

    def fail_second_replace(source, destination):
        nonlocal failed
        if not failed and destination == second.resolve():
            failed = True
            raise OSError("injected second replace failure")
        real_replace(source, destination)

    monkeypatch.setattr(runner_module.os, "replace", fail_second_replace)

    with pytest.raises(RuntimeError, match="all replaced files were restored"):
        TypewriterRunner().process_paths([first, second])

    assert first.read_bytes() == first_original
    assert second.read_bytes() == second_original
    assert stat.S_IMODE(first.stat().st_mode) == 0o751
    assert stat.S_IMODE(second.stat().st_mode) == 0o640
    assert list(tmp_path.glob(".*.typewriter-*")) == []


def test_temporary_write_cleans_up_when_mode_application_fails(tmp_path, monkeypatch):
    destination = tmp_path / "source.py"
    destination.write_bytes(b"original\n")

    def fail_chmod(path, mode):
        raise OSError("injected chmod failure")

    monkeypatch.setattr(runner_module.os, "chmod", fail_chmod)

    with pytest.raises(OSError, match="injected chmod failure"):
        runner_module._write_temporary_file(destination, b"replacement\n", 0o640)

    assert destination.read_bytes() == b"original\n"
    assert list(tmp_path.glob(".*.typewriter-*")) == []


def test_runner_detects_source_drift_before_staging_writes(tmp_path, monkeypatch):
    source = tmp_path / "source.py"
    original = b"value: int = None\n"
    source.write_bytes(original)
    real_read_bytes = type(source).read_bytes
    source_reads = 0

    def inject_drift(path):
        nonlocal source_reads
        if path == source.resolve():
            source_reads += 1
            if source_reads == 2:
                return b"externally changed\n"
        return real_read_bytes(path)

    monkeypatch.setattr(type(source), "read_bytes", inject_drift)

    with pytest.raises(RuntimeError, match="File changed while Typewriter was running"):
        TypewriterRunner().process_paths([source])

    assert real_read_bytes(source) == original
    assert list(tmp_path.glob(".*.typewriter-*")) == []


def test_runner_cleans_staged_transform_when_backup_creation_fails(tmp_path, monkeypatch):
    source = tmp_path / "source.py"
    original = b"value: int = None\n"
    source.write_bytes(original)
    real_write_temporary_file = runner_module._write_temporary_file
    calls = 0

    def fail_backup(destination, content, mode):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected backup failure")
        return real_write_temporary_file(destination, content, mode)

    monkeypatch.setattr(runner_module, "_write_temporary_file", fail_backup)

    with pytest.raises(RuntimeError, match="all replaced files were restored: injected backup failure"):
        TypewriterRunner().process_paths([source])

    assert source.read_bytes() == original
    assert list(tmp_path.glob(".*.typewriter-*")) == []


def test_runner_detects_source_drift_after_staging_but_before_replace(tmp_path, monkeypatch):
    source = tmp_path / "source.py"
    original = b"value: int = None\n"
    source.write_bytes(original)
    real_read_bytes = type(source).read_bytes
    source_reads = 0

    def inject_late_drift(path):
        nonlocal source_reads
        if path == source.resolve():
            source_reads += 1
            if source_reads == 3:
                return b"externally changed\n"
        return real_read_bytes(path)

    monkeypatch.setattr(type(source), "read_bytes", inject_late_drift)

    with pytest.raises(RuntimeError, match="File changed while Typewriter was running"):
        TypewriterRunner().process_paths([source])

    assert real_read_bytes(source) == original
    assert list(tmp_path.glob(".*.typewriter-*")) == []


def test_runner_preserves_backup_when_rollback_itself_fails(tmp_path, monkeypatch):
    first = tmp_path / "a.py"
    first_original = b"a: int = None\n"
    first.write_bytes(first_original)
    second = tmp_path / "b.py"
    second_original = b"b: str = None\n"
    second.write_bytes(second_original)
    real_replace = runner_module.os.replace
    replace_calls = 0

    def fail_write_and_rollback(source, destination):
        nonlocal replace_calls
        replace_calls += 1
        if replace_calls == 2:
            raise OSError("injected write failure")
        if replace_calls == 3:
            raise OSError("injected rollback failure")
        real_replace(source, destination)

    monkeypatch.setattr(runner_module.os, "replace", fail_write_and_rollback)

    with pytest.raises(RuntimeError, match="rollback also failed.*injected rollback failure"):
        TypewriterRunner().process_paths([first, second])

    assert first.read_bytes() != first_original
    assert second.read_bytes() == second_original
    preserved_backups = list(tmp_path.glob(".a.py.typewriter-*"))
    assert len(preserved_backups) == 1
    assert preserved_backups[0].read_bytes() == first_original


def test_runner_process_paths_apply_preserves_file_modes(tmp_path):
    first = tmp_path / "a.py"
    first.write_text("a: int = None\n", encoding="utf-8")
    first.chmod(0o751)
    second = tmp_path / "b.py"
    second.write_text("b: str = None\n", encoding="utf-8")
    second.chmod(0o640)

    result = TypewriterRunner().process_paths([first, second])

    assert result.changed_files == [first, second]
    assert "Optional[int]" in first.read_text(encoding="utf-8")
    assert "Optional[str]" in second.read_text(encoding="utf-8")
    assert stat.S_IMODE(first.stat().st_mode) == 0o751
    assert stat.S_IMODE(second.stat().st_mode) == 0o640


def test_runner_process_paths_applies_ignore_and_gitignore_to_explicit_files(tmp_path):
    ignored_by_pattern = tmp_path / "generated.py"
    ignored_by_pattern.write_text("generated: int = None\n", encoding="utf-8")
    ignored_by_git = tmp_path / "ignored.py"
    ignored_by_git.write_text("ignored: int = None\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("ignored.py\n", encoding="utf-8")

    pattern_result = TypewriterRunner(ignore=["generated.py"]).process_paths([ignored_by_pattern], write=False)
    gitignore_result = TypewriterRunner(respect_gitignore=True).process_paths([ignored_by_git], write=False)

    assert pattern_result.processed_files == 0
    assert pattern_result.changed_files == []
    assert gitignore_result.processed_files == 0
    assert gitignore_result.changed_files == []


def test_runner_process_paths_rejects_an_empty_path_sequence():
    with pytest.raises(ValueError, match="At least one path"):
        TypewriterRunner().process_paths([])

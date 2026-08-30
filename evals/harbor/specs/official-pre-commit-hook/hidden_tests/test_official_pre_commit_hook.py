import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml  # type: ignore[import-untyped]

WORKSPACE = Path.cwd().resolve()


def _run(*command: str, cwd: Path, check: bool = True, env=None):
    return subprocess.run(
        command,
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
        env=env,
    )


def _init_repository(path: Path) -> None:
    path.mkdir(parents=True)
    _run("git", "init", "-q", "-b", "main", cwd=path)
    _run("git", "config", "user.name", "Typewriter Hook Eval", cwd=path)
    _run("git", "config", "user.email", "hook-eval@typewriter.invalid", cwd=path)


def _commit_all(path: Path, message: str) -> None:
    _run("git", "add", "-A", cwd=path)
    _run("git", "commit", "-q", "-m", message, cwd=path)


def _build_hook_repository(path: Path) -> None:
    _init_repository(path)
    for filename in ("LICENSE", "README.md", "pyproject.toml", ".pre-commit-hooks.yaml"):
        shutil.copy2(WORKSPACE / filename, path / filename)
    shutil.copytree(WORKSPACE / "typewriter", path / "typewriter")
    _commit_all(path, "hook source")


def _run_try_repo(sample: Path, hook_repo: Path, pre_commit_home: Path):
    pre_commit = shutil.which("pre-commit")
    assert pre_commit is not None
    environment = os.environ.copy()
    environment["PRE_COMMIT_HOME"] = str(pre_commit_home)
    return _run(
        pre_commit,
        "try-repo",
        str(hook_repo),
        "typewriter",
        "--files",
        "selected_first.py",
        "selected_second.py",
        "interface.pyi",
        cwd=sample,
        check=False,
        env=environment,
    )


def test_manifest_uses_normal_serial_python_filename_passing():
    hooks = yaml.safe_load((WORKSPACE / ".pre-commit-hooks.yaml").read_text(encoding="utf-8"))

    assert len(hooks) == 1
    hook = hooks[0]
    assert hook["id"] == "typewriter"
    assert hook["name"] == "typewriter"
    assert hook["entry"] == "typewriter run"
    assert hook["language"] == "python"
    assert hook["types"] == ["python"]
    assert hook["exclude"] == r"\.pyi$"
    assert hook["require_serial"] is True
    assert "pass_filenames" not in hook


def test_fresh_hook_environment_is_forced_offline():
    assert os.environ["PIP_NO_INDEX"] == "1"
    assert os.environ["UV_OFFLINE"] == "1"
    wheelhouse = Path(os.environ["PIP_FIND_LINKS"])
    assert wheelhouse.is_dir()
    assert next(wheelhouse.glob("*.whl"), None) is not None


def test_try_repo_has_one_dedicated_non_matrix_ci_job():
    workflow_path = WORKSPACE / ".github" / "workflows" / "pre-commit-hook.yml"
    workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))

    assert set(workflow["jobs"]) == {"try-repo"}
    job = workflow["jobs"]["try-repo"]
    assert "strategy" not in job
    run_commands = [step["run"] for step in job["steps"] if "run" in step]
    assert any("tools/test_pre_commit_hook.sh" in command for command in run_commands)
    assert os.access(WORKSPACE / "tools" / "test_pre_commit_hook.sh", os.X_OK)


def test_try_repo_hook_is_atomic_scoped_policy_aware_and_repeatable(tmp_path):
    hook_repo = tmp_path / "hook-source"
    sample = tmp_path / "sample"
    pre_commit_home = tmp_path / "pre-commit-home"
    _build_hook_repository(hook_repo)
    _init_repository(sample)

    (sample / "pyproject.toml").write_text(
        '[tool.typewriter]\ntarget-version = "3.10"\n',
        encoding="utf-8",
    )
    (sample / "selected_first.py").write_bytes(b"first: int = None\n")
    (sample / "selected_second.py").write_bytes(b"def broken(:\n")
    (sample / "not_passed.py").write_bytes(b"unpassed: int = None\n")
    (sample / "interface.pyi").write_bytes(b"interface: int = None\n")
    _commit_all(sample, "initial sample")

    malformed_result = _run_try_repo(sample, hook_repo, pre_commit_home)

    assert malformed_result.returncode != 0
    assert "Syntax Error" in malformed_result.stdout + malformed_result.stderr
    assert (sample / "selected_first.py").read_bytes() == b"first: int = None\n"
    assert (sample / "selected_second.py").read_bytes() == b"def broken(:\n"

    (sample / "selected_second.py").write_bytes(b"second: int = None\n")
    _commit_all(sample, "repair sample")

    modification_result = _run_try_repo(sample, hook_repo, pre_commit_home)

    assert modification_result.returncode != 0
    assert "files were modified by this hook" in modification_result.stdout
    assert (sample / "selected_first.py").read_bytes() == b"first: int | None = None\n"
    assert (sample / "selected_second.py").read_bytes() == b"second: int | None = None\n"
    assert (sample / "not_passed.py").read_bytes() == b"unpassed: int = None\n"
    assert (sample / "interface.pyi").read_bytes() == b"interface: int = None\n"

    _run("git", "add", "selected_first.py", "selected_second.py", cwd=sample)
    clean_result = _run_try_repo(sample, hook_repo, pre_commit_home)

    assert clean_result.returncode == 0
    assert "Passed" in clean_result.stdout
    assert _run("git", "diff", "--quiet", cwd=sample, check=False).returncode == 0
    assert sys.version_info[:2] == (3, 10)

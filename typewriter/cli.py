import json
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import click
import typer

from typewriter.codemod import ProcessResult, ProcessStringResult
from typewriter.runner import TypewriterRunner, _parse_target_version

app = typer.Typer(no_args_is_help=True, help="Run python-typewriter codemods.")


class OutputFormat(str, Enum):
    TEXT = "text"
    JSON = "json"


def _serialize_process_result(
    result: ProcessResult,
    *,
    path: Path,
    check: bool,
    target_version: Optional[str],
    use_pep604: bool,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "type": "directory" if path.is_dir() else "file",
        "path": str(path),
        "check": check,
        "processed_files": result.processed_files,
        "changed_count": result.changed_count,
        "changed_files": [str(file_path) for file_path in result.changed_files],
        "target_version": target_version,
        "use_pep604": use_pep604,
    }
    if result.diffs:
        payload["diffs"] = {str(file_path): diff_text for file_path, diff_text in result.diffs.items()}
    return payload


def _serialize_string_result(
    result: ProcessStringResult,
    *,
    check: bool,
    target_version: Optional[str],
    use_pep604: bool,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "type": "code",
        "check": check,
        "changed": result.changed,
        "target_version": target_version,
        "use_pep604": use_pep604,
    }
    if check:
        if result.changed:
            import difflib

            diff_lines = difflib.unified_diff(
                result.original_code.splitlines(),
                result.transformed_code.splitlines(),
                fromfile="provided",
                tofile="provided",
                lineterm="",
            )
            payload["diff"] = "\n".join(diff_lines)
    else:
        payload["transformed_code"] = result.transformed_code
    return payload


def _emit_json(payload: Dict[str, Any], *, err: bool = False) -> None:
    typer.echo(json.dumps(payload, sort_keys=True), err=err)


@app.callback()
def main() -> None:
    """Typer app callback (CLI entrypoint)."""
    return


@app.command("run")
def run(
    path: Optional[Path] = typer.Argument(
        None,
        exists=True,
        file_okay=True,
        dir_okay=True,
        readable=True,
        resolve_path=True,
        help="A Python file or a directory to scan recursively for Python files.",
    ),
    code: Optional[str] = typer.Option(
        None,
        "--code",
        help="Python source code to transform in-memory (prints transformed code to stdout). Mutually exclusive with PATH.",
    ),
    check: bool = typer.Option(
        False,
        "--check",
        help="Show files that would change without writing updates.",
    ),
    target_version: Optional[str] = typer.Option(
        None,
        "--target-version",
        help="Target Python version (e.g. '3.10'). Python 3.10+ enables PEP 604 union syntax (T | None) instead of Optional[T].",
    ),
    ignore: Optional[List[str]] = typer.Option(
        None,
        "--ignore",
        help=(
            "Glob pattern for files or directories to skip. "
            "Matched against both the bare name and the path relative to the "
            "scanned directory. May be repeated."
        ),
    ),
    respect_gitignore: bool = typer.Option(
        False,
        "--respect-gitignore",
        help="Respect the nearest .gitignore at or above the scanned directory.",
    ),
    output_format: OutputFormat = typer.Option(
        OutputFormat.TEXT,
        "--output-format",
        help="Choose 'text' for human-readable output or 'json' for automation.",
    ),
) -> None:
    """Rewrite `None`-related type annotations in a file or directory.

    Provide either `PATH` (a Python file or directory) or `--code` (in-memory source).
    Use `--check` to preview changes and return a non-zero exit code when rewrites would occur.
    Use `--target-version 3.10` to emit PEP 604 union syntax (`T | None`).
    Use `--ignore` to skip additional files or directories by glob pattern.
    Use `--respect-gitignore` to also skip files ignored by Git.
    """
    try:
        use_pep604 = _parse_target_version(target_version)
        typewriter_runner = TypewriterRunner(
            target_version=target_version,
            ignore=ignore,
            respect_gitignore=respect_gitignore,
        )

        if code is not None:
            if path is not None:
                raise typer.BadParameter("Provide either PATH or --code, not both.")

            normalized_code = code.replace("\\n", "\n")
            string_result = typewriter_runner.process_code(normalized_code)
            if check:
                if output_format is OutputFormat.JSON:
                    _emit_json(
                        _serialize_string_result(
                            string_result,
                            check=True,
                            target_version=target_version,
                            use_pep604=use_pep604,
                        )
                    )
                    if string_result.changed:
                        raise typer.Exit(code=1)
                    return
                if string_result.changed:
                    typer.echo("Would transform provided code.")
                    # Provide a readable diff in check mode.
                    import difflib

                    diff_lines = difflib.unified_diff(
                        string_result.original_code.splitlines(),
                        string_result.transformed_code.splitlines(),
                        fromfile="provided",
                        tofile="provided",
                        lineterm="",
                    )
                    typer.echo("\n".join(diff_lines))
                    raise typer.Exit(code=1)
                typer.echo("No changes.")
                return

            if output_format is OutputFormat.JSON:
                _emit_json(
                    _serialize_string_result(
                        string_result,
                        check=False,
                        target_version=target_version,
                        use_pep604=use_pep604,
                    )
                )
            else:
                typer.echo(string_result.transformed_code, nl=False)
            return

        if path is None:
            if output_format is OutputFormat.JSON:
                _emit_json({"error": "either PATH or --code must be provided.", "type": "error"}, err=True)
            else:
                typer.echo("Error: either PATH or --code must be provided.", err=True)
            raise typer.Exit(code=2)

        if path.is_dir():
            result = typewriter_runner.process_directory(path, write=not check, include_diff=check)
        else:
            if path.suffix != ".py":
                raise typer.BadParameter("Only '.py' files are supported.")
            result = typewriter_runner.process_file(path, write=not check, include_diff=check)
    except typer.Exit:
        raise
    except ValueError as exc:
        if output_format is OutputFormat.JSON:
            _emit_json({"error": str(exc), "type": "error"}, err=True)
            raise typer.Exit(code=2)
        raise typer.BadParameter(str(exc))
    except click.ClickException as exc:
        if output_format is OutputFormat.JSON:
            _emit_json({"error": exc.format_message(), "type": "error"}, err=True)
            raise typer.Exit(code=exc.exit_code)
        raise
    except Exception as exc:
        if output_format is OutputFormat.JSON:
            _emit_json({"error": str(exc), "type": "error"}, err=True)
        else:
            typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=2)

    if output_format is OutputFormat.JSON:
        _emit_json(
            _serialize_process_result(
                result,
                path=path,
                check=check,
                target_version=target_version,
                use_pep604=use_pep604,
            )
        )
        if check and result.changed_count > 0:
            raise typer.Exit(code=1)
        return

    action = "Would transform" if check else "Transformed"
    for file_path in result.changed_files:
        typer.echo(f"{action} {file_path}")
        if check:
            diff_text = result.diffs.get(file_path)
            if diff_text:
                typer.echo(diff_text, nl=False)

    if check:
        if result.changed_count > 0:
            typer.echo(f"{result.changed_count} file(s) would be transformed.")
            raise typer.Exit(code=1)
        typer.echo("No files need changes.")
        return

    typer.echo(f"Transformed {result.changed_count} file(s).")


if __name__ == "__main__":
    app()

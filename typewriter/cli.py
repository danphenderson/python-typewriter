from pathlib import Path
from typing import List, Optional

import click
import typer

from typewriter.codemod import CodemodContext, process_code, process_file, process_files_in_directory

app = typer.Typer(no_args_is_help=True, help="Run python-typewriter codemods.")


def _parse_target_version(value: Optional[str]) -> Optional[bool]:
    """Return *True* when *value* indicates Python 3.10+ (PEP 604 unions)."""
    if value is None:
        return False
    try:
        parts = value.replace("py", "").split(".")
        if len(parts) == 1 and len(parts[0]) >= 3:
            # e.g. "py310" → (3, 10)
            major = int(parts[0][0])
            minor = int(parts[0][1:])
        else:
            major, minor = int(parts[0]), int(parts[1])
        return (major, minor) >= (3, 10)
    except (ValueError, IndexError):
        raise typer.BadParameter(f"Invalid target version: {value!r}. Use e.g. '3.10' or '3.9'.")


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
        help=(
            "Target Python version (e.g. '3.10'). "
            "Python 3.10+ enables PEP 604 union syntax (T | None) instead of Optional[T]."
        ),
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
) -> None:
    """Rewrite `None`-related type annotations in a file or directory.

    Provide either `PATH` (a Python file or directory) or `--code` (in-memory source).
    Use `--check` to preview changes and return a non-zero exit code when rewrites would occur.
    Use `--target-version 3.10` to emit PEP 604 union syntax (`T | None`).
    Use `--ignore` to skip additional files or directories by glob pattern.
    """
    try:
        use_pep604 = _parse_target_version(target_version)
        context = CodemodContext(use_pep604=use_pep604)
        extra_ignore_patterns = list(ignore) if ignore else None

        if code is not None:
            if path is not None:
                raise typer.BadParameter("Provide either PATH or --code, not both.")

            normalized_code = code.replace("\\n", "\n")
            string_result = process_code(normalized_code, context=context)
            if check:
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

            typer.echo(string_result.transformed_code, nl=False)
            return

        if path is None:
            typer.echo("Error: either PATH or --code must be provided.", err=True)
            raise typer.Exit(code=2)

        if path.is_dir():
            result = process_files_in_directory(
                path,
                write=not check,
                include_diff=check,
                context=context,
                extra_ignore_patterns=extra_ignore_patterns,
            )
        else:
            if path.suffix != ".py":
                raise typer.BadParameter("Only '.py' files are supported.")
            result = process_file(path, write=not check, include_diff=check, context=context)
    except (typer.Exit, click.ClickException):
        raise
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=2)

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

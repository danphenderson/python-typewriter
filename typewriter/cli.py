from pathlib import Path
from typing import Optional

import click
import typer

from typewriter.codemod import process_code, process_file, process_files_in_directory

app = typer.Typer(no_args_is_help=True, help="Run python-typewriter codemods.")


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
) -> None:
    """Rewrite `None`-related type annotations in a file or directory.

    Provide either `PATH` (a Python file or directory) or `--code` (in-memory source).
    Use `--check` to preview changes and return a non-zero exit code when rewrites would occur.
    """
    try:
        if code is not None:
            if path is not None:
                raise typer.BadParameter("Provide either PATH or --code, not both.")

            normalized_code = code.replace("\\n", "\n")
            string_result = process_code(normalized_code)
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
            result = process_files_in_directory(path, write=not check, include_diff=check)
        else:
            if path.suffix != ".py":
                raise typer.BadParameter("Only '.py' files are supported.")
            result = process_file(path, write=not check, include_diff=check)
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

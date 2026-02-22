from pathlib import Path

import typer

from typewriter.codemod import process_files_in_directory

app = typer.Typer(no_args_is_help=True, help="Run python-typewriter codemods.")


@app.callback()
def main() -> None:
    """CLI entrypoint."""
    return


@app.command("run")
def run(
    path: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
        help="Directory to scan recursively for Python files.",
    ),
    check: bool = typer.Option(
        False,
        "--check",
        help="Show files that would change without writing updates.",
    ),
) -> None:
    try:
        result = process_files_in_directory(path, write=not check)
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=2)

    action = "Would transform" if check else "Transformed"
    for file_path in result.changed_files:
        typer.echo(f"{action} {file_path}")

    if check:
        if result.changed_count > 0:
            typer.echo(f"{result.changed_count} file(s) would be transformed.")
            raise typer.Exit(code=1)
        typer.echo("No files need changes.")
        return

    typer.echo(f"Transformed {result.changed_count} file(s).")


if __name__ == "__main__":
    app()

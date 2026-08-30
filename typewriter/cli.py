import json
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import click
import typer

from typewriter.codemod import ProcessResult, ProcessStringResult
from typewriter.config import (
    TypewriterConfig,
    apply_cli_overrides,
    load_typewriter_config,
)
from typewriter.runner import TypewriterRunner

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


def _serialize_paths_result(
    result: ProcessResult,
    *,
    paths: List[Path],
    check: bool,
    target_version: Optional[str],
    use_pep604: bool,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "type": "paths",
        "paths": [str(path) for path in paths],
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


def _serialize_config(config: TypewriterConfig) -> Dict[str, Any]:
    return {
        "type": "config",
        "config_file": (str(config.provenance.config_path) if config.provenance.config_path is not None else None),
        "values": {
            "target_version": {
                "value": config.target_version,
                "source": config.provenance.target_version.value,
            },
            "respect_gitignore": {
                "value": config.respect_gitignore,
                "source": config.provenance.respect_gitignore.value,
            },
            "ignore": [{"pattern": pattern, "source": source.value} for pattern, source in zip(config.ignore, config.provenance.ignore)],
        },
    }


def _emit_config_text(config: TypewriterConfig) -> None:
    config_file = str(config.provenance.config_path) if config.provenance.config_path is not None else "(none)"
    target_version = config.target_version if config.target_version is not None else "(none)"
    typer.echo(f"Config file: {config_file}")
    typer.echo(f"target_version: {target_version} ({config.provenance.target_version.value})")
    typer.echo("respect_gitignore: " f"{str(config.respect_gitignore).lower()} ({config.provenance.respect_gitignore.value})")
    if not config.ignore:
        typer.echo("ignore: (none)")
        return
    typer.echo("ignore:")
    for pattern, source in zip(config.ignore, config.provenance.ignore):
        typer.echo(f"  - {pattern} ({source.value})")


@app.callback()
def main() -> None:
    """Typer app callback (CLI entrypoint)."""
    return


@app.command("config")
def config_command(
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        exists=False,
        file_okay=True,
        dir_okay=True,
        readable=False,
        resolve_path=True,
        help="Use this TOML file instead of discovering the nearest pyproject.toml.",
    ),
    target_version: Optional[str] = typer.Option(
        None,
        "--target-version",
        help="Override the configured target Python version.",
    ),
    ignore: Optional[List[str]] = typer.Option(
        None,
        "--ignore",
        help="Append a glob pattern to the effective ignore policy. May be repeated.",
    ),
    respect_gitignore: Optional[bool] = typer.Option(
        None,
        "--respect-gitignore/--no-respect-gitignore",
        help="Override whether the nearest .gitignore is respected.",
    ),
    output_format: OutputFormat = typer.Option(
        OutputFormat.TEXT,
        "--output-format",
        help="Choose 'text' for human-readable output or 'json' for automation.",
    ),
) -> None:
    """Show the effective project policy and where each value came from."""
    try:
        effective_config = apply_cli_overrides(
            load_typewriter_config(config_path=config),
            target_version=target_version,
            ignore=ignore,
            respect_gitignore=respect_gitignore,
        )
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
        _emit_json(_serialize_config(effective_config))
        return
    _emit_config_text(effective_config)


@app.command("run")
def run(
    paths: Optional[List[Path]] = typer.Argument(
        None,
        exists=False,
        file_okay=True,
        dir_okay=True,
        readable=False,
        resolve_path=True,
        help="One or more Python files or directories to process in order.",
    ),
    code: Optional[str] = typer.Option(
        None,
        "--code",
        help="Python source code to transform in-memory (prints transformed code to stdout). Mutually exclusive with PATHS.",
    ),
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        exists=False,
        file_okay=True,
        dir_okay=True,
        readable=False,
        resolve_path=True,
        help="Use this TOML file instead of discovering the nearest pyproject.toml.",
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
    respect_gitignore: Optional[bool] = typer.Option(
        None,
        "--respect-gitignore/--no-respect-gitignore",
        help="Override whether the nearest .gitignore is respected.",
    ),
    output_format: OutputFormat = typer.Option(
        OutputFormat.TEXT,
        "--output-format",
        help="Choose 'text' for human-readable output or 'json' for automation.",
    ),
) -> None:
    """Rewrite `None`-related type annotations in files and directories.

    Provide either one or more `PATHS` or `--code` (in-memory source).
    Use `--check` to preview changes and return a non-zero exit code when rewrites would occur.
    Use `--target-version 3.10` to emit PEP 604 union syntax (`T | None`).
    Use `--ignore` to skip additional files or directories by glob pattern.
    Use `--respect-gitignore` to also skip files ignored by Git.
    Project defaults are discovered from the nearest ancestor `pyproject.toml`.
    """
    try:
        loaded_config = load_typewriter_config(config_path=config)
        effective_config = apply_cli_overrides(
            loaded_config,
            target_version=target_version,
            ignore=ignore,
            respect_gitignore=respect_gitignore,
        )
        typewriter_runner = TypewriterRunner.from_config(effective_config)
        effective_target_version = effective_config.target_version
        use_pep604 = typewriter_runner.use_pep604

        if code is not None:
            if paths:
                raise typer.BadParameter("Provide either PATH or --code, not both.")

            normalized_code = code.replace("\\n", "\n")
            string_result = typewriter_runner.process_code(normalized_code)
            if check:
                if output_format is OutputFormat.JSON:
                    _emit_json(
                        _serialize_string_result(
                            string_result,
                            check=True,
                            target_version=effective_target_version,
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
                        target_version=effective_target_version,
                        use_pep604=use_pep604,
                    )
                )
            else:
                typer.echo(string_result.transformed_code, nl=False)
            return

        if not paths:
            if output_format is OutputFormat.JSON:
                _emit_json({"error": "either PATH or --code must be provided.", "type": "error"}, err=True)
            else:
                typer.echo("Error: either PATH or --code must be provided.", err=True)
            raise typer.Exit(code=2)

        result = typewriter_runner.process_paths(paths, write=not check, include_diff=check)
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
        if len(paths) == 1:
            _emit_json(
                _serialize_process_result(
                    result,
                    path=paths[0],
                    check=check,
                    target_version=effective_target_version,
                    use_pep604=use_pep604,
                )
            )
        else:
            _emit_json(
                _serialize_paths_result(
                    result,
                    paths=paths,
                    check=check,
                    target_version=effective_target_version,
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

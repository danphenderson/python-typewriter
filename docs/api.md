# API reference

Typewriter is primarily a CLI-first tool, so the hosted documentation keeps a **lightweight manual API reference** instead of generating a large autodoc section from every module docstring.

That is a deliberate choice for this MkDocs migration: it keeps the docs easier to maintain while still documenting the public entry points that are useful for integrators.

## CLI entry point

The supported command is:

```bash
typewriter run [PATHS]... [OPTIONS]
```

The most important options are:

- `--check` to preview diffs and exit non-zero when rewrites are needed
- `--code` to transform an in-memory string instead of reading from disk
- `--config` to use an explicit TOML policy instead of ancestor discovery
- `--target-version` to choose `Optional[...]` output or PEP 604 unions
- `--ignore` for repeatable skip patterns
- `--respect-gitignore` to honor the nearest `.gitignore`
- `--output-format json` for automation-friendly output

Use `typewriter config` with the same policy options to inspect resolved values
and their `default`, `config`, or `cli` sources without scanning source code.
`--output-format json` emits `type`, `config_file`, and `values` for maintenance
automation. Policy parse and validation failures use the same exit-code `2`
error behavior as `typewriter run`.

## Programmatic runner

For Python integrations, use `typewriter.TypewriterRunner`:

```python
from pathlib import Path

from typewriter import TypewriterRunner, load_typewriter_config

config = load_typewriter_config(
    config_path=Path("pyproject.toml"),
)
runner = TypewriterRunner.from_config(config)

code_result = runner.process_code("value: int = None\n")
file_result = runner.process_file(Path("example.py"), write=False, include_diff=True)
directory_result = runner.process_directory(Path("."), write=False, include_diff=True)
batch_result = runner.process_paths(
    [Path("src"), Path("tests/test_cli.py")],
    write=False,
    include_diff=True,
)
```

`process_code` returns a structured string result with the original and transformed source.

`process_file`, `process_directory`, and `process_paths` return structured results describing processed paths, changed paths, and optional unified diffs. `process_paths` preserves explicit input order, deduplicates overlaps by resolved path, and completes all reads and transformations before atomically replacing changed files.

`load_typewriter_config` returns an immutable `TypewriterConfig`. Without an
explicit path it discovers the nearest ancestor `pyproject.toml` from the
invocation directory. The runner retains the effective config and its internal
source provenance for integrations, while processing uses config-rooted ignore
patterns consistently for explicit files and recursive scans.

## Lower-level codemod module

`typewriter.codemod` remains available for callers that need lower-level transformation helpers or want to manage codemod context directly, but most integrations should prefer `TypewriterRunner` because it mirrors the CLI options cleanly.

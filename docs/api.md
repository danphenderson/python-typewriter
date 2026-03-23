# API reference

Typewriter is primarily a CLI-first tool, so the hosted documentation keeps a **lightweight manual API reference** instead of generating a large autodoc section from every module docstring.

That is a deliberate choice for this MkDocs migration: it keeps the docs easier to maintain while still documenting the public entry points that are useful for integrators.

## CLI entry point

The supported command is:

```bash
typewriter run [PATH] [OPTIONS]
```

The most important options are:

- `--check` to preview diffs and exit non-zero when rewrites are needed
- `--code` to transform an in-memory string instead of reading from disk
- `--target-version` to choose `Optional[...]` output or PEP 604 unions
- `--ignore` for repeatable skip patterns
- `--respect-gitignore` to honor the nearest `.gitignore`
- `--output-format json` for automation-friendly output

## Programmatic runner

For Python integrations, use `typewriter.TypewriterRunner`:

```python
from pathlib import Path

from typewriter import TypewriterRunner

runner = TypewriterRunner(
    target_version="3.10",
    ignore=["generated"],
    respect_gitignore=True,
)

code_result = runner.process_code("value: int = None\n")
file_result = runner.process_file(Path("example.py"), write=False, include_diff=True)
directory_result = runner.process_directory(Path("."), write=False, include_diff=True)
```

`process_code` returns a structured string result with the original and transformed source.

`process_file` and `process_directory` return structured results describing processed paths, changed paths, and optional unified diffs.

## Lower-level codemod module

`typewriter.codemod` remains available for callers that need lower-level transformation helpers or want to manage codemod context directly, but most integrations should prefer `TypewriterRunner` because it mirrors the CLI options cleanly.

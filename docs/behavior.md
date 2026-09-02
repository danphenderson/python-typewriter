# Behavior

## Choosing a target Python version

By default, Typewriter emits `Optional[...]` so output remains compatible with Python 3.9 codebases.

Use `--target-version 3.10` or any newer version when your project prefers PEP 604 syntax and you want Typewriter to normalize existing `Optional[...]` and `Union[...]` annotations to `T | None` as well:

```bash
typewriter run path/to/example.py --target-version 3.10
```

## Ignore rules and `.gitignore`

Use `--ignore` for project-specific exclusions that should always remain outside a run:

```bash
typewriter run myproject --ignore "test_*" --ignore "generated"
```

Patterns are matched against both the bare file or directory name and the relative path from the scanned root.

Use `--respect-gitignore` when you also want Typewriter to honor the nearest `.gitignore` at or above the scanned directory:

```bash
typewriter run myproject --respect-gitignore
```

The built-in skip set stays active regardless of custom patterns.

## Project policy and precedence

The nearest ancestor `pyproject.toml` from the invocation directory can define:

```toml
[tool.typewriter]
target-version = "3.10"
respect-gitignore = true
ignore = ["generated", "src/vendor/*"]
```

An explicit `--config` path bypasses ancestor discovery. Unknown keys, malformed
values, invalid TOML, and unreadable explicit config files are errors. Target
version and `.gitignore` behavior use CLI-over-config-over-default precedence;
the paired `--respect-gitignore` and `--no-respect-gitignore` flags provide an
explicit boolean override. Configured ignores come first, repeatable CLI ignores
are appended with stable deduplication, and configured patterns remain anchored
to the config directory rather than whichever input directory is scanned.

## Batch processing

One invocation can contain multiple files and directories. Typewriter validates all
explicit inputs first, preserves their order, sorts each directory traversal, and
deduplicates overlaps by resolved path. Every selected file gets an independent codemod
context, and apply mode finishes all reads and transformations before it replaces any
file. If a later replacement fails, earlier replacements are restored.

## Additional details

- Qualified typing references are preserved.
- Import statements are added as needed and deduplicated.
- Unused `Union` and `Optional` imports are cleaned up after rewriting.
- `x: Any = None` stays unchanged.

## Scope and non-goals

Typewriter intentionally focuses on one narrow codemod: normalizing `None`-related type annotations.

It does not try to:

- perform broad typing cleanup beyond the current rewrite rules
- rewrite docstrings or narrative documentation
- infer business meaning beyond syntax-driven transformations
- replace formatters, linters, or static-analysis tools

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

# Typewriter

Typewriter is a [Typer](https://typer.tiangolo.com/) CLI built on [LibCST](https://libcst.readthedocs.io/en/latest/) that normalizes `None`-related type annotations in Python source code.

The hosted docs on Read the Docs publish the default branch as **latest** and tagged releases as **stable/versioned** documentation, so the docs stay aligned with project releases without committing generated HTML to the repository.

## What Typewriter rewrites

Default mode keeps output Python 3.9-compatible:

```python
Union[T, None] -> Optional[T]
Union[T1, T2, None] -> Optional[Union[T1, T2]]
x: T = None -> x: Optional[T] = None
def f(x: T = None) -> def f(x: Optional[T] = None)
```

With `--target-version 3.10` or newer, Typewriter emits PEP 604 unions instead:

```python
Union[T, None] -> T | None
Optional[T] -> T | None
Union[T1, T2] -> T1 | T2
Union[T1, T2, None] -> T1 | T2 | None
x: T = None -> x: T | None = None
def f(x: T = None) -> def f(x: T | None = None)
```

## Highlights

- Adds, preserves, and cleans up typing imports as needed.
- Leaves `Any = None` annotations unchanged.
- Supports check-only mode for CI and apply mode for local codemods.
- Can respect both custom `--ignore` patterns and the nearest `.gitignore`.

## Read next

- [Getting started](getting-started.md) for installation and a first run
- [Usage](usage.md) for CLI, CI, and pre-commit examples
- [Behavior](behavior.md) for target-version and ignore semantics
- [Motivation](motivation.md) for the Playwright context behind the tool
- [API reference](api.md) for the intentionally lightweight public API docs

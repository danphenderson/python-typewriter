# Typewriter

[![Documentation Status](https://readthedocs.org/projects/python-typewriter/badge/?style=flat)](docs/index.md)
[![GitHub Actions Build Status](https://github.com/danphenderson/python-typewriter/actions/workflows/CI.yml/badge.svg)](https://github.com/danphenderson/python-typewriter/actions)
[![Coveralls](https://coveralls.io/repos/github/danphenderson/python-typewriter/badge.svg?branch=main)](https://coveralls.io/github/danphenderson/python-typewriter?branch=main)
[![Codecov](https://codecov.io/gh/danphenderson/python-typewriter/graph/badge.svg?branch=main)](https://codecov.io/gh/danphenderson/python-typewriter)
[![PyPI Package latest release](https://img.shields.io/pypi/v/py-typewriter-cli.svg)](https://pypi.org/project/py-typewriter-cli)
[![PyPI Wheel](https://img.shields.io/pypi/wheel/py-typewriter-cli.svg)](https://pypi.org/project/py-typewriter-cli)
[![Supported versions](https://img.shields.io/pypi/pyversions/py-typewriter-cli.svg)](https://pypi.org/project/py-typewriter-cli)
[![Supported implementations](https://img.shields.io/pypi/implementation/py-typewriter-cli.svg)](https://pypi.org/project/py-typewriter-cli)

Full documentation is available in the repository at [docs/index.md](docs/index.md).

## Overview

Typewriter is a Python [Typer](https://typer.tiangolo.com/) CLI built on [LibCST](https://libcst.readthedocs.io/en/latest/) that normalizes `None`-related type annotations in Python source code. It can be used to automatically rewrite type annotations to use `Optional` instead of `Union` when `None` is involved, and to ensure `Optional` is used for variable and parameter annotations when the default value is `None`.

What it rewrites (default mode, Python 3.9-compatible):
```python
Union[T, None] -> Optional[T]

Union[T1, T2, None] -> Optional[Union[T1, T2]]

x: T = None -> x: Optional[T] = None

def f(x: T = None) -> def f(x: Optional[T] = None)
```

With `--target-version 3.10` (PEP 604 mode):
```python
Union[T, None] -> T | None

Optional[T] -> T | None

Union[T1, T2] -> T1 | T2

Union[T1, T2, None] -> T1 | T2 | None

x: T = None -> x: T | None = None

def f(x: T = None) -> def f(x: T | None = None)
```

Additional notes:
- `x: Any = None` stays unchanged.
- Qualified typing references are preserved.
- Import statements are added as needed and deduplicated.
- Unused `Union` and `Optional` imports are cleaned up after rewriting.

## Quick Start

### Installation for PyPI
```bash
pip install py-typewriter-cli # Python 3.10-3.13
```

### Usage
Typewriter exposes one subcommand: `run`.
Consider `example.py` with contents:
```python
from typing import Any, Union

count: int = None
name: str = None
payload: Any = None

def greet(user_id: int = None, msg: Union[str, None] = None) -> Union[str, None]:
    if user_id is None:
        return None
    return f"hello-{user_id}\n{msg}"
```
To see what would change without writing files, run with `--check`:
```bash
typewriter run path/to/example.py --check
```
```text
Would transform path/to/example.py
--- path/to/example.py
+++ path/to/example.py
@@ ...
-old line
+new line
```
In ``--check`` mode, Typewriter prints a unified diff of its proposed changes to stdout and provides the following Exit codes:
- `0`: no changes needed
- `1`: changes would be made
- `2`: error

To apply the detected changes, run without `--check`:
```bash
typewriter run path/to/example.py
```

### Additional features:
To run recursively on all `*.py` files in a directory:
```bash
typewriter run examples # Non-`.py` files are rejected.
```
To transform an in-memory string and return the result to stdout, use `--code`:
```bash
typewriter run --code "var: int = None\\n"
```

#### PEP 604 mode
To emit `T | None` style unions instead of `Optional[T]`, pass `--target-version 3.10` (or any Python 3.10+ version):
```bash
typewriter run path/to/example.py --target-version 3.10
```
In this mode, existing `Optional[...]` and `Union[...]` annotations are normalized to
PEP 604 syntax too.
The default output remains Python 3.9-compatible (`Optional[T]`).

#### Skip configuration
To skip additional files or directories by glob pattern, use `--ignore` (repeatable):
```bash
typewriter run myproject --ignore "test_*" --ignore "generated"
```
Patterns are matched against both the bare file/directory name **and** the relative
path from the scanned root.  The built-in skip set (`.git`, `.venv`, `__pycache__`,
`build`, `dist`, etc.) is always active regardless of extra patterns.

To also honor the nearest `.gitignore` at or above the scanned directory:
```bash
typewriter run myproject --respect-gitignore
```

#### Additional Details:
- `PATH` and `--code` are mutually exclusive.
- Literal `\\n` sequences in `--code` input are interpreted as newlines.
- When a directory is provided as `PATH`, Typewriter will ignore non-`.py` files and
common non-source subdirectories such as `.git`, `.venv`, `venv`, `__pycache__`, `build`, and `dist`.
- PEP 604 syntax (`T | None`) is opt-in via `--target-version 3.10` and is not used by default.

## Recommended workflows

### Using Typewriter in CI

Use `--check` in CI when you want Typewriter to fail the job if a pull request still
contains `None`-related typing rewrites that should be applied:

```bash
typewriter run . --check --respect-gitignore
```

Exit codes in CI-friendly `--check` mode are:

- `0`: the scanned files are already normalized
- `1`: Typewriter found rewrites it would apply
- `2`: Typewriter hit an error

For bots and automation, switch to machine-readable output:

```bash
typewriter run . --check --respect-gitignore --output-format json
```

A minimal GitHub Actions step looks like this:

```yaml
- name: Check None-related typing annotations
  run: typewriter run . --check --respect-gitignore
```

### Using Typewriter with pre-commit

Typewriter currently accepts a single path per invocation, so the simplest pre-commit
integration is a local hook that scans the repository root:

```yaml
repos:
  - repo: local
    hooks:
      - id: typewriter
        name: typewriter
        entry: typewriter run .
        language: system
        pass_filenames: false
```

That hook applies changes in place. Pair it with a CI `--check` run so contributors see
the same normalization rules locally and in pull requests.

### Check vs apply

- `typewriter run . --check` previews diffs, leaves files untouched, and exits with `1`
  when changes are needed.
- `typewriter run .` applies the same rewrites in place and exits with `0` when it
  completes successfully.

Use `--check` in CI, editor integrations, and review bots. Use apply mode in local
cleanup workflows or scripted codemod runs.

### Ignore rules and Git ignore support

Use `--ignore` for paths that should always stay out of scope for a Typewriter run:

```bash
typewriter run . --check --ignore "generated" --ignore "test_*"
```

Those patterns are matched against both bare names and paths relative to the scanned
directory. `--respect-gitignore` is complementary: it applies the nearest `.gitignore`
at or above the scanned directory, which is helpful in monorepos and CI jobs that scan
from a package subdirectory.

### Choosing between Optional[...] and T | None

By default, Typewriter emits `Optional[...]` so the output stays compatible with Python
3.9 codebases. Use `--target-version 3.10` (or any 3.10+ target) when your project is
already standardized on PEP 604 unions and you want Typewriter to normalize existing
`Optional[...]` and `Union[...]` annotations to `T | None` as well:

```bash
typewriter run path/to/example.py --target-version 3.10
```

## Scope and non-goals

Typewriter intentionally focuses on one narrow kind of codemod: normalizing
`None`-related type annotations.

It does not try to:

- perform broad typing cleanup outside the current `None`-focused rewrite rules,
- rewrite docstrings or narrative documentation,
- infer business meaning beyond the syntax-driven codemod rules,
- replace a full linting, formatting, or static-analysis workflow.

If you need larger typing migrations, use Typewriter as one step in a broader toolchain
instead of expecting it to infer project-wide intent.

### Versioning
The package version is the single source of truth. The documentation version in
`docs/source/conf.py` is derived automatically from `typewriter.__version__`, which
reads the distribution metadata for `py-typewriter-cli`.

## Motivation

Typewriter was created to resolve issue [#2303](https://github.com/microsoft/playwright-python/issues/2303) in `microsoft/playwright-python`.

The issue highlighted a common inconsistency in the codebase where type annotations involving `None` were not standardized, leading to confusion and maintenance challenges. Specifically, some type annotations used `Union[T, None]` while others used `Optional[T]`, and there were cases where variable and parameter annotations did not use `Optional` even when the default value was `None`. This made it difficult to maintain a consistent style and to leverage static analysis tools effectively.

Surely, other developers have encountered similar inconsistencies in their codebases, and Typewriter can be a useful tool for anyone looking to standardize a common inconsistency and correct a common issue related to the use of `None` in type annotations. By using Typewriter,
developers can ensure that their codebase adheres to [PEP 484](https://peps.python.org/pep-0484/) proposal of requiring optional types to be made explicit.


## Contributing
Contributions to Typewriter are welcome! Please follow the fork-and-pull request workflow:
1. Fork the repository and create a new branch for your feature or bug fix.
2. Make your changes and commit them with clear messages.
3. Push your branch to your fork and open a pull request against the `main` branch of the original repository.

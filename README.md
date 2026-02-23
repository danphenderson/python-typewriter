# Typewriter

[![Documentation Status](https://readthedocs.org/projects/python-typewriter/badge/?style=flat)](https://danphenderson.github.io/python-typewriter/)
[![GitHub Actions Build Status](https://github.com/danphenderson/python-typewriter/actions/workflows/CI.yml/badge.svg)](https://github.com/danphenderson/python-typewriter/actions)
[![Coverage Status](https://coveralls.io/repos/danphenderson/python-typewriter/badge.svg?branch=main&service=github)](https://coveralls.io/r/danphenderson/python-typewriter)
[![Coverage Status](https://codecov.io/gh/danphenderson/python-typewriter/branch/main/graphs/badge.svg?branch=main)](https://codecov.io/github/danphenderson/python-typewriter)
[![PyPI Package latest release](https://img.shields.io/pypi/v/python-typewriter.svg)](https://pypi.org/project/python-typewriter)
[![PyPI Wheel](https://img.shields.io/pypi/wheel/python-typewriter.svg)](https://pypi.org/project/python-typewriter)
[![Supported versions](https://img.shields.io/pypi/pyversions/python-typewriter.svg)](https://pypi.org/project/python-typewriter)
[![Supported implementations](https://img.shields.io/pypi/implementation/python-typewriter.svg)](https://pypi.org/project/python-typewriter)

## Overview

Typewriter is a Python [Typer](https://typer.tiangolo.com/) CLI built on [LibCST](https://libcst.readthedocs.io/en/latest/) that normalizes `None`-related type annotations while preserving formatting and comments.

### What it rewrites

- `Union[T, None]` -> `Optional[T]`
- `Union[T1, T2, None]` -> `Optional[Union[T1, T2]]`
- `x: T = None` -> `x: Optional[T] = None`
- `def f(x: T = None)` -> `def f(x: Optional[T] = None)`

Additional behavior:
- `Any` annotations are left unchanged (for example, `x: Any = None` stays unchanged).
- Qualified typing references are preserved (for example, `typing.Union[...]` -> `typing.Optional[...]`).
- When bare `Optional[...]` is introduced, Typewriter adds `from typing import Optional` when needed. Also, if `Union` is no longer needed, Typewriter removes the previously imported `Union` from `typing`.

### Directory scanning behavior

When you run against a directory, Typewriter recursively processes `*.py` files and skips common non-source folders such as `.git`, `.venv`, `venv`, `__pycache__`, `build`, and `dist`.

## Installation

```bash
pip install python-typewriter
```

## Quick Start

Suppose you start with:
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

Preview changes:
```bash
typewriter run path/to/file.py --check
```

Apply changes:
```bash
typewriter run path/to/file.py
```

Result:
```python
from typing import Optional, Any

count: Optional[int] = None
name: Optional[str] = None
payload: Any = None

def greet(user_id: Optional[int] = None, msg: Optional[str] = None) -> Optional[str]:
    if user_id is None:
        return None
    return f"hello-{user_id}\n{msg}"
```

Run recursively on a directory:
```bash
typewriter run examples
```

## CLI

Typewriter exposes one subcommand: `run`.

### Transform a directory

Recursively transforms all `*.py` files under the directory.

```bash
typewriter run path/to/python_package_or_repo
```

### Transform a single file

```bash
typewriter run path/to/python_file.py
```

Non-`.py` files are rejected.

### Check mode (no writes)

Use `--check` to see what would change without writing files.

```bash
typewriter run path/to/python_dir --check
typewriter run path/to/python_file.py --check
```

In `--check` mode, Typewriter prints a unified diff for each file that would change:

```text
Would transform path/to/python_file.py
--- path/to/python_file.py
+++ path/to/python_file.py
@@ ...
-old line
+new line
```

Exit codes for `--check`:
- `0`: no changes needed
- `1`: changes would be made
- `2`: error

### Transform an in-memory string

Use `--code` to transform a string and print the transformed code to stdout (no files are written).

```bash
typewriter run --code "var: int = None\\n"
```

`--code` is mutually exclusive with `PATH`. In `--check` mode, this reports whether the provided code would change:

```bash
typewriter run --code "var: int = None\\n" --check
```

When changes are needed, `--check` also prints a unified diff labeled `provided`.

Notes:
- `PATH` and `--code` are mutually exclusive.
- Literal `\\n` sequences in `--code` input are interpreted as newlines.

## Motivation

This project was created to resolve issue [#2303](https://github.com/microsoft/playwright-python/issues/2303) in `microsoft/playwright-python`.

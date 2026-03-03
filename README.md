# Typewriter

[![Documentation Status](https://readthedocs.org/projects/python-typewriter/badge/?style=flat)](https://danphenderson.github.io/python-typewriter/)
[![GitHub Actions Build Status](https://github.com/danphenderson/python-typewriter/actions/workflows/CI.yml/badge.svg)](https://github.com/danphenderson/python-typewriter/actions)
[![Coveralls](https://coveralls.io/repos/github/danphenderson/python-typewriter/badge.svg?branch=main)](https://coveralls.io/github/danphenderson/python-typewriter?branch=main)
[![Codecov](https://codecov.io/gh/danphenderson/python-typewriter/graph/badge.svg?branch=main)](https://codecov.io/gh/danphenderson/python-typewriter)
[![PyPI Package latest release](https://img.shields.io/pypi/v/py-typewriter-cli.svg)](https://pypi.org/project/py-typewriter-cli)
[![PyPI Wheel](https://img.shields.io/pypi/wheel/py-typewriter-cli.svg)](https://pypi.org/project/py-typewriter-cli)
[![Supported versions](https://img.shields.io/pypi/pyversions/py-typewriter-cli.svg)](https://pypi.org/project/py-typewriter-cli)
[![Supported implementations](https://img.shields.io/pypi/implementation/py-typewriter-cli.svg)](https://pypi.org/project/py-typewriter-cli)

## Overview

Typewriter is a Python [Typer](https://typer.tiangolo.com/) CLI built on [LibCST](https://libcst.readthedocs.io/en/latest/) that normalizes `None`-related type annotations in Python source code. It can be used to automatically rewrite type annotations to use `Optional` instead of `Union` when `None` is involved, and to ensure `Optional` is used for variable and parameter annotations when the default value is `None`.

What it rewrites:
```python
Union[T, None] -> Optional[T]

Union[T1, T2, None] -> Optional[Union[T1, T2]]

x: T = None -> x: Optional[T] = None

def f(x: T = None) -> def f(x: Optional[T] = None)
```

Additional notes:
- `x: Any = None` stays unchanged.
- Qualified typing references are preserved.
- Import statements are added as needed and deduplicated.

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
#### Additional Details:
- `PATH` and `--code` are mutually exclusive.
- Literal `\\n` sequences in `--code` input are interpreted as newlines.
- When a directory is provided as `PATH`, Typewriter will ignore non-`.py` files and
common non-source subdirectories such as `.git`, `.venv`, `venv`, `__pycache__`, `build`, and `dist`.
- We ignore the more recent `PEP 604` syntax of `T | None` since it is not supported in Python 3.9, which is currently supported by `microsoft/playwright-python` and the ecosystem. However, support for this syntax may be added in the future.

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

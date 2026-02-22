# Typewriter

![Documentation Status](https://readthedocs.org/projects/python-typewriter/badge/?style=flat)
[![GitHub Actions Build Status](https://github.com/danphenderson/python-typewriter/actions/workflows/github-actions.yml/badge.svg)](https://github.com/danphenderson/python-typewriter/actions)
[![Coverage Status](https://coveralls.io/repos/danphenderson/python-typewriter/badge.svg?branch=main&service=github)](https://coveralls.io/r/danphenderson/python-typewriter)
[![Coverage Status](https://codecov.io/gh/danphenderson/python-typewriter/branch/main/graphs/badge.svg?branch=main)](https://codecov.io/github/danphenderson/python-typewriter)
[![PyPI Package latest release](https://img.shields.io/pypi/v/typewriter.svg)](https://pypi.org/project/typewriter)
[![PyPI Wheel](https://img.shields.io/pypi/wheel/typewriter.svg)](https://pypi.org/project/typewriter)
[![Supported versions](https://img.shields.io/pypi/pyversions/typewriter.svg)](https://pypi.org/project/typewriter)
[![Supported implementations](https://img.shields.io/pypi/implementation/typewriter.svg)](https://pypi.org/project/typewriter)


# Overview

A Python CLI to a `LibCST` codemode that standardizes Python None type annotations by:
- Converting optional parameters that default to `None` to have an explicit `Optional` type annotation
(unless the parameter is already annotated as `Optional` or `Union[..., None]`).
- Converting `Union[..., None]` to `Optional[...]`.

LibCST is a powerful library for parsing the abstract syntax tree (AST) of Python code while preserving formatting and comments. This allows for safe and accurate code transformations without losing the original style. For more information on LibCST, see the [LibCST documentation](https://libcst.readthedocs.io/en/latest/).

# Installation
You can install Typewriter using pip:

```bash
pip install typewriter
```

# Usage
To use Typewriter, simply run the following command in your terminal:
```bash
typewriter path/to/your/code.py
```
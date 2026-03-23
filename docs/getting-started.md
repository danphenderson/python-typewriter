# Getting started

## Install

```bash
pip install py-typewriter-cli
```

Typewriter supports Python 3.10 through 3.13.

## First run

Given a file like:

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

Preview the rewrite without changing the file:

```bash
typewriter run path/to/example.py --check
```

In `--check` mode Typewriter prints a unified diff and exits with:

- `0` when no changes are needed
- `1` when rewrites would be applied
- `2` when an error occurs

Apply the same rewrite in place:

```bash
typewriter run path/to/example.py
```

## Directory and inline-code runs

Run recursively on Python files in a directory:

```bash
typewriter run examples
```

Transform an in-memory string instead of a file:

```bash
typewriter run --code "var: int = None\n"
```

`PATH` and `--code` are mutually exclusive, and literal `\n` sequences in `--code` input are interpreted as newlines.

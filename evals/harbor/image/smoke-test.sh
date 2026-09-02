#!/usr/bin/env bash
set -euo pipefail

git --version
rustc --version
uv --version
pre-commit --version
autoflake --version
black --version
flake8 --version
mypy --version
python -m build --version
python -c 'import autoflake; print("autoflake import ok")'

for version in 310 311 312 313 314; do
    python_path="/opt/typewriter/venvs/py${version}/bin/python"
    "${python_path}" -c \
        'import coverage, libcst, pathspec, pytest, typer; print("maintenance imports ok")'
done

test -d /opt/typewriter/pre-commit
test -n "$(find /opt/typewriter/wheelhouse -maxdepth 1 -type f -name '*.whl' -print -quit)"
test -d /workspace/typewriter

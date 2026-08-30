#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
default_source_repo=$(cd -- "${script_dir}/.." && pwd -P)
source_repo=${TYPEWRITER_HOOK_REPO:-${default_source_repo}}
sample_repo=$(mktemp -d "${TMPDIR:-/tmp}/typewriter-pre-commit.XXXXXX")
pre_commit_bin=${PRE_COMMIT:-pre-commit}

cleanup() {
    rm -rf -- "${sample_repo}"
}
trap cleanup EXIT

git -C "${sample_repo}" init -q -b main
git -C "${sample_repo}" config user.name "Typewriter Hook Test"
git -C "${sample_repo}" config user.email "hook-test@typewriter.invalid"

printf '%s\n' '[tool.typewriter]' 'target-version = "3.10"' >"${sample_repo}/pyproject.toml"
printf '%s\n' 'first: int = None' >"${sample_repo}/selected_first.py"
printf '%s\n' 'def broken(:' >"${sample_repo}/selected_second.py"
printf '%s\n' 'unpassed: int = None' >"${sample_repo}/not_passed.py"
printf '%s\n' 'interface: int = None' >"${sample_repo}/interface.pyi"

git -C "${sample_repo}" add -A
git -C "${sample_repo}" commit -q -m "initial hook fixture"

run_hook() {
    (
        cd "${sample_repo}"
        "${pre_commit_bin}" try-repo "${source_repo}" typewriter \
            --files selected_first.py selected_second.py interface.pyi
    )
}

set +e
run_hook
atomic_rc=$?
set -e
if [[ "${atomic_rc}" -eq 0 ]]; then
    echo "expected malformed batch to fail" >&2
    exit 1
fi
if [[ "$(<"${sample_repo}/selected_first.py")" != 'first: int = None' ]]; then
    echo "valid file changed despite a malformed later file" >&2
    exit 1
fi
if [[ "$(<"${sample_repo}/selected_second.py")" != 'def broken(:' ]]; then
    echo "malformed file changed during failed batch" >&2
    exit 1
fi

printf '%s\n' 'second: int = None' >"${sample_repo}/selected_second.py"
git -C "${sample_repo}" add selected_second.py
git -C "${sample_repo}" commit -q -m "repair second fixture"

set +e
run_hook
first_run_rc=$?
set -e
if [[ "${first_run_rc}" -eq 0 ]]; then
    echo "expected first clean-input run to report hook modifications" >&2
    exit 1
fi
if [[ "$(<"${sample_repo}/selected_first.py")" != 'first: int | None = None' ]]; then
    echo "first passed file did not use configured Python 3.10 syntax" >&2
    exit 1
fi
if [[ "$(<"${sample_repo}/selected_second.py")" != 'second: int | None = None' ]]; then
    echo "second passed file did not use configured Python 3.10 syntax" >&2
    exit 1
fi
if [[ "$(<"${sample_repo}/not_passed.py")" != 'unpassed: int = None' ]]; then
    echo "hook changed a Python file that was not passed" >&2
    exit 1
fi
if [[ "$(<"${sample_repo}/interface.pyi")" != 'interface: int = None' ]]; then
    echo "hook changed an excluded .pyi file" >&2
    exit 1
fi

git -C "${sample_repo}" add selected_first.py selected_second.py
run_hook

if ! git -C "${sample_repo}" diff --quiet; then
    echo "clean hook rerun changed files" >&2
    exit 1
fi

echo "pre-commit try-repo integration passed"

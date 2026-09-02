#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
source_repo=$(cd -- "${script_dir}/.." && pwd -P)
package_source=${1:-${source_repo}}
python_bin=${PYTHON:-python3}
sample_root=$(mktemp -d "${TMPDIR:-/tmp}/typewriter-adoption.XXXXXX")
sample_repo="${sample_root}/repo"
sample_venv="${sample_root}/venv"
pre_commit_home="${sample_root}/pre-commit-home"

cleanup() {
    rm -rf -- "${sample_root}"
}
trap cleanup EXIT

mkdir "${sample_repo}"
"${python_bin}" -m venv "${sample_venv}"
sample_python="${sample_venv}/bin/python"
sample_typewriter="${sample_venv}/bin/typewriter"
sample_pre_commit="${sample_venv}/bin/pre-commit"
"${sample_python}" -m pip install --disable-pip-version-check \
    "${package_source}" \
    "pre-commit==4.6.2"

"${sample_python}" -c '
import importlib.metadata as metadata

distribution = metadata.metadata("py-typewriter-cli")
assert metadata.version("py-typewriter-cli") == "1.2.0"
assert distribution["Summary"] == "A LibCST codemod and CLI for normalizing None-related Python type annotations."
'

git -C "${sample_repo}" init -q -b main
git -C "${sample_repo}" config user.name "Typewriter Adoption Test"
git -C "${sample_repo}" config user.email "adoption-test@typewriter.invalid"

printf '%s\n' 'value: int = None' >"${sample_repo}/example.py"

set +e
default_preview=$(cd "${sample_repo}" && "${sample_typewriter}" run example.py --check 2>&1)
default_preview_rc=$?
set -e
if [[ "${default_preview_rc}" -ne 1 || "${default_preview}" != *"Optional[int]"* ]]; then
    echo "default preview did not report the expected Optional rewrite" >&2
    exit 1
fi
if [[ "$(<"${sample_repo}/example.py")" != 'value: int = None' ]]; then
    echo "preview changed the sample source" >&2
    exit 1
fi

printf '%s\n' \
    '[tool.typewriter]' \
    'target-version = "3.10"' \
    'respect-gitignore = false' \
    'ignore = ["generated"]' \
    >"${sample_repo}/pyproject.toml"
mkdir "${sample_repo}/generated"
printf '%s\n' 'generated: int = None' >"${sample_repo}/generated/ignored.py"

config_json=$(cd "${sample_repo}" && "${sample_typewriter}" config --output-format json)
"${sample_python}" -c '
import json
import sys

payload = json.loads(sys.argv[1])
assert payload["type"] == "config"
assert payload["values"]["target_version"] == {"value": "3.10", "source": "config"}
assert payload["values"]["respect_gitignore"] == {"value": False, "source": "config"}
assert payload["values"]["ignore"] == [{"pattern": "generated", "source": "config"}]
' "${config_json}"

set +e
policy_preview=$(cd "${sample_repo}" && "${sample_typewriter}" run . --check 2>&1)
policy_preview_rc=$?
set -e
if [[ "${policy_preview_rc}" -ne 1 || "${policy_preview}" != *"int | None"* ]]; then
    echo "policy preview did not report the expected PEP 604 rewrite" >&2
    exit 1
fi
if [[ "$(<"${sample_repo}/example.py")" != 'value: int = None' ]]; then
    echo "policy preview changed the sample source" >&2
    exit 1
fi

(cd "${sample_repo}" && "${sample_typewriter}" run .)
if [[ "$(<"${sample_repo}/example.py")" != 'value: int | None = None' ]]; then
    echo "apply did not produce the reviewed PEP 604 rewrite" >&2
    exit 1
fi
if [[ "$(<"${sample_repo}/generated/ignored.py")" != 'generated: int = None' ]]; then
    echo "apply changed a config-ignored file" >&2
    exit 1
fi

printf '%s\n' \
    'repos:' \
    '  - repo: https://github.com/danphenderson/python-typewriter' \
    '    rev: v1.2.0' \
    '    hooks:' \
    '      - id: typewriter' \
    >"${sample_repo}/.pre-commit-config.yaml"
if ! grep -Fq 'rev: v1.2.0' "${sample_repo}/.pre-commit-config.yaml"; then
    echo "planned hook config is not pinned to v1.2.0" >&2
    exit 1
fi

printf '%s\n' 'hook_only: int = None' >"${sample_repo}/hook_only.py"
git -C "${sample_repo}" add -A
git -C "${sample_repo}" commit -q -m "pre-hook adoption sample"

run_candidate_hook() {
    (
        cd "${sample_repo}"
        PRE_COMMIT_HOME="${pre_commit_home}" \
            "${sample_pre_commit}" try-repo "${source_repo}" typewriter \
            --files hook_only.py
    )
}

set +e
hook_first_output=$(run_candidate_hook 2>&1)
hook_first_rc=$?
set -e
if [[ "${hook_first_rc}" -eq 0 || "${hook_first_output}" != *"files were modified by this hook"* ]]; then
    echo "candidate hook first run did not modify and fail" >&2
    exit 1
fi
if [[ "$(<"${sample_repo}/hook_only.py")" != 'hook_only: int | None = None' ]]; then
    echo "candidate hook did not apply project policy" >&2
    exit 1
fi

git -C "${sample_repo}" add hook_only.py
run_candidate_hook

(cd "${sample_repo}" && "${sample_typewriter}" run . --check)

echo "verified 1.2.0 adoption workflow passed"

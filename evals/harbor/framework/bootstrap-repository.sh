#!/usr/bin/env bash
set -euo pipefail

workspace=/workspace/typewriter
archive="${workspace}/repository.tar"
setup_script="${workspace}/setup.sh"

if [[ "$(pwd -P)" != "${workspace}" ]]; then
    echo "repository setup must run from ${workspace}" >&2
    exit 1
fi

if [[ ! -f "${archive}" ]]; then
    echo "missing repository snapshot: ${archive}" >&2
    exit 1
fi

shopt -s dotglob nullglob
for entry in "${workspace}"/*; do
    case "${entry}" in
        "${archive}"|"${setup_script}") ;;
        *)
            echo "refusing to overwrite unexpected setup input: ${entry}" >&2
            exit 1
            ;;
    esac
done

tar -xf "${archive}" -C "${workspace}"
rm -f "${archive}" "${setup_script}"

git init -q -b eval-baseline
git config user.name "Typewriter Eval"
git config user.email "eval@typewriter.invalid"
git add -A
GIT_AUTHOR_DATE="2000-01-01T00:00:00Z" \
GIT_COMMITTER_DATE="2000-01-01T00:00:00Z" \
    git commit -q --no-gpg-sign -m "eval baseline"

cp -R --no-preserve=ownership /opt/typewriter/venvs/py310 .venv
uv pip install \
    --python .venv/bin/python \
    --no-build-isolation \
    --no-deps \
    --editable .

git status --short

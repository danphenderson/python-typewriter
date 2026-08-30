#!/usr/bin/env bash
set -u

workspace=/workspace/typewriter
verifier_logs=/logs/verifier
receipts=${verifier_logs}/receipts

mkdir -p "${receipts}" "${verifier_logs}"
cd "${workspace}" || exit 1

run_gate() {
    local name="$1"
    shift
    "$@" >"${receipts}/${name}.log" 2>&1
    local return_code=$?
    printf '%s' "${return_code}"
}

targeted_rc=$(run_gate targeted \
    .venv/bin/python -m pytest -q /tests/hidden_tests \
    --junitxml="${verifier_logs}/targeted-junit.xml")

regression_rc=$(run_gate regression \
    .venv/bin/python -m pytest -q tests \
    --junitxml="${verifier_logs}/regression-junit.xml")

rm -rf "${receipts}/dist"
build_rc=$(run_gate build \
    .venv/bin/python -m build --no-isolation --outdir "${receipts}/dist")

git -c safe.directory="${workspace}" status --short >"${receipts}/git-status.txt"
git -c safe.directory="${workspace}" add -N -- .
git -c safe.directory="${workspace}" diff --binary >"${receipts}/agent.patch"

reward=0
if [[ "${targeted_rc}" -eq 0 && "${regression_rc}" -eq 0 && "${build_rc}" -eq 0 ]]; then
    reward=1
fi

jq -n \
    --argjson targeted_rc "${targeted_rc}" \
    --argjson regression_rc "${regression_rc}" \
    --argjson build_rc "${build_rc}" \
    --argjson reward "${reward}" \
    '{targeted_rc: $targeted_rc, regression_rc: $regression_rc, build_rc: $build_rc, reward: $reward}' \
    >"${receipts}/gate-results.json"

printf '%s\n' "${reward}" >"${verifier_logs}/reward.txt"
exit 0

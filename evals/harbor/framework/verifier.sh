#!/usr/bin/env bash
set -u

workspace=/workspace/typewriter
artifacts=/logs/artifacts
verifier_logs=/logs/verifier

mkdir -p "${artifacts}" "${verifier_logs}"
cd "${workspace}" || exit 1

run_gate() {
    local name="$1"
    shift
    "$@" >"${artifacts}/${name}.log" 2>&1
    local return_code=$?
    printf '%s' "${return_code}"
}

targeted_rc=$(run_gate targeted \
    .venv/bin/python -m pytest -q /tests/hidden_tests \
    --junitxml="${verifier_logs}/targeted-junit.xml")

regression_rc=$(run_gate regression \
    .venv/bin/python -m pytest -q tests \
    --junitxml="${verifier_logs}/regression-junit.xml")

rm -rf "${artifacts}/dist"
build_rc=$(run_gate build \
    .venv/bin/python -m build --no-isolation --outdir "${artifacts}/dist")

git diff --binary >"${artifacts}/agent.patch"
git status --short >"${artifacts}/git-status.txt"

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
    >"${artifacts}/gate-results.json"

printf '%s\n' "${reward}" >"${verifier_logs}/reward.txt"
exit 0

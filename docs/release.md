# Release 1.2.0 runbook

The source tree is prepared for version 1.2.0, but the release is not complete.
Every gate below is independent and fail-closed. Record command output and the
exact commit SHA in the release issue; do not use success at one gate as evidence
for another.

## Gate 1: build and package verification

From a clean checkout of the candidate commit:

```bash
python -m build
tools/test_adoption_workflow.sh dist/py_typewriter_cli-1.2.0-py3-none-any.whl
```

Verify that both sdist and wheel exist, wheel metadata reports version `1.2.0`
and the intended description, and the isolated adoption workflow passes its
preview, policy, apply, local-candidate `pre-commit try-repo`, and clean CI
checks. The candidate hook must use a fresh pre-commit cache; the planned
downstream `v1.2.0` config is not fetched at this gate. Stop if the checkout is
dirty, metadata differs, installation uses another source, the hook environment
cannot be created, or any clean-sample check fails.

## Gate 2: all Harbor maintenance controls

Generate and load every task, then require a negative and positive control for
every listed slug:

```bash
python tools/harbor_eval.py validate-all --harbor-import-check
python tools/harbor_eval.py generate-all
python tools/harbor_eval.py list
```

For each slug returned by `list`, run Harbor once with the `nop` agent and assert
reward `0`, then with the `oracle` agent and assert reward `1`. Preserve the job
directories as evidence. Stop on an empty slug list, nondeterministic generation,
load failure, exception, missing artifact, or unexpected reward.

## Gate 3: hosted CI

Push the candidate only after Gates 1 and 2. Require the exact candidate SHA to
be green in the normal lint/test/build matrix, the official-hook try-repo job,
the adoption workflow, and Harbor maintenance controls. Local results do not
substitute for hosted checks. Stop on a missing, skipped, stale-head, neutral,
cancelled, or failing required check.

## Gate 4: tag and GitHub release

Only after Gate 3 is green, confirm the candidate equals the intended protected
branch head and that `v1.2.0` does not already exist. Create the tag at that exact
commit and publish a GitHub release from the reviewed 1.2.0 changelog entry. Stop
on branch divergence, an existing or ambiguous ref, changed release notes, or a
tag that does not resolve to the approved commit.

## Gate 5: PyPI publication

Treat the release-triggered publication workflow as a new gate. Require trusted
publishing to complete, download both artifacts from PyPI in a clean environment,
verify their hashes and metadata against Gate 1, and run the installed CLI smoke
test. A GitHub release alone is not PyPI evidence. Stop on a missing artifact,
metadata or hash mismatch, failed workflow, or install from any non-PyPI source.

## Gate 6: downstream adoption baseline

Only after Gate 5, select and record the first downstream repository and its
pre-adoption commit SHA. Follow the adoption guide in a review branch, recording
the Typewriter version, policy, preview exit code, changed-file count, hook clean
rerun, CI result, and post-adoption commit. This receipt is the baseline for
future adoption comparisons; do not infer adoption, quality improvement, or
repository-wide coverage from package publication alone.

No tag, GitHub release, PyPI upload, or downstream mutation is authorized by
this runbook itself.

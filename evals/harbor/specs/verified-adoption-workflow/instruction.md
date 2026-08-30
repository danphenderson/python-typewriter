# Publish a verified project-policy adoption workflow

Prepare the source tree for an unreleased version 1.2.0. Set the package
description exactly to:

```text
A LibCST codemod and CLI for normalizing None-related Python type annotations.
```

Turn the README and MkDocs documentation into one executable adoption path:
install the exact released package, preview with `--check`, commit and inspect a
shared `[tool.typewriter]` policy, preview again, apply the reviewed batch,
enable the official hook at the planned `rev: v1.2.0`, and add the same policy
as a CI check. Make it explicit that the package and hook commands are for use
only after 1.2.0 is actually published.

Add an unreleased 1.2.0 changelog entry and a fail-closed release runbook. Keep
package build/metadata verification, every Harbor no-op and Oracle control,
hosted CI at the exact candidate SHA, tag and GitHub release creation, PyPI
publication, and a measured downstream-adoption baseline as six separate gates.
Do not claim that a later gate passed because an earlier one did. This task must
not create a tag, GitHub release, PyPI publication, or downstream mutation.

Add an executable clean-sample rehearsal and one focused, non-matrix CI job. The
rehearsal must install the candidate and confirm version/description metadata,
prove default and policy-aware previews do not write, inspect resolved config,
apply while respecting a config-rooted ignore, exercise a real local-candidate
`pre-commit try-repo` modify-then-clean lifecycle, and finish with the documented
CI check. Keep the sample repository separate from its virtual environment and
pre-commit cache. The focused CI job must strictly build MkDocs before running
the rehearsal against the built wheel.

The workflow must remain feasible in the maintenance-v2 environment with
networking disabled and dependencies coming from its wheelhouse. Run the full
Python 3.10-3.14 regression matrix, strict documentation build, package build,
and repository hooks before finishing.

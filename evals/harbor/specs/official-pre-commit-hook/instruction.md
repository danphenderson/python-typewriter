# Publish an official pre-commit hook

Publish a root `.pre-commit-hooks.yaml` entry with these semantics:

```yaml
- id: typewriter
  name: typewriter
  entry: typewriter run
  language: python
  types: [python]
  exclude: '\.pyi$'
  require_serial: true
```

Keep normal pre-commit filename passing; do not use `pass_filenames: false` and
do not switch to a system-language hook. The selected Python filenames must be
passed together to Typewriter's atomic batch API, so a malformed later file
leaves earlier files unchanged. Hook runs must load the same nearest
`[tool.typewriter]` policy as direct CLI runs. Stub files ending in `.pyi` must
remain excluded.

Add a real `pre-commit try-repo` integration that builds the hook environment
and exercises a temporary sample Git repository. It must prove that only passed
files are considered, project policy is applied, a passed `.pyi` is excluded, a
malformed later input rolls the whole batch back, the first successful rewrite
returns nonzero after modifying files, and the staged clean rerun succeeds.
Place that integration in one dedicated CI path or job rather than multiplying
hook-environment creation across the full operating-system/Python test matrix.

The integration must be feasible from the maintenance-v2 wheelhouse with
networking disabled. Document the official repository hook with a release-tag
placeholder, its normal changed-file scope, atomicity, project policy, `.pyi`
exclusion, and modify-then-rerun lifecycle. Do not claim or create a release tag
as part of this change. Run the full test suite and package build before
finishing.

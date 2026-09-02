# Adopt Typewriter 1.2.0

Version 1.2.0 is currently prepared in source but unreleased. The commands below
become a downstream installation path only after the release runbook confirms
the GitHub and PyPI gates. Before publication, repository maintainers can run
`tools/test_adoption_workflow.sh` against a local source tree or built wheel.

## 1. Install the released package

Use an exact version so the CLI and hook policy remain reproducible:

```bash
python -m pip install "py-typewriter-cli==1.2.0"
```

## 2. Preview the existing repository

Check the proposed rewrites without changing source files:

```bash
typewriter run . --check
```

Exit code `1` means Typewriter found changes; exit code `0` means the current
scope is already normalized. Exit code `2` is an error and must not be treated
as a clean result.

## 3. Commit project policy

Add shared policy to the nearest project `pyproject.toml`:

```toml
[tool.typewriter]
target-version = "3.10"
respect-gitignore = true
ignore = ["generated", "src/vendor/*"]
```

Inspect the exact resolved values and sources, then preview again under that
policy. The second preview is the one to review before applying changes:

```bash
typewriter config
typewriter run . --check
```

## 4. Apply the reviewed batch

```bash
typewriter run .
```

The batch is atomic: malformed or unwritable later input does not leave earlier
files partially replaced. Review and test the resulting repository changes
before committing them.

## 5. Enable the official hook

After the `v1.2.0` tag exists and its release gates are complete, add:

```yaml
repos:
  - repo: https://github.com/danphenderson/python-typewriter
    rev: v1.2.0
    hooks:
      - id: typewriter
```

Then install and run the hook:

```bash
pre-commit install
pre-commit run typewriter --all-files
```

The first run exits nonzero when it modifies files. Stage the changes and rerun
until it passes. The hook uses normal changed-file passing, project policy, one
serial atomic batch, and excludes `.pyi` files.

## 6. Add the CI check

Use the same committed policy in CI:

```yaml
- name: Install Typewriter
  run: python -m pip install "py-typewriter-cli==1.2.0"
- name: Check Typewriter policy
  run: typewriter run . --check
```

Keep installation, preview, policy review, apply, hook enablement, and CI as
separate reviewable steps. Do not enable the pinned hook or CI installation in a
downstream repository until 1.2.0 is actually published.

# Usage

## Core CLI patterns

Use check mode for review, CI, and bots:

```bash
typewriter run . --check --respect-gitignore
```

Use apply mode for local cleanup:

```bash
typewriter run . --respect-gitignore
```

When a directory is scanned, Typewriter ignores non-`.py` files and common non-source directories such as `.git`, `.venv`, `venv`, `__pycache__`, `build`, and `dist`.

Combine files and directories when a maintenance task spans several scopes:

```bash
typewriter run src tests/test_cli.py --check
```

Inputs keep their command-line order, files found within each directory are sorted,
and overlapping paths are processed once. Apply mode validates and transforms the
entire batch before replacing files; a later failure restores any earlier replacement.

## Project policy

Store shared defaults under `[tool.typewriter]` in `pyproject.toml`:

```toml
[tool.typewriter]
target-version = "3.10"
respect-gitignore = true
ignore = ["generated", "src/vendor/*"]
```

Discovery starts from the invocation directory and selects the nearest ancestor
`pyproject.toml`; `--config` bypasses discovery. CLI target and `.gitignore`
flags override configured values. CLI ignore patterns append after configured
patterns, and configured ignores are always interpreted relative to the config
file's directory.

Inspect the effective policy without scanning or rewriting source files:

```bash
typewriter config
typewriter config --config path/to/policy.toml --ignore local-only --output-format json
```

The report names the selected config file and shows the effective target,
`.gitignore` setting, and ordered ignore patterns together with each value's
source (`default`, `config`, or `cli`). JSON reports use the stable top-level
fields `type`, `config_file`, and `values`. The reporting command only reads
policy; it never discovers, parses, or writes Python source files.

## JSON output for automation

If another tool needs structured output, use JSON:

```bash
typewriter run . --check --respect-gitignore --output-format json
```

Directory and file runs report the scanned path, whether check mode was used, how many files were processed, how many changed, and optional unified diffs. `--code` runs report whether the input changed and return either the transformed code or the diff, depending on the mode.

## CI example

A minimal GitHub Actions step looks like:

```yaml
- name: Check None-related typing annotations
  run: typewriter run . --check --respect-gitignore
```

## pre-commit example

The official hook uses the filenames selected by pre-commit and processes them
as one atomic batch. Replace `<tag-containing-hook>` with a released tag that
contains the hook manifest:

```yaml
repos:
  - repo: https://github.com/danphenderson/python-typewriter
    rev: <tag-containing-hook>
    hooks:
      - id: typewriter
```

Normal filename passing means only selected Python files are considered; `.pyi`
stubs are excluded. The hook applies the nearest `[tool.typewriter]` policy and
keeps batch rollback guarantees if any passed file fails. Its first rewriting
run exits nonzero, so stage the edits and rerun. Pair it with a CI `--check` run
so contributors see the same policy locally and in pull requests.

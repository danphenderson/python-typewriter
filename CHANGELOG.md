# Changelog

All notable changes to Typewriter are recorded here.

## [1.2.0] - Unreleased

### Added

- Atomic ordered processing for multiple file and directory inputs.
- Immutable `[tool.typewriter]` project policy with nearest-file discovery,
  explicit config selection, CLI precedence, config-rooted ignores, and Python
  3.10 `tomli` support.
- `typewriter config` text and JSON reports for effective values and provenance.
- An official serial Python pre-commit hook with normal changed-file passing,
  `.pyi` exclusion, and dedicated `pre-commit try-repo` coverage.
- A verified clean-sample adoption workflow and a fail-closed release runbook.
- Harbor maintenance tasks and no-op/Oracle controls for each repository story.

### Changed

- Package metadata now describes Typewriter as a LibCST codemod and CLI for
  normalizing `None`-related Python type annotations.
- Supported maintenance environments cover Python 3.10 through 3.14.

This entry prepares the source for 1.2.0. It does not indicate that a tag,
GitHub release, PyPI publication, or downstream adoption baseline exists.

[1.2.0]: https://github.com/danphenderson/python-typewriter/compare/v1.1.0...HEAD

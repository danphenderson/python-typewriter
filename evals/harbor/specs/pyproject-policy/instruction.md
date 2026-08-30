# Load project policy from pyproject.toml

Add a reusable project-policy layer so teams can share Typewriter defaults
without repeating CLI flags in every maintenance workflow.

Define an immutable public `TypewriterConfig` and a loader for the
`[tool.typewriter]` table. Supported keys are:

```toml
[tool.typewriter]
target-version = "3.10"
respect-gitignore = true
ignore = ["generated", "src/vendor/*"]
```

Without an explicit config path, discover the nearest ancestor
`pyproject.toml` from the invocation working directory. That first file is the
project boundary even when it has no Typewriter table. Add `--config PATH` to
bypass discovery and use that TOML file instead. Unknown Typewriter keys,
invalid TOML, malformed field types or values, and missing, unreadable, or
non-file explicit config paths must fail with exit code `2`. JSON mode must emit
one error object on stderr, leave stdout empty, and perform no source writes.

Implement field-specific precedence. `--target-version` overrides config, which
overrides the existing default. Make `.gitignore` policy tri-state with
`--respect-gitignore` and `--no-respect-gitignore`; either explicit flag
overrides config, which otherwise defaults to false. Config ignore patterns come
first, repeatable CLI ignores append, and exact duplicates are removed stably so
the first rule keeps its meaning.

Configured ignores must be anchored to the directory containing the resolved
config file. Apply those rules to explicit files and recursive directory inputs,
including when a narrower subdirectory is scanned. Do not apply them to paths
outside that root. Preserve the existing scan-root semantics for CLI and direct
runner ignore patterns. Add `TypewriterRunner.from_config` and retain internal
value provenance on the effective immutable config for a later reporting
feature, but do not add new provenance fields to CLI JSON yet.

Python 3.10 must load TOML through the `tomli` fallback. Declare `tomli` as a
runtime dependency with a Python `<3.11` marker, not only as a test dependency.
Document project policy, precedence, anchoring, and explicit config usage while
preserving existing single-path, batch, and inline-code behavior. Run the full
test suite and package build before finishing.

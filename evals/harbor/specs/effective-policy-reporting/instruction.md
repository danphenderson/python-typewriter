# Explain the effective project policy

Add a read-only `typewriter config` command that explains the policy Typewriter
would use without discovering, parsing, transforming, or writing Python source
files. It must accept the same policy inputs as `typewriter run`: `--config`,
`--target-version`, repeatable `--ignore`, the paired
`--respect-gitignore`/`--no-respect-gitignore` override, and `--output-format`.
Reuse project-policy discovery, validation, precedence, stable ignore
deduplication, and retained provenance rather than implementing a second policy
model.

Text output must identify the selected config file (or that none was selected)
and show the effective target version, `.gitignore` boolean, and ordered ignore
patterns with each value's `default`, `config`, or `cli` source. JSON output has
exactly these top-level fields:

```json
{
  "type": "config",
  "config_file": "/absolute/path/to/pyproject.toml",
  "values": {
    "target_version": {"value": "3.10", "source": "config"},
    "respect_gitignore": {"value": false, "source": "cli"},
    "ignore": [
      {"pattern": "generated", "source": "config"},
      {"pattern": "local-only", "source": "cli"}
    ]
  }
}
```

Use JSON `null` for an absent config file or target version. Preserve config
ignore items before CLI items, and keep the first item's source when exact
duplicates are removed. Invalid TOML, unknown or malformed policy values, and
invalid explicit config paths must retain exit code `2`; JSON mode emits one
`{"type": "error", ...}` object on stderr with empty stdout.

Do not add config or provenance fields to any existing `typewriter run` JSON
shape. Document text and JSON inspection for contributors and maintenance
automation. Run the full test suite and package build before finishing.

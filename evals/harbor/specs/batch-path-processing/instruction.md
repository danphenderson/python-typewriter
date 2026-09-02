# Add atomic multi-path processing

Typewriter currently processes one file or directory per invocation. Extend it
so repository-maintenance workflows can submit an ordered batch of files and
directories without risking a partially rewritten checkout.

Add this public runner API:

```python
TypewriterRunner.process_paths(
    paths: Sequence[Path],
    *,
    write: bool = True,
    include_diff: bool = False,
) -> ProcessResult
```

The method must validate every explicit input before transforming anything.
Missing or unreadable paths, unsupported explicit file suffixes, and inputs that
are neither regular files nor directories must fail the whole call. Recursively
discovered non-Python files remain out of scope. Preserve explicit input order,
sort directory discoveries, and deduplicate overlaps by resolved path so the
first eligible occurrence wins. Apply configured ignore patterns and nearest
`.gitignore` rules to explicit files as well as recursive discoveries.

Each source file must receive a fresh codemod context. Read, parse, and transform
every selected file in memory before write mode changes the checkout. Replace
changed files atomically through same-directory temporary files while preserving
their mode bits. If a later replacement fails, restore every file already
replaced and report an error. Check mode must never write and must return the
aggregate changed paths and optional diffs.

Update the CLI to accept `typewriter run [PATHS]...`. `--code` remains mutually
exclusive with any path. A single path must retain the existing text behavior
and JSON object (`type` is `file` or `directory` and `path` remains singular).
For multiple paths, emit one JSON object with `type: "paths"`, the ordered input
`paths`, aggregate processed and changed counts, ordered changed files, policy
fields, and diffs when requested. Preserve exit codes: apply success is `0`, a
clean check is `0`, a changed check is `1`, and invalid, parse, or write failures
are `2`.

Document the multi-path API and CLI behavior. Keep lower-level codemod helpers
and existing single-path and inline-code workflows compatible. Run the relevant
tests and package build before finishing.

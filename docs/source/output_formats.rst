==============
Output formats
==============

Default text output
===================

The default CLI output remains human-oriented text so existing usage keeps working:

* apply mode prints each changed file and a summary line,
* ``--check`` prints each changed file, a unified diff, and a summary line,
* ``--code`` prints the transformed source directly.

JSON output for automation
==========================

Use ``--output-format json`` when another tool needs structured output:

.. code-block:: bash

   typewriter run . --check --output-format json

Directory and file runs return a JSON object with:

* ``type``: ``"directory"`` or ``"file"``,
* ``path``: the scanned path,
* ``check``: whether ``--check`` was used,
* ``processed_files``: number of Python files inspected,
* ``changed_count``: number of changed files,
* ``changed_files``: changed paths as strings,
* ``diffs``: optional unified diffs keyed by file path.

``--code`` runs return a JSON object with:

* ``type``: ``"code"``,
* ``check``: whether ``--check`` was used,
* ``changed``: whether the input would change,
* ``transformed_code`` in apply mode,
* ``diff`` in check mode when the input would change.

Diff-only behavior in check mode
================================

For automation, ``--check --output-format json`` is intentionally diff-oriented:

* file and directory scans include unified diffs rather than rewritten file contents,
* ``--code --check`` includes ``diff`` instead of ``transformed_code``.

That keeps check-mode payloads compact and aligned with the existing text-mode
semantics, where ``--check`` is for review and gating rather than applying changes.

Structured errors
=================

When JSON output is enabled, CLI errors are emitted as JSON on stderr and the existing
exit code semantics stay the same.

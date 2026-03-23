=========
Embedding
=========

Typewriter exposes a higher-level runner for tools that want to reuse the existing
codemod pipeline without rebuilding CLI option handling.

Using ``TypewriterRunner``
==========================

.. code-block:: python

   from pathlib import Path

   from typewriter import TypewriterRunner

   runner = TypewriterRunner(
       target_version="3.10",
       ignore=["generated"],
       respect_gitignore=True,
   )

   code_result = runner.process_code("value: int = None\n")
   assert code_result.changed is True
   assert "value: int | None = None" in code_result.transformed_code

   file_result = runner.process_file(Path("example.py"), write=False, include_diff=True)
   directory_result = runner.process_directory(Path("."), write=False, include_diff=True)

Runner behavior
===============

``TypewriterRunner`` centralizes a few decisions that CLI users already make:

* target Python version / PEP 604 output,
* ignore patterns for directory scans,
* whether to respect ``.gitignore``.

Each method returns the same structured results as the lower-level functions in
``typewriter.codemod``:

* ``process_code`` returns ``ProcessStringResult`` with the original and transformed
  source.
* ``process_file`` and ``process_directory`` return ``ProcessResult`` with processed
  paths, changed paths, and optional diffs.

When to use the lower-level functions
=====================================

Use ``typewriter.codemod`` directly when you already manage your own context object or
need fine-grained access to the lower-level transformation helpers. Use
``TypewriterRunner`` when you want a small reusable object that mirrors the CLI options.

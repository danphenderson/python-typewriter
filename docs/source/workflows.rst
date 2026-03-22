=========
Workflows
=========

Recommended workflows
=====================

Typewriter is easiest to adopt when you split usage into two modes:

* **Apply mode** for local cleanup runs that rewrite files in place.
* **Check mode** for CI, bots, and editor integrations that need a diff and a stable
  exit code without modifying files.

Check vs apply
==============

Preview changes without writing files:

.. code-block:: bash

   typewriter run . --check --respect-gitignore

Apply the same transformation in place:

.. code-block:: bash

   typewriter run . --respect-gitignore

In ``--check`` mode the CLI exits with:

* ``0`` when no files need changes,
* ``1`` when rewrites would be applied,
* ``2`` when Typewriter hits an error.

Using Typewriter in CI
======================

Typewriter is a good fit for CI jobs that guard against unnormalized ``None``-related
annotations:

.. code-block:: yaml

   - name: Check None-related typing annotations
     run: typewriter run . --check --respect-gitignore

If your CI system or bot needs structured output, use JSON:

.. code-block:: bash

   typewriter run . --check --respect-gitignore --output-format json

Using Typewriter with pre-commit
================================

Typewriter currently accepts a single path per invocation, so a local hook that scans
the repository root is the most predictable setup:

.. code-block:: yaml

   repos:
     - repo: local
       hooks:
         - id: typewriter
           name: typewriter
           entry: typewriter run .
           language: system
           pass_filenames: false

That keeps the hook configuration simple and aligns well with a matching CI
``--check`` run.

Ignore rules and Git ignore support
===================================

Use ``--ignore`` for project-specific exclusions that should always remain outside a
Typewriter run:

.. code-block:: bash

   typewriter run . --check --ignore "generated" --ignore "test_*"

Use ``--respect-gitignore`` when you want Typewriter to also honor the nearest
``.gitignore`` at or above the scanned directory.

Choosing between Optional[...] and T | None
===========================================

Typewriter defaults to ``Optional[...]`` so output stays compatible with Python 3.9.
Use ``--target-version 3.10`` or newer when your codebase already prefers PEP 604
syntax and you want Typewriter to normalize existing ``Optional[...]`` and ``Union[...]``
annotations to ``T | None`` too.

Scope and non-goals
===================

Typewriter intentionally focuses on ``None``-related annotation normalization.

It does not:

* perform broad typing cleanup beyond the current codemod rules,
* rewrite docstrings,
* infer intent beyond syntax-driven rewrites,
* replace formatters, linters, or type checkers.

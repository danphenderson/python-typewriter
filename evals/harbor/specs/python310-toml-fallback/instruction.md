# Restore Python 3.10 package-version compatibility

Typewriter declares support for Python 3.10, but importing the package currently
fails when the standard-library `tomllib` module is unavailable.

Update the package-version resolution in `typewriter/__init__.py` so it works on
Python 3.10 using the dependencies already declared by the project. Preserve the
existing resolution order:

1. Prefer installed distribution metadata.
2. Fall back to the version in `pyproject.toml`.
3. Fall back to `0.0.0` when neither source is available.

Keep the change focused and do not raise the minimum supported Python version.
Run the relevant tests before finishing.

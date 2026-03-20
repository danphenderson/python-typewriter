from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

_DISTRIBUTION_NAME = "py-typewriter-cli"

try:
    __version__ = version(_DISTRIBUTION_NAME)
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"

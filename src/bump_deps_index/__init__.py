"""Bump dependencies from an index server."""

from __future__ import annotations

from ._cli import Options, main
from ._run import run
from .version import __version__

__all__ = [
    "Options",
    "__version__",
    "main",
    "run",
]

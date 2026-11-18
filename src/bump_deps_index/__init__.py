"""Bump dependencies from an index server."""

from __future__ import annotations

__lazy_modules__ = [
    f"{__spec__.parent}._cli",  # ty: ignore[missing-union-attribute]  # imported modules have a spec
    f"{__spec__.parent}._run",  # ty: ignore[missing-union-attribute]  # imported modules have a spec
    f"{__spec__.parent}.version",  # ty: ignore[missing-union-attribute]  # imported modules have a spec
]

from ._cli import Options, main
from ._run import run
from .version import __version__

__all__ = [
    "Options",
    "__version__",
    "main",
    "run",
]

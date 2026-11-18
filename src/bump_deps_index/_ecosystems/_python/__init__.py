"""Python package index and PEP 440 bumps."""

from __future__ import annotations

__lazy_modules__ = [
    f"{__spec__.parent}._index",  # ty: ignore[missing-union-attribute]  # imported modules have a spec
    f"{__spec__.parent}._loaders",  # ty: ignore[missing-union-attribute]  # imported modules have a spec
    f"{__spec__.parent}._pep440",  # ty: ignore[missing-union-attribute]  # imported modules have a spec
]

from ._index import SimpleIndex, python_name
from ._loaders import PyProjectToml, Requirements, ScriptMetadata, SetupCfg, ToxIni, ToxToml
from ._pep440 import bump_python

__all__ = [
    "PyProjectToml",
    "Requirements",
    "ScriptMetadata",
    "SetupCfg",
    "SimpleIndex",
    "ToxIni",
    "ToxToml",
    "bump_python",
    "python_name",
]

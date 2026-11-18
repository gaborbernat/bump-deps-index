"""Package registries, version bumps and dependency files, one package per ecosystem."""

from __future__ import annotations

__lazy_modules__ = [
    f"{__spec__.parent}._registry",  # ty: ignore[missing-union-attribute]  # imported modules have a spec
    f"{__spec__.parent}._table",  # ty: ignore[missing-union-attribute]  # imported modules have a spec
    f"{__spec__.parent}.model",  # ty: ignore[missing-union-attribute]  # imported modules have a spec
]

from ._registry import get_loaders
from ._table import Ecosystem, ecosystem_table
from .model import (
    Loaded,
    Loader,
    Lookup,
    Registry,
    exclude_newer_for,
)

__all__ = [
    "Ecosystem",
    "Loaded",
    "Loader",
    "Lookup",
    "Registry",
    "ecosystem_table",
    "exclude_newer_for",
    "get_loaders",
]

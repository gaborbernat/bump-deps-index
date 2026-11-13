"""Package registries, version bumps and dependency files, one package per ecosystem."""

from __future__ import annotations

from ._registry import get_loaders
from ._table import Ecosystem, ecosystem_table
from .model import (
    Candidate,
    Candidates,
    Entry,
    HookLanguages,
    Loaded,
    Loader,
    Lookup,
    Registry,
    SingleFileLoader,
    accepted_versions,
    exclude_newer_for,
    splice,
)

__all__ = [
    "Candidate",
    "Candidates",
    "Ecosystem",
    "Entry",
    "HookLanguages",
    "Loaded",
    "Loader",
    "Lookup",
    "Registry",
    "SingleFileLoader",
    "accepted_versions",
    "ecosystem_table",
    "exclude_newer_for",
    "get_loaders",
    "splice",
]

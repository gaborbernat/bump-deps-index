"""Shared loader and candidate contracts for ecosystem implementations."""

from __future__ import annotations

from ._common import (
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
    "Entry",
    "HookLanguages",
    "Loaded",
    "Loader",
    "Lookup",
    "Registry",
    "SingleFileLoader",
    "accepted_versions",
    "exclude_newer_for",
    "splice",
]

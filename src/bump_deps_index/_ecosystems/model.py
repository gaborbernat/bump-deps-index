"""Shared loader and candidate contracts for ecosystem implementations."""

from __future__ import annotations

__lazy_modules__ = [f"{__spec__.parent}._common"]  # ty: ignore[missing-union-attribute]  # imported modules have a spec

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

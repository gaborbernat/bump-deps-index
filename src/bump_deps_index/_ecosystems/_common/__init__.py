"""Parts shared by every ecosystem: candidates, the loader contract and the loader registry."""

from __future__ import annotations

__lazy_modules__ = [
    f"{__spec__.parent}._candidates",  # ty: ignore[missing-union-attribute]  # imported modules have a spec
    f"{__spec__.parent}._loader",  # ty: ignore[missing-union-attribute]  # imported modules have a spec
    f"{__spec__.parent}._pre_commit",  # ty: ignore[missing-union-attribute]  # imported modules have a spec
    f"{__spec__.parent}._registry",  # ty: ignore[missing-union-attribute]  # imported modules have a spec
]

from ._candidates import Candidate, Candidates, Lookup, Registry, accepted_versions, exclude_newer_for
from ._loader import Entry, Loaded, Loader, SingleFileLoader, splice
from ._pre_commit import HookLanguages
from ._registry import get_loaders

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
    "get_loaders",
    "splice",
]

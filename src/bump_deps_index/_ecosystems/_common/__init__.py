"""Parts shared by every ecosystem: candidates, the loader contract and the loader registry."""

from __future__ import annotations

from ._candidates import Candidate, Candidates, Lookup, Registry, accepted_versions, exclude_newer_for
from ._loader import Entry, Loaded, Loader, SingleFileLoader, splice
from ._pre_commit import HookLanguages, PreCommitConfig
from ._registry import get_loaders

__all__ = [
    "Candidate",
    "Candidates",
    "Entry",
    "HookLanguages",
    "Loaded",
    "Loader",
    "Lookup",
    "PreCommitConfig",
    "Registry",
    "SingleFileLoader",
    "accepted_versions",
    "exclude_newer_for",
    "get_loaders",
    "splice",
]

"""HTTP session, response cache and pre-commit hook manifests."""

from __future__ import annotations

__lazy_modules__ = [f"{__spec__.parent}._hook_manifest", f"{__spec__.parent}._session"]  # ty: ignore[missing-union-attribute]  # imported modules have a spec

from ._hook_manifest import hook_languages
from ._session import Session, new_client

__all__ = [
    "Session",
    "hook_languages",
    "new_client",
]

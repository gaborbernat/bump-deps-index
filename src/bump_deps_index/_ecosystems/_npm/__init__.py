"""npm registry and semver bumps."""

from __future__ import annotations

__lazy_modules__ = [
    f"{__spec__.parent}._loaders",  # ty: ignore[missing-union-attribute]  # imported modules have a spec
    f"{__spec__.parent}._registry",  # ty: ignore[missing-union-attribute]  # imported modules have a spec
    f"{__spec__.parent}._semver",  # ty: ignore[missing-union-attribute]  # imported modules have a spec
]

from ._loaders import PackageJson
from ._registry import NpmRegistry, npm_indexes
from ._semver import bump_js, npm_name

__all__ = [
    "NpmRegistry",
    "PackageJson",
    "bump_js",
    "npm_indexes",
    "npm_name",
]

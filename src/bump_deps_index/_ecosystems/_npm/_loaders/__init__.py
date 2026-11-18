"""Loaders for the dependency files of npm projects."""

from __future__ import annotations

__lazy_modules__ = [f"{__spec__.parent}.package_json"]  # ty: ignore[missing-union-attribute]  # imported modules have a spec

from .package_json import PackageJson

__all__ = [
    "PackageJson",
]

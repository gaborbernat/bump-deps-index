"""Loaders for the dependency files of Python projects."""

from __future__ import annotations

__lazy_modules__ = [
    f"{__spec__.parent}.pyproject_toml",  # ty: ignore[missing-union-attribute]  # imported modules have a spec
    f"{__spec__.parent}.requirements",  # ty: ignore[missing-union-attribute]  # imported modules have a spec
    f"{__spec__.parent}.script_metadata",  # ty: ignore[missing-union-attribute]  # imported modules have a spec
    f"{__spec__.parent}.setup_cfg",  # ty: ignore[missing-union-attribute]  # imported modules have a spec
    f"{__spec__.parent}.tox_ini",  # ty: ignore[missing-union-attribute]  # imported modules have a spec
    f"{__spec__.parent}.tox_toml",  # ty: ignore[missing-union-attribute]  # imported modules have a spec
]

from .pyproject_toml import PyProjectToml
from .requirements import Requirements
from .script_metadata import ScriptMetadata
from .setup_cfg import SetupCfg
from .tox_ini import ToxIni
from .tox_toml import ToxToml

__all__ = [
    "PyProjectToml",
    "Requirements",
    "ScriptMetadata",
    "SetupCfg",
    "ToxIni",
    "ToxToml",
]

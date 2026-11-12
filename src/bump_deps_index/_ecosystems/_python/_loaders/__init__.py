"""Loaders for the dependency files of Python projects."""

from __future__ import annotations

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

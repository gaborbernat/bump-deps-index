from __future__ import annotations

from functools import cache

from ._base import Loader
from .pre_commit_config import PreCommitConfig
from .pyproject_toml import PyProjectToml
from .requirements import Requirements
from .setup_cfg import SetupCfg
from .tox_ini import ToxIni
from .tox_toml import ToxToml


@cache
def get_loaders() -> list[Loader]:
    """Return a list of all available loaders."""
    return [
        PreCommitConfig(),
        PyProjectToml(),
        ToxToml(),
        Requirements(),
        SetupCfg(),
        ToxIni(),
    ]


__all__ = [
    "Loader",
    "get_loaders",
]

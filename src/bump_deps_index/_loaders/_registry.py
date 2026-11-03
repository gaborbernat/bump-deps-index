from __future__ import annotations

from functools import cache
from typing import TYPE_CHECKING

from .package_json import PackageJson
from .pre_commit_config import PreCommitConfig
from .pyproject_toml import PyProjectToml
from .requirements import Requirements
from .script_metadata import ScriptMetadata
from .setup_cfg import SetupCfg
from .tox_ini import ToxIni
from .tox_toml import ToxToml

if TYPE_CHECKING:
    from ._base import Loader


@cache
def get_loaders() -> list[Loader]:
    return [
        PreCommitConfig(),
        PackageJson(),
        PyProjectToml(),
        ToxToml(),
        Requirements(),
        SetupCfg(),
        ToxIni(),
        ScriptMetadata(),
    ]


__all__ = [
    "get_loaders",
]

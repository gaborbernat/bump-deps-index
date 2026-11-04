from __future__ import annotations

from typing import TYPE_CHECKING

from bump_deps_index._ecosystems._npm._loaders.package_json import PackageJson
from bump_deps_index._ecosystems._python._loaders.pyproject_toml import PyProjectToml
from bump_deps_index._ecosystems._python._loaders.requirements import Requirements
from bump_deps_index._ecosystems._python._loaders.script_metadata import ScriptMetadata
from bump_deps_index._ecosystems._python._loaders.setup_cfg import SetupCfg
from bump_deps_index._ecosystems._python._loaders.tox_ini import ToxIni
from bump_deps_index._ecosystems._python._loaders.tox_toml import ToxToml

from ._pre_commit import PreCommitConfig

if TYPE_CHECKING:
    from ._loader import Loader
    from ._pre_commit import HookLanguages


def get_loaders(hook_languages: HookLanguages) -> list[Loader]:
    return [
        PreCommitConfig(hook_languages),
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

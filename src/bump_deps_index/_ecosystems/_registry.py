from __future__ import annotations

__lazy_modules__ = [
    f"{__spec__.parent}._common",  # ty: ignore[missing-union-attribute]  # imported modules have a spec
    f"{__spec__.parent}._npm",  # ty: ignore[missing-union-attribute]  # imported modules have a spec
    f"{__spec__.parent}._python",  # ty: ignore[missing-union-attribute]  # imported modules have a spec
]

from typing import TYPE_CHECKING

from ._common import get_loaders as common_get_loaders
from ._npm import PackageJson
from ._python import PyProjectToml, Requirements, ScriptMetadata, SetupCfg, ToxIni, ToxToml

if TYPE_CHECKING:
    from collections.abc import Callable

    from bump_deps_index.model import Parsed, UvIndexes

    from .model import HookLanguages, Loader


def get_loaders(
    hook_languages: HookLanguages, uv_indexes: Callable[[dict[str, Parsed]], tuple[UvIndexes, str | None]]
) -> list[Loader]:
    return common_get_loaders(
        hook_languages,
        [
            PackageJson(),
            PyProjectToml(),
            ToxToml(),
            Requirements(),
            SetupCfg(),
            ToxIni(),
            ScriptMetadata(uv_indexes),
        ],
    )


__all__ = [
    "get_loaders",
]

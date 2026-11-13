from __future__ import annotations

from typing import TYPE_CHECKING

from ._pre_commit import PreCommitConfig

if TYPE_CHECKING:
    from collections.abc import Iterable

    from ._loader import Loader
    from ._pre_commit import HookLanguages


def get_loaders(hook_languages: HookLanguages, loaders: Iterable[Loader]) -> list[Loader]:
    return [PreCommitConfig(hook_languages), *loaders]


__all__ = [
    "get_loaders",
]

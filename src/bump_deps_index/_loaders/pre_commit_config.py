from __future__ import annotations

from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, NotRequired, TypedDict, cast

from yaml import safe_load as load_yaml

from bump_deps_index._spec import PkgType

from ._base import Loader

if TYPE_CHECKING:
    from collections.abc import Iterator


class Hook(TypedDict):
    id: str
    args: NotRequired[list[str]]
    additional_dependencies: NotRequired[list[str]]


class RepoConfig(TypedDict):
    repo: str
    rev: NotRequired[str]
    hooks: list[Hook]


class PreCommitConfig(Loader):
    _filename: ClassVar[str] = ".pre-commit-config.yaml"

    @cached_property
    def files(self) -> Iterator[Path]:
        if (path := Path.cwd() / self._filename).exists():
            yield path

    def supports(self, filename: Path) -> bool:
        return filename.name == self._filename

    def load(self, filename: Path, *, pre_release: bool | None) -> Iterator[tuple[str, PkgType, bool]]:  # noqa: PLR6301
        with filename.open("rt", encoding="utf-8") as file_handler:
            cfg = load_yaml(file_handler)
        pre = True if pre_release is None else pre_release
        repos = cast("list[RepoConfig]", cfg.get("repos", []) if isinstance(cfg, dict) else [])
        for repo in repos:
            for hook in repo["hooks"]:
                for pkg in hook.get("additional_dependencies", []):
                    yield pkg, PkgType.JS if "@" in pkg else PkgType.PYTHON, pre


__all__ = [
    "PreCommitConfig",
]

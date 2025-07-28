from __future__ import annotations

from configparser import RawConfigParser
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from bump_deps_index._spec import PkgType

from ._base import Loader

if TYPE_CHECKING:
    from collections.abc import Iterator


class NoTransformConfigParser(RawConfigParser):
    def optionxform(self, optionstr: str) -> str:  # noqa: PLR6301
        """Disable default lower-casing."""
        return optionstr


class SetupCfg(Loader):
    _filename: ClassVar[str] = "setup.cfg"

    @cached_property
    def files(self) -> Iterator[Path]:
        if (path := Path.cwd() / self._filename).exists():
            yield path

    def supports(self, filename: Path) -> bool:
        return filename.name == self._filename

    def load(self, filename: Path, *, pre_release: bool | None) -> Iterator[tuple[str, PkgType, bool]]:
        cfg = NoTransformConfigParser()
        cfg.read(filename)
        if cfg.has_section("options"):
            yield from self._generate(cfg["options"].get("install_requires", "").split("\n"), pkg_type=PkgType.PYTHON)
        pre = False if pre_release is None else pre_release
        if cfg.has_section("options.extras_require"):
            for group in cfg["options.extras_require"].values():
                yield from self._generate(group.split("\n"), pkg_type=PkgType.PYTHON, pre_release=pre)


__all__ = [
    "SetupCfg",
]

from __future__ import annotations

import re
from configparser import RawConfigParser
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from typing_extensions import override

from bump_deps_index._spec import PkgType

from ._base import Loader

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

    from ._base import Entry


class NoTransformConfigParser(RawConfigParser):
    @override
    def optionxform(self, optionstr: str) -> str:
        """Preserve dependency names because package indexes treat punctuation as significant."""
        return optionstr


class SetupCfg(Loader):
    _filename: ClassVar[str] = "setup.cfg"

    @property
    def files(self) -> Iterator[Path]:
        if (path := Path.cwd() / self._filename).exists():
            yield path

    def supports(self, filename: Path) -> bool:
        return filename.name == self._filename

    def _update_text(self, text: str, changes: Mapping[str, str]) -> str:
        # configparser hands every `[DEFAULT]` key to `[options.extras_require]`, which reads each key as an extra
        extras = re.search(r"^\[options\.extras_require\]", text, re.MULTILINE) is not None
        return self._update_ini(
            text,
            changes,
            lambda section, key: (
                (section in {"options", "DEFAULT"} and key == "install_requires")
                or section == "options.extras_require"
                or (section == "DEFAULT" and extras)
            ),
        )

    def load(self, filename: Path, *, pre_release: bool | None) -> Iterator[Entry]:
        cfg = NoTransformConfigParser()
        cfg.read(filename)
        pre = False if pre_release is None else pre_release
        if cfg.has_section("options"):
            yield from self._generate(
                cfg["options"].get("install_requires", "").split("\n"),
                pkg_type=PkgType.PYTHON,
                pre_release=pre,
            )
        if cfg.has_section("options.extras_require"):
            for group in cfg["options.extras_require"].values():
                yield from self._generate(group.split("\n"), pkg_type=PkgType.PYTHON, pre_release=pre)


__all__ = [
    "SetupCfg",
]

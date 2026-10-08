from __future__ import annotations

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


class ToxIni(Loader):
    _filename: ClassVar[str] = "tox.ini"

    @property
    def files(self) -> Iterator[Path]:
        if (path := Path.cwd() / self._filename).exists():
            yield path

    def supports(self, filename: Path) -> bool:
        return filename.name == self._filename

    def _update_text(self, text: str, changes: Mapping[str, str]) -> str:
        return self._update_ini(
            text,
            changes,
            # configparser hands a `[DEFAULT]` key to every section that lacks it
            lambda section, key: (
                (section in {"tox", "DEFAULT"} and key == "requires")
                or ((section.startswith("testenv") or section == "DEFAULT") and key == "deps")
            ),
        )

    def load(self, filename: Path, *, pre_release: bool | None) -> Iterator[Entry]:
        cfg = NoTransformConfigParser()
        cfg.read(filename)
        pre = False if pre_release is None else pre_release
        for section in cfg.sections():
            if section.startswith("testenv"):
                values = self._ini_values(cfg[section].get("deps", ""))
                yield from self._generate(
                    [self._strip_factor(value) for value in values],
                    pkg_type=PkgType.PYTHON,
                    pre_release=pre,
                )
            elif section == "tox":
                yield from self._generate(
                    self._ini_values(cfg[section].get("requires", "")), pkg_type=PkgType.PYTHON, pre_release=pre
                )

    @classmethod
    def _ini_values(cls, value: str) -> list[str]:
        # tox drops a `#` comment after a requirement, and expands `{...}` and `-r` lines itself
        return [line for raw in value.split("\n") if (line := cls._split_comment(raw)[0].strip())[:1] not in {"{", "-"}]


__all__ = [
    "ToxIni",
]

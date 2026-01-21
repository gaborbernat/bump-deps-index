from __future__ import annotations

from configparser import RawConfigParser
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from bump_deps_index._spec import PkgType

from ._base import Loader

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping


class NoTransformConfigParser(RawConfigParser):
    def optionxform(self, optionstr: str) -> str:  # noqa: PLR6301
        """Disable default lower-casing."""
        return optionstr


class ToxIni(Loader):
    _filename: ClassVar[str] = "tox.ini"

    @cached_property
    def files(self) -> Iterator[Path]:
        if (path := Path.cwd() / self._filename).exists():
            yield path

    def supports(self, filename: Path) -> bool:
        return filename.name == self._filename

    def update_file(self, filename: Path, changes: Mapping[str, str]) -> None:
        lines = filename.read_text(encoding="utf-8").split("\n")
        result: list[str] = []
        in_deps_section = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("["):
                in_deps_section = stripped.startswith("[testenv") or stripped == "[tox]"
            elif in_deps_section and stripped and not stripped.startswith("#") and stripped[:1] not in {"-", "{"}:
                line = self._apply_changes(line, changes)  # noqa: PLW2901
            result.append(line)
        filename.write_text("\n".join(result), encoding="utf-8")

    def load(self, filename: Path, *, pre_release: bool | None) -> Iterator[tuple[str, PkgType, bool]]:
        cfg = NoTransformConfigParser()
        cfg.read(filename)
        pre = False if pre_release is None else pre_release
        for section in cfg.sections():
            if section.startswith("testenv"):
                values = [i for i in cfg[section].get("deps", "").split("\n") if i.strip()[:1] not in {"{", "-"}]
                yield from self._generate(values, pkg_type=PkgType.PYTHON, pre_release=pre)
            elif section == "tox":
                values = [i for i in cfg[section].get("requires", "").split("\n") if i.strip()[:1] not in {"{", "-"}]
                yield from self._generate(values, pkg_type=PkgType.PYTHON, pre_release=pre)


__all__ = [
    "ToxIni",
]

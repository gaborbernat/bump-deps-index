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
        lines = text.split("\n")
        result: list[str] = []
        section = ""
        dependency_key = ""
        for line in lines:
            stripped = line.strip()
            key_line = False
            if stripped.startswith("["):
                section = stripped.strip("[]")
                dependency_key = ""
            elif stripped and not line[:1].isspace() and "=" in line:
                dependency_key = line.partition("=")[0].strip()
                key_line = True
            update = (section == "tox" and dependency_key == "requires") or (
                section.startswith("testenv") and dependency_key == "deps"
            )
            if not update:
                result.append(line)
            elif key_line:
                result.append(self._replace_key_line(line, changes))
            else:
                result.append(self._replace_requirement_line(line, changes))
        return "\n".join(result)

    def load(self, filename: Path, *, pre_release: bool | None) -> Iterator[Entry]:
        cfg = NoTransformConfigParser()
        cfg.read(filename)
        pre = False if pre_release is None else pre_release
        for section in cfg.sections():
            if section.startswith("testenv"):
                values = [i for i in cfg[section].get("deps", "").split("\n") if i.strip()[:1] not in {"{", "-"}]
                yield from self._generate(
                    [self._strip_factor(value) for value in values],
                    pkg_type=PkgType.PYTHON,
                    pre_release=pre,
                )
            elif section == "tox":
                values = [i for i in cfg[section].get("requires", "").split("\n") if i.strip()[:1] not in {"{", "-"}]
                yield from self._generate(values, pkg_type=PkgType.PYTHON, pre_release=pre)


__all__ = [
    "ToxIni",
]

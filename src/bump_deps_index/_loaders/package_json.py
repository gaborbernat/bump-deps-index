from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Final

from bump_deps_index._spec import PkgType

from ._base import Loader

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

    from ._base import Entry

# skip `peerDependencies`, a raised lower bound there narrows what you declare compatible
_SECTIONS: Final = ("dependencies", "devDependencies", "optionalDependencies")
_SECTION: Final = re.compile(rf'"(?:{"|".join(_SECTIONS)})"\s*:\s*\{{[^{{}}]*\}}')


class PackageJson(Loader):
    _filename: ClassVar[str] = "package.json"

    @property
    def files(self) -> Iterator[Path]:
        if (path := Path.cwd() / self._filename).exists():
            yield path

    def supports(self, filename: Path) -> bool:
        return filename.name == self._filename

    @staticmethod
    def _update_text(text: str, changes: Mapping[str, str]) -> str:
        return _SECTION.sub(lambda section: _replace_ranges(section[0], changes), text)

    def load(self, filename: Path, *, pre_release: bool | None) -> Iterator[Entry]:
        with filename.open(encoding="utf-8") as file_handler:
            cfg = json.load(file_handler)
        if not isinstance(cfg, dict):
            return
        yield from self._generate(
            [
                f"{name}@{wanted}"
                for section in _SECTIONS
                for name, wanted in cfg.get(section, {}).items()
                # skip aliases, paths, URLs and workspace links; the registry has no version for them
                if ":" not in wanted and "/" not in wanted
            ],
            pkg_type=PkgType.JS,
            pre_release=False if pre_release is None else pre_release,
        )


def _replace_ranges(section: str, changes: Mapping[str, str]) -> str:
    for spec, updated in changes.items():
        at = spec.find("@", 1)
        pattern = re.compile(rf'(?P<key>"{re.escape(spec[:at])}"\s*:\s*"){re.escape(spec[at + 1 :])}"')
        section = pattern.sub(lambda match, wanted=updated[at + 1 :]: f'{match["key"]}{wanted}"', section)
    return section


__all__ = [
    "PackageJson",
]

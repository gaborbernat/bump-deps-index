from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from typing_extensions import override

from bump_deps_index._spec import PkgType

from ._base import Entry, SingleFileLoader
from ._ini import ini_values, read_ini, update_ini
from ._lines import strip_factor

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping
    from pathlib import Path


class ToxIni(SingleFileLoader):
    filename: ClassVar[str] = "tox.ini"

    @override
    def load(self, filename: Path) -> Iterator[Entry]:
        cfg = read_ini(filename)
        for section in cfg.sections():
            if section.startswith("testenv"):
                values = [strip_factor(value) for value in ini_values(cfg[section].get("deps", ""))]
            elif section == "tox":
                values = ini_values(cfg[section].get("requires", ""))
            else:
                continue
            # tox expands `{...}` substitutions and `-r` lines itself; check after removing a factor such as `{py311}:`
            yield from (Entry(value, PkgType.PYTHON) for value in values if value[:1] not in {"{", "-"})

    @override
    def _update_text(self, filename: Path, text: str, changes: Mapping[str, str]) -> str:
        return update_ini(
            text,
            changes,
            # configparser copies a `[DEFAULT]` key into each section that lacks the key
            lambda section, key: (
                (section in {"tox", "DEFAULT"} and key == "requires")
                or ((section.startswith("testenv") or section == "DEFAULT") and key == "deps")
            ),
        )


__all__ = [
    "ToxIni",
]

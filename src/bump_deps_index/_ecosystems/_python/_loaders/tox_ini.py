from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from typing_extensions import override

from bump_deps_index.model import PkgType

from ...model import (  # ruff: ignore[relative-imports]  # shared contracts belong to the ecosystem owner
    Entry,
    Loaded,
    SingleFileLoader,
)
from ._ini import ini_values, read_ini, update_ini
from ._lines import strip_factor

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path


class ToxIni(SingleFileLoader):
    filename: ClassVar[str] = "tox.ini"

    @override
    def load(self, filename: Path) -> Loaded:
        cfg = read_ini(filename)
        entries: list[Entry] = []
        for section in cfg.sections():
            if section.startswith("testenv"):
                values = [strip_factor(value) for value in ini_values(cfg[section].get("deps", ""))]
            elif section == "tox":
                values = ini_values(cfg[section].get("requires", ""))
            else:
                continue
            # tox expands `{...}` substitutions and `-r` lines itself; check after removing a factor such as `{py311}:`
            entries.extend(
                Entry(spec=value, pkg_type=PkgType.PYTHON) for value in values if value[:1] not in {"{", "-"}
            )
        return Loaded(entries=entries, rewrite=self._update_text)

    @staticmethod
    def _update_text(text: str, changes: Mapping[str, str]) -> str:
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

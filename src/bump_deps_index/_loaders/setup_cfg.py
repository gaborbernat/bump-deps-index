from __future__ import annotations

import re
from typing import TYPE_CHECKING, ClassVar

from typing_extensions import override

from bump_deps_index._spec import PkgType

from ._base import Entry, SingleFileLoader
from ._ini import ini_values, read_ini, update_ini

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping
    from pathlib import Path


class SetupCfg(SingleFileLoader):
    filename: ClassVar[str] = "setup.cfg"

    @override
    def load(self, filename: Path) -> Iterator[Entry]:
        cfg = read_ini(filename)
        groups = [
            *([cfg["options"].get("install_requires", "")] if cfg.has_section("options") else []),
            *(cfg["options.extras_require"].values() if cfg.has_section("options.extras_require") else []),
        ]
        for group in groups:
            yield from (Entry(value, PkgType.PYTHON) for value in ini_values(group))

    @override
    def _update_text(self, filename: Path, text: str, changes: Mapping[str, str]) -> str:
        # configparser copies the `[DEFAULT]` keys into `[options.extras_require]`, which reads each key as an extra
        extras = re.search(r"^\[options\.extras_require\]", text, re.MULTILINE) is not None
        return update_ini(
            text,
            changes,
            lambda section, key: (
                (section in {"options", "DEFAULT"} and key == "install_requires")
                or section == "options.extras_require"
                or (section == "DEFAULT" and extras)
            ),
        )


__all__ = [
    "SetupCfg",
]

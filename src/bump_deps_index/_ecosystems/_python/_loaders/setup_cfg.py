from __future__ import annotations

import re
from typing import TYPE_CHECKING, ClassVar, Final

from typing_extensions import override

from bump_deps_index.model import PkgType

from ...model import (  # ruff: ignore[relative-imports]  # shared contracts belong to the ecosystem owner
    Entry,
    Loaded,
    SingleFileLoader,
)
from ._ini import ini_values, read_ini, update_ini

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path


_UPDATE_TEXT_PATTERN: Final[re.Pattern[str]] = re.compile(r"^\[options\.extras_require\]", re.MULTILINE)


class SetupCfg(SingleFileLoader):
    filename: ClassVar[str] = "setup.cfg"

    @override
    def load(self, filename: Path) -> Loaded:
        cfg = read_ini(filename)
        groups = [
            *([cfg["options"].get("install_requires", "")] if cfg.has_section("options") else []),
            *(cfg["options.extras_require"].values() if cfg.has_section("options.extras_require") else []),
        ]
        return Loaded(
            entries=[
                Entry(spec=value, pkg_type=PkgType.PYTHON, group="project")
                for group in groups
                for value in ini_values(group)
            ],
            rewrite=self._update_text,
        )

    @staticmethod
    def _update_text(text: str, changes: Mapping[str, str]) -> str:
        # configparser copies the `[DEFAULT]` keys into `[options.extras_require]`, which reads each key as an extra
        extras = _UPDATE_TEXT_PATTERN.search(text) is not None
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

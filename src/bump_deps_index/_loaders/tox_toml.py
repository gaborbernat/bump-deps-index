from __future__ import annotations

import re
from functools import cached_property
from pathlib import Path
from tomllib import load as load_toml
from typing import TYPE_CHECKING, ClassVar

from bump_deps_index._spec import PkgType

from ._base import Loader

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping
    from typing import TypeAlias

    TomlValue: TypeAlias = "str | int | float | bool | list[TomlValue] | dict[str, TomlValue] | None"

_NESTED: frozenset[str] = frozenset({"env", "env_base"})


class ToxToml(Loader):
    _filename: ClassVar[str] = "tox.toml"

    @cached_property
    def files(self) -> Iterator[Path]:
        if (path := Path.cwd() / self._filename).exists():
            yield path  # pragma: no cover # false positive

    def supports(self, filename: Path) -> bool:
        return filename.name == self._filename

    def update_file(self, filename: Path, changes: Mapping[str, str]) -> None:
        lines = filename.read_text(encoding="utf-8").split("\n")
        result: list[str] = []
        in_deps_section = False
        bracket_depth = 0
        deps_pattern = re.compile(r"^(requires|deps)\s*=\s*\[")
        for line in lines:
            stripped = line.strip()
            if deps_pattern.match(stripped):
                in_deps_section = True
                bracket_depth = stripped.count("[") - stripped.count("]")
            elif in_deps_section:
                bracket_depth += stripped.count("[") - stripped.count("]")
            if in_deps_section:
                line = self._apply_changes(line, changes)  # noqa: PLW2901
            result.append(line)
            if in_deps_section and bracket_depth == 0:
                in_deps_section = False
        filename.write_text("\n".join(result), encoding="utf-8")

    def load(self, filename: Path, *, pre_release: bool | None) -> Iterator[tuple[str, PkgType, bool]]:
        pre = False if pre_release is None else pre_release
        with filename.open("rb") as file_handler:
            cfg: dict[str, TomlValue] = load_toml(file_handler)
        yield from self._generate(self._specs(cfg.get("requires")), pkg_type=PkgType.PYTHON, pre_release=pre)
        yield from self._extract_deps(cfg, pre_release=pre)

    def _extract_deps(self, cfg: dict[str, TomlValue], *, pre_release: bool) -> Iterator[tuple[str, PkgType, bool]]:
        for key, section in cfg.items():
            if not isinstance(section, dict):
                continue
            yield from self._deps_from_section(section, pre_release=pre_release)
            if key in _NESTED:
                for env_section in section.values():
                    if isinstance(env_section, dict):
                        yield from self._deps_from_section(env_section, pre_release=pre_release)

    def _deps_from_section(
        self, section: dict[str, TomlValue], *, pre_release: bool
    ) -> Iterator[tuple[str, PkgType, bool]]:
        yield from self._generate(self._specs(section.get("deps")), pkg_type=PkgType.PYTHON, pre_release=pre_release)

    @classmethod
    def _specs(cls, value: TomlValue) -> list[str]:
        """
        Collect requirement strings from a tox ``requires``/``deps`` value.

        tox native TOML lets a list hold inline-table substitutions alongside plain strings. A spec can only live in
        the branches a substitution may fall back to: ``if`` (``then``/``else``), ``posargs``/``env``/``glob``
        (``default``); these are followed transitively so nested substitutions are bumped too. ``ref`` points at
        another config key bumped where it is defined, so it carries no inline spec. Flag entries (``-r ...``) and
        ``{...}`` references are skipped, matching the tox.ini loader.
        """
        found: list[str] = []
        cls._collect(value, found)
        return found

    @classmethod
    def _collect(cls, value: TomlValue, found: list[str]) -> None:
        if isinstance(value, str):
            if value and value[0] not in {"-", "{"}:
                found.append(value)
        elif isinstance(value, list):
            for item in value:
                cls._collect(item, found)
        elif isinstance(value, dict):
            replace = value.get("replace")
            if replace == "if":
                cls._collect(value.get("then"), found)
                cls._collect(value.get("else"), found)
            elif replace in {"posargs", "env", "glob"}:
                cls._collect(value.get("default"), found)


__all__ = [
    "ToxToml",
]

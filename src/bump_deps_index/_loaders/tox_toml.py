from __future__ import annotations

import re
from functools import cached_property
from pathlib import Path
from tomllib import load as load_toml
from typing import TYPE_CHECKING, Any, ClassVar, cast

from bump_deps_index._spec import PkgType

from ._base import Loader

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

_Section = dict[str, object]


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
            cfg = load_toml(file_handler)
        yield from self._generate(cfg.get("requires", []), pkg_type=PkgType.PYTHON, pre_release=pre)
        yield from self._extract_deps(cfg, pre_release=pre)

    def _extract_deps(self, cfg: dict[str, Any], *, pre_release: bool) -> Iterator[tuple[str, PkgType, bool]]:
        for key, section in cfg.items():
            if not isinstance(section, dict):
                continue
            yield from self._deps_from_section(cast("_Section", section), pre_release=pre_release)
            if key == "env":
                for env_section in cast("dict[str, _Section]", section).values():
                    yield from self._deps_from_section(env_section, pre_release=pre_release)

    def _deps_from_section(self, section: _Section, *, pre_release: bool) -> Iterator[tuple[str, PkgType, bool]]:
        deps: object = section.get("deps")
        if isinstance(deps, list):
            yield from self._generate(
                [d for d in cast("list[str]", deps) if not d.startswith("-")],
                pkg_type=PkgType.PYTHON,
                pre_release=pre_release,
            )


__all__ = [
    "ToxToml",
]

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


class PyProjectToml(Loader):
    _filename: ClassVar[str] = "pyproject.toml"

    @cached_property
    def files(self) -> Iterator[Path]:
        if (path := Path.cwd() / self._filename).exists():
            yield path

    def supports(self, filename: Path) -> bool:
        return filename.name == self._filename

    def update_file(self, filename: Path, changes: Mapping[str, str]) -> None:  # noqa: PLR6301
        """Update only dependency sections in pyproject.toml."""
        content = filename.read_text(encoding="utf-8")
        lines = content.split("\n")
        in_deps_section = False
        bracket_depth = 0
        result_lines: list[str] = []
        current_section = None
        section_pattern = re.compile(r"^\[(.*?)\]")
        deps_pattern = re.compile(r"^(requires|dependencies|optional-dependencies\.[a-z_-]+|[a-z_-]+)\s*=\s*\[")
        for line in lines:
            stripped = line.strip()
            if section_match := section_pattern.match(stripped):
                current_section = section_match.group(1)
            if match := deps_pattern.match(stripped):
                key = match.group(1)
                if (
                    key in {"requires", "dependencies"}
                    or key.startswith("optional-dependencies.")
                    or current_section == "dependency-groups"
                ):
                    in_deps_section = True
                    bracket_depth = stripped.count("[") - stripped.count("]")
            elif in_deps_section:
                bracket_depth += stripped.count("[") - stripped.count("]")
            if in_deps_section:
                for src, dst in changes.items():
                    line = line.replace(src, dst)  # noqa: PLW2901
            result_lines.append(line)
            if in_deps_section and bracket_depth == 0:
                in_deps_section = False
        filename.write_text("\n".join(result_lines), encoding="utf-8")

    def load(self, filename: Path, *, pre_release: bool | None) -> Iterator[tuple[str, PkgType, bool]]:
        with filename.open("rb") as file_handler:
            cfg = load_toml(file_handler)
        yield from self._generate(cfg.get("build-system", {}).get("requires", []), pkg_type=PkgType.PYTHON)
        yield from self._generate(cfg.get("project", {}).get("dependencies", []), pkg_type=PkgType.PYTHON)
        pre = False if pre_release is None else pre_release
        for entries in cfg.get("project", {}).get("optional-dependencies", {}).values():
            yield from self._generate(entries, pkg_type=PkgType.PYTHON, pre_release=pre)
        for values in cfg.get("dependency-groups", {}).values():
            yield from self._generate([v for v in values if not isinstance(v, dict)], pkg_type=PkgType.PYTHON)


__all__ = [
    "PyProjectToml",
]

from __future__ import annotations

import re
from pathlib import Path
from tomllib import load as load_toml
from typing import TYPE_CHECKING, ClassVar

from bump_deps_index._spec import PkgType

from ._base import Loader

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping


class PyProjectToml(Loader):
    _filename: ClassVar[str] = "pyproject.toml"

    @property
    def files(self) -> Iterator[Path]:
        if (path := Path.cwd() / self._filename).exists():
            yield path

    def supports(self, filename: Path) -> bool:
        return filename.name == self._filename

    def update_file(self, filename: Path, changes: Mapping[str, str]) -> None:
        content = filename.read_text(encoding="utf-8")
        lines = content.split("\n")
        in_deps_section = False
        bracket_depth = 0
        result_lines: list[str] = []
        current_section = ""
        section_pattern = re.compile(r"^\[(?P<section>[^]]+)]")
        key_pattern = re.compile(r"^(?P<key>(?:[^=\s]|\s(?!\s*=))+?)\s*=\s*\[")
        for line in lines:
            stripped = line.strip()
            if section_match := section_pattern.match(stripped):
                current_section = section_match["section"]
            if match := key_pattern.match(stripped):
                key = match["key"].strip("\"'")
                project_dependency = current_section == "project" and (
                    key == "dependencies" or key.startswith("optional-dependencies.")
                )
                if (
                    (current_section == "build-system" and key == "requires")
                    or project_dependency
                    or current_section in {"project.optional-dependencies", "dependency-groups"}
                ):
                    in_deps_section = True
                    bracket_depth = stripped.count("[") - stripped.count("]")
            elif in_deps_section:
                bracket_depth += stripped.count("[") - stripped.count("]")
            result_lines.append(self._replace_quoted(line, changes) if in_deps_section else line)
            if in_deps_section and bracket_depth == 0:
                in_deps_section = False
        filename.write_text("\n".join(result_lines), encoding="utf-8")

    def load(self, filename: Path, *, pre_release: bool | None) -> Iterator[tuple[str, PkgType, bool]]:
        with filename.open("rb") as file_handler:
            cfg = load_toml(file_handler)
        pre = False if pre_release is None else pre_release
        yield from self._generate(
            cfg.get("build-system", {}).get("requires", []), pkg_type=PkgType.PYTHON, pre_release=pre
        )
        yield from self._generate(
            cfg.get("project", {}).get("dependencies", []), pkg_type=PkgType.PYTHON, pre_release=pre
        )
        for entries in cfg.get("project", {}).get("optional-dependencies", {}).values():
            yield from self._generate(entries, pkg_type=PkgType.PYTHON, pre_release=pre)
        for values in cfg.get("dependency-groups", {}).values():
            yield from self._generate(
                [value for value in values if not isinstance(value, dict)],
                pkg_type=PkgType.PYTHON,
                pre_release=pre,
            )


__all__ = [
    "PyProjectToml",
]

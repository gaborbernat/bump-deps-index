from __future__ import annotations

import re
from pathlib import Path
from tomllib import load as load_toml
from typing import TYPE_CHECKING, ClassVar, Final

from bump_deps_index._spec import PkgType

from ._base import Loader

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

    from ._base import Entry

_TABLE: Final = re.compile(r"^\[(?P<table>[^]]+)]")
_KEY: Final = re.compile(r"^(?P<key>[^=]*)=\s*[\[{]")
_DEPENDENCY_KEYS: Final = frozenset({
    "build-system.requires",
    "dependency-groups",
    "project.dependencies",
    "project.optional-dependencies",
    "tool.uv.dev-dependencies",
})


class PyProjectToml(Loader):
    _filename: ClassVar[str] = "pyproject.toml"

    @property
    def files(self) -> Iterator[Path]:
        if (path := Path.cwd() / self._filename).exists():
            yield path

    def supports(self, filename: Path) -> bool:
        return filename.name == self._filename

    def _update_text(self, text: str, changes: Mapping[str, str]) -> str:
        result_lines: list[str] = []
        table = string_quote = ""
        bracket_depth = 0
        for line in text.split("\n"):
            stripped = line.strip()
            if update := bracket_depth > 0:
                bracket_depth += self._bracket_delta(stripped)
            elif string_quote:  # skip the text of a multi-line string, it may hold lines that look like keys
                string_quote = "" if string_quote in stripped else string_quote
            elif header := _TABLE.match(stripped):
                table = _dotted(header["table"])
            elif (match := _KEY.match(stripped)) and _is_dependency_key(f"{table}.{_dotted(match['key'])}".lstrip(".")):
                update = True
                bracket_depth = self._bracket_delta(stripped)
            else:
                string_quote = next((quote for quote in ('"""', "'''") if stripped.count(quote) % 2), "")
            result_lines.append(self._replace_quoted(line, changes) if update else line)
        return "\n".join(result_lines)

    def load(self, filename: Path, *, pre_release: bool | None) -> Iterator[Entry]:
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
        yield from self._generate(
            cfg.get("tool", {}).get("uv", {}).get("dev-dependencies", []), pkg_type=PkgType.PYTHON, pre_release=pre
        )
        for values in cfg.get("dependency-groups", {}).values():
            yield from self._generate(
                [value for value in values if not isinstance(value, dict)],
                pkg_type=PkgType.PYTHON,
                pre_release=pre,
            )


def _dotted(key: str) -> str:
    return ".".join(part.strip(" \"'") for part in key.split("."))


def _is_dependency_key(key: str) -> bool:
    return key in _DEPENDENCY_KEYS or key.startswith(("project.optional-dependencies.", "dependency-groups."))


__all__ = [
    "PyProjectToml",
]

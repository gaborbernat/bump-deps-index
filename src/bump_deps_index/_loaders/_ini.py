from __future__ import annotations

import re
from configparser import RawConfigParser
from typing import TYPE_CHECKING, Final

from typing_extensions import override

from ._lines import replace_requirement_line, split_comment

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from pathlib import Path

# configparser splits a key line at its first `=` or `:`
_KEY: Final[re.Pattern[str]] = re.compile(r"^(?P<key>[^=:]*)[=:]")
_SECTION: Final[re.Pattern[str]] = re.compile(r"^\[(?P<header>.+)\]")


def read_ini(filename: Path) -> RawConfigParser:
    cfg = _NoTransformConfigParser()
    cfg.read(filename, encoding="utf-8")
    return cfg


class _NoTransformConfigParser(RawConfigParser):
    @override
    def optionxform(self, optionstr: str) -> str:
        """Preserve dependency names because package indexes treat punctuation as significant."""
        return optionstr


def ini_values(value: str) -> list[str]:
    # tox and setuptools drop a `#` comment after a value
    return [line for raw in value.split("\n") if (line := split_comment(raw)[0].strip())]


def update_ini(text: str, changes: Mapping[str, str], wanted: Callable[[str, str], bool]) -> str:
    # follow configparser: an indented line continues the open key, blank and comment lines keep it open
    result: list[str] = []
    section = key = ""
    key_indent = 0
    for line in text.split("\n"):
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if not stripped or stripped[0] in {"#", ";"}:
            result.append(line)
        elif key and indent > key_indent:
            result.append(replace_requirement_line(line, changes) if wanted(section, key) else line)
        elif header := _SECTION.match(stripped):
            section, key = header["header"], ""
            result.append(line)
        else:
            key, key_indent = re.split(r"[=:]", stripped, maxsplit=1)[0].strip(), indent
            result.append(_replace_key_line(line, changes) if wanted(section, key) else line)
    return "\n".join(result)


def _replace_key_line(line: str, changes: Mapping[str, str]) -> str:
    value = _KEY.sub("", line, count=1)
    return f"{line[: len(line) - len(value)]}{replace_requirement_line(value, changes)}"


__all__ = [
    "ini_values",
    "read_ini",
    "update_ini",
]

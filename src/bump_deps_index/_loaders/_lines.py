from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Mapping

# match the factor shape to skip the colons inside URL requirements
_FACTOR: Final[re.Pattern[str]] = re.compile(
    r"^(?P<prefix>[\w!{}.-]+(?:\s*,\s*[\w!{}.-]+)*\s*:\s*)(?P<requirement>\S.*)$"
)


def replace_requirement_line(line: str, changes: Mapping[str, str]) -> str:
    prefix = line[: len(line) - len(line.lstrip())]
    value_with_spacing, suffix = split_comment(line[len(prefix) :])
    value = value_with_spacing.rstrip()
    requirement = value.removesuffix("\\").rstrip()
    if requirement in changes:
        updated = changes[requirement]
    elif (factor := _FACTOR.match(requirement)) and factor["requirement"] in changes:
        updated = f"{factor['prefix']}{changes[factor['requirement']]}"
    else:
        return line
    return f"{prefix}{updated}{value[len(requirement) :]}{value_with_spacing[len(value) :]}{suffix}"


def split_comment(value: str) -> tuple[str, str]:
    quote = ""
    for index, character in enumerate(value):
        if character in {"'", '"'} and (not quote or quote == character):
            quote = "" if quote == character else character
        elif character == "#" and not quote and index and value[index - 1].isspace():
            start = index - 1
            while start and value[start - 1].isspace():
                start -= 1
            return value[:start], value[start:]
    return value, ""


def strip_factor(value: str) -> str:
    return factor["requirement"] if (factor := _FACTOR.match(value.strip())) else value.strip()


__all__ = [
    "replace_requirement_line",
    "split_comment",
    "strip_factor",
]

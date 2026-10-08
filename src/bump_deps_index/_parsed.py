from __future__ import annotations

from typing import TypeAlias

Parsed: TypeAlias = str | int | float | bool | list["Parsed"] | dict[str, "Parsed"] | None


def table(value: Parsed, *keys: str) -> dict[str, Parsed]:
    # read a mistyped field as a missing one, so one malformed field does not stop the run
    for key in keys:
        value = value.get(key) if isinstance(value, dict) else None
    return value if isinstance(value, dict) else {}


def mappings(value: Parsed) -> list[dict[str, Parsed]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def strings(value: Parsed) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


__all__ = [
    "Parsed",
    "mappings",
    "strings",
    "table",
]

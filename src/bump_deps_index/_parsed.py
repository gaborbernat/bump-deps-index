from __future__ import annotations

import os
import re
from typing import Final, TypeAlias

Parsed: TypeAlias = str | int | float | bool | list["Parsed"] | dict[str, "Parsed"] | None

_ENV_REFERENCE: Final[re.Pattern[str]] = re.compile(r"\$\{(?P<name>\w+)\}")


def table(value: Parsed, *keys: str) -> dict[str, Parsed]:
    # read a mistyped field as a missing one, so one malformed field does not stop the run
    for key in keys:
        value = value.get(key) if isinstance(value, dict) else None
    return value if isinstance(value, dict) else {}


def mappings(value: Parsed) -> list[dict[str, Parsed]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def strings(value: Parsed) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def expand_env(text: str) -> str:
    # pip and npm substitute `${NAME}` from the environment in their config and requirements files
    return _ENV_REFERENCE.sub(lambda match: os.environ.get(match["name"], ""), text)


__all__ = [
    "Parsed",
    "expand_env",
    "mappings",
    "strings",
    "table",
]

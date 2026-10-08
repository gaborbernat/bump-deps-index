from __future__ import annotations

from typing import TYPE_CHECKING, TypeAlias, TypeVar

if TYPE_CHECKING:
    from httpx import Response

Parsed: TypeAlias = str | int | float | bool | list["Parsed"] | dict[str, "Parsed"] | None
_JsonField = TypeVar("_JsonField", list[Parsed], dict[str, Parsed])


def table(value: Parsed, *keys: str) -> dict[str, Parsed]:
    # read a mistyped field as a missing one, so one malformed field does not stop the run
    for key in keys:
        value = value.get(key) if isinstance(value, dict) else None
    return value if isinstance(value, dict) else {}


def mappings(value: Parsed) -> list[dict[str, Parsed]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def strings(value: Parsed) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def json_field(response: Response, name: str, kind: type[_JsonField]) -> _JsonField:
    if not isinstance(payload := response.json(), dict) or not isinstance(value := payload.get(name), kind):
        msg = f"{response.url} has no {name} {kind.__name__}"
        raise TypeError(msg)
    return value


__all__ = [
    "Parsed",
    "json_field",
    "mappings",
    "strings",
    "table",
]

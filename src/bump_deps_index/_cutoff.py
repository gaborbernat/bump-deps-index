from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bump_deps_index._parsed import Parsed


def parse_exclude_newer(value: str, now: datetime) -> datetime:
    text = value.strip()
    # no calendar units, which have no fixed length; uv rejects them as well
    iso = re.fullmatch(
        r"""
        P                             # the duration designator
        (?:(?P<weeks>\d+)W)?          # weeks
        (?:(?P<days>\d+)D)?           # days
        (?:T                          # the time separator, which precedes any hour, minute or second
            (?:(?P<hours>\d+)H)?      # hours
            (?:(?P<minutes>\d+)M)?    # minutes
            (?:(?P<seconds>\d+)S)?    # seconds
        )?
        """,
        text,
        re.VERBOSE,
    )
    if iso and any(iso.groupdict().values()):
        return now - timedelta(**{name: int(count) for name, count in iso.groupdict().items() if count})
    friendly = re.fullmatch(
        r"""
        (?P<count>\d+)                                   # the amount
        \s*                                              # an optional space before the unit
        (?P<unit>seconds?|minutes?|hours?|days?|weeks?)  # the unit, singular or plural
        """,
        text,
        re.VERBOSE | re.IGNORECASE,
    )
    if friendly:
        return now - timedelta(**{f"{friendly['unit'].lower().rstrip('s')}s": int(friendly["count"])})
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return datetime.fromisoformat(text).astimezone()
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        msg = f"{value!r} is not an RFC 3339 timestamp, a local date, an ISO 8601 or a friendly duration"
        raise ValueError(msg) from exc
    # pip reads a datetime without an offset as local time
    return parsed if parsed.tzinfo is not None else parsed.astimezone()


def parse_timestamp(value: Parsed) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


__all__ = [
    "parse_exclude_newer",
    "parse_timestamp",
]

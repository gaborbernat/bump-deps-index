from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Final

_ISO_PATTERN: Final[re.Pattern[str]] = re.compile(
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
    re.VERBOSE,
)

_PARSE_EXCLUDE_NEWER_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"""
        (?P<count>\d+)                                   # the amount
        \s*                                              # an optional space before the unit
        (?P<unit>seconds?|minutes?|hours?|days?|weeks?)  # the unit, singular or plural
        """,
    re.VERBOSE | re.IGNORECASE,
)

_PARSE_EXCLUDE_NEWER_PATTERN_2: Final[re.Pattern[str]] = re.compile(r"\d{4}-\d{2}-\d{2}")


def parse_exclude_newer(value: str, now: datetime) -> datetime:
    text = value.strip()
    # no calendar units, which have no fixed length; uv rejects them as well
    if (iso := _ISO_PATTERN.fullmatch(text)) and any(iso.groupdict().values()):
        return now - timedelta(**{name: int(count) for name, count in iso.groupdict().items() if count})
    if friendly := _PARSE_EXCLUDE_NEWER_PATTERN.fullmatch(text):
        return now - timedelta(**{f"{friendly['unit'].lower().rstrip('s')}s": int(friendly["count"])})
    if _PARSE_EXCLUDE_NEWER_PATTERN_2.fullmatch(text):
        return datetime.fromisoformat(text).astimezone()
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        msg = f"{value!r} is not a cutoff: use a timestamp such as 2026-10-27T15:46:26Z, a date or P7D"
        raise ValueError(msg) from exc
    # pip reads a datetime without an offset as local time
    return parsed if parsed.tzinfo is not None else parsed.astimezone()


def accepts_upload(exclude_newer: datetime | None, uploaded: datetime | None) -> bool:
    # uv skips a file without an upload time under a cutoff, so only a dated upload before the cutoff counts
    return exclude_newer is None or (uploaded is not None and uploaded < exclude_newer)


__all__ = [
    "accepts_upload",
    "parse_exclude_newer",
]

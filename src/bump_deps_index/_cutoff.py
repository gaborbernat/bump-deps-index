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
        r"P(?:(?P<weeks>\d+)W)?(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?",
        text,
    )
    if iso and any(iso.groupdict().values()):
        return now - timedelta(**{name: int(count) for name, count in iso.groupdict().items() if count})
    if friendly := re.fullmatch(
        r"(?P<count>\d+)\s*(?P<unit>seconds?|minutes?|hours?|days?|weeks?)", text, re.IGNORECASE
    ):
        return now - timedelta(**{f"{friendly['unit'].lower().rstrip('s')}s": int(friendly["count"])})
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return datetime.fromisoformat(text).astimezone()
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        parsed = None
    if parsed is None or parsed.tzinfo is None:  # a timestamp without an offset is not RFC 3339
        msg = f"{value!r} is not an RFC 3339 timestamp, a local date, an ISO 8601 or a friendly duration"
        raise ValueError(msg)
    return parsed


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

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Final

import pytest

from bump_deps_index._cutoff import parse_exclude_newer, parse_timestamp

if TYPE_CHECKING:
    from bump_deps_index._parsed import Parsed

_NOW: Final[datetime] = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("value", "result"),
    [
        pytest.param("2026-10-27T15:46:26Z", datetime(2026, 10, 27, 15, 46, 26, tzinfo=UTC), id="zulu"),
        pytest.param(
            "2026-10-27T17:46:26+02:00", datetime(2026, 10, 27, 15, 46, 26, tzinfo=UTC), id="offset"
        ),
        pytest.param(" 2026-10-27T15:46:26Z ", datetime(2026, 10, 27, 15, 46, 26, tzinfo=UTC), id="surrounding-space"),
        pytest.param("2026-10-27", datetime(2026, 10, 27).astimezone(), id="local-date"),
        pytest.param("P7D", _NOW - timedelta(days=7), id="iso-days"),
        pytest.param("PT24H", _NOW - timedelta(hours=24), id="iso-hours"),
        pytest.param("P2W", _NOW - timedelta(weeks=2), id="iso-weeks"),
        pytest.param("P1DT12H30M", _NOW - timedelta(days=1, hours=12, minutes=30), id="iso-combined"),
        pytest.param("7 days", _NOW - timedelta(days=7), id="friendly-days"),
        pytest.param("1 week", _NOW - timedelta(weeks=1), id="friendly-week"),
        pytest.param("24hours", _NOW - timedelta(hours=24), id="friendly-no-space"),
        pytest.param("30 Minutes", _NOW - timedelta(minutes=30), id="friendly-case"),
        pytest.param("90 seconds", _NOW - timedelta(seconds=90), id="friendly-seconds"),
    ],
)
def test_parse_exclude_newer_accepts(value: str, result: datetime) -> None:
    assert parse_exclude_newer(value, _NOW) == result


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("soon", id="words"),
        pytest.param("2026-10-27T15:46:26", id="timestamp-without-offset"),
        pytest.param("P", id="empty-iso-duration"),
        pytest.param("PT", id="empty-iso-time"),
        pytest.param("P1M", id="iso-calendar-month"),
        pytest.param("P1Y", id="iso-calendar-year"),
        pytest.param("7 months", id="friendly-calendar-month"),
        pytest.param("", id="empty"),
    ],
)
def test_parse_exclude_newer_rejects(value: str) -> None:
    with pytest.raises(ValueError, match="is not an RFC 3339 timestamp"):
        parse_exclude_newer(value, _NOW)


@pytest.mark.parametrize(
    ("value", "result"),
    [
        pytest.param("2026-10-27T15:46:26Z", datetime(2026, 10, 27, 15, 46, 26, tzinfo=UTC), id="zulu"),
        pytest.param(
            "2026-10-27T15:46:26.123456+00:00",
            datetime(2026, 10, 27, 15, 46, 26, 123456, tzinfo=UTC),
            id="fraction",
        ),
        pytest.param("2026-10-27T15:46:26", None, id="no-offset"),
        pytest.param("not-a-time", None, id="malformed"),
        pytest.param(None, None, id="missing"),
        pytest.param(1, None, id="not-a-string"),
    ],
)
def test_parse_timestamp(value: Parsed, result: datetime | None) -> None:
    assert parse_timestamp(value) == result

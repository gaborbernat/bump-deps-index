from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from bump_deps_index._parsed import parse_timestamp  # ruff: ignore[import-private-name] Tests exercise timestamp parsing directly.

if TYPE_CHECKING:
    from bump_deps_index._parsed import Parsed


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

from __future__ import annotations

import re
from typing import Final
from urllib.parse import urlsplit, urlunsplit


def redact_url(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc.rpartition("@")[2], parsed.path, parsed.query, parsed.fragment))


_REDACT_TEXT_PATTERN: Final[re.Pattern[str]] = re.compile(r"(?<=://)[^/\s@]+@")


def redact_text(text: str) -> str:
    # userinfo may hold quotes, so stop at the characters that end it
    return _REDACT_TEXT_PATTERN.sub("", text)


__all__ = [
    "redact_text",
    "redact_url",
]

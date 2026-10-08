from __future__ import annotations

import re
from typing import Final
from urllib.parse import urlsplit, urlunsplit

# userinfo may hold quotes, so stop at the characters that end it
_URL_CREDENTIALS: Final[re.Pattern[str]] = re.compile(r"(?<=://)[^/\s@]+@")


def redact_url(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc.rpartition("@")[2], parsed.path, parsed.query, parsed.fragment))


def redact_text(text: str) -> str:
    return _URL_CREDENTIALS.sub("", text)


__all__ = [
    "redact_text",
    "redact_url",
]

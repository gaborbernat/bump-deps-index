from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit


def redact_url(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc.rpartition("@")[2], parsed.path, parsed.query, parsed.fragment))


def redact_text(text: str) -> str:
    # userinfo may hold quotes, so stop at the characters that end it
    return re.sub(r"(?<=://)[^/\s@]+@", "", text)


__all__ = [
    "redact_text",
    "redact_url",
]

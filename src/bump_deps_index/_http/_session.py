from __future__ import annotations

import ssl
from typing import TYPE_CHECKING, Final

from httpx import Client, Limits
from truststore import SSLContext

from ._cache import FetchCache

if TYPE_CHECKING:
    from httpx import Response

# httpx's own default; `Limits()` would lift every cap
_DEFAULT_LIMITS: Final[Limits] = Limits(max_connections=100, max_keepalive_connections=20)


def new_client(*, timeout: float = 5.0, limits: Limits = _DEFAULT_LIMITS) -> Client:
    return Client(verify=SSLContext(ssl.PROTOCOL_TLS_CLIENT), timeout=timeout, limits=limits)


class Session:
    def __init__(self, client: Client) -> None:
        self._client = client
        self._responses: FetchCache[tuple[str, str, str | None], Response] = FetchCache()

    def get(self, url: str, *, accept: str, authorization: str | None = None) -> Response:
        headers = {"Accept": accept} if authorization is None else {"Accept": accept, "Authorization": authorization}
        return self._responses.get(
            (url, accept, authorization),
            lambda: self._client.get(url, headers=headers, follow_redirects=True).raise_for_status(),
        )


__all__ = [
    "Session",
    "new_client",
]

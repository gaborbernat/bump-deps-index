from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import quote

from ._cache import FetchCache
from ._cutoff import accepts_upload
from ._parsed import json_field, parse_timestamp, table
from ._semver import split_npm_spec

if TYPE_CHECKING:
    from datetime import datetime

    from httpx import Client

    from ._config import NpmSettings


@dataclass(frozen=True, slots=True, kw_only=True)
class NpmRelease:
    versions: tuple[str, ...]
    latest: str | None


class NpmRegistry:
    def __init__(self, client: Client, exclude_newer: datetime | None, settings: NpmSettings) -> None:
        self.client = client
        self.exclude_newer = exclude_newer
        self._settings = settings
        self._documents: FetchCache[NpmRelease] = FetchCache()

    def release(self, registry: str, spec: str) -> NpmRelease:
        package, _ = split_npm_spec(spec)
        url = f"{registry.rstrip('/')}/{quote(package, safe='@')}"
        return self._documents.get(url, lambda url: self._fetch(url, self._settings.authorization(registry)))

    def _fetch(self, url: str, authorization: str | None) -> NpmRelease:
        response = self.client.get(
            url,
            headers={
                # the abbreviated document omits the `time` map of upload times, so a cutoff needs the full one
                "Accept": (
                    "application/vnd.npm.install-v1+json; q=1.0, application/json; q=0.8"
                    if self.exclude_newer is None
                    else "application/json"
                ),
                **({} if authorization is None else {"Authorization": authorization}),
            },
            follow_redirects=True,
        )
        response.raise_for_status()
        times = {} if self.exclude_newer is None else table(response.json(), "time")
        latest = table(response.json(), "dist-tags").get("latest")
        return NpmRelease(
            versions=tuple(
                version
                for version, meta in json_field(response, "versions", dict).items()
                if not (isinstance(meta, dict) and meta.get("deprecated"))
                and accepts_upload(self.exclude_newer, parse_timestamp(times.get(version)))
            ),
            latest=latest if isinstance(latest, str) else None,
        )


__all__ = [
    "NpmRegistry",
]

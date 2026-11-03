from __future__ import annotations

from typing import TYPE_CHECKING, Final, NamedTuple
from urllib.parse import quote

from bump_deps_index._cache import FetchCache
from bump_deps_index._cutoff import accepts_upload
from bump_deps_index._parsed import json_field, parse_timestamp, table
from bump_deps_index._semver import split_npm_spec

if TYPE_CHECKING:
    from datetime import datetime

    from httpx import Client

    from bump_deps_index._config import NpmSettings

_ACCEPT: Final[str] = "application/vnd.npm.install-v1+json; q=1.0, application/json; q=0.8"


class NpmRelease(NamedTuple):
    versions: tuple[str, ...]
    """Versions the index accepts: not deprecated, and uploaded before the cutoff when there is one."""
    latest: str | None
    """The `latest` dist-tag."""


class NpmRegistry:
    def __init__(self, client: Client, exclude_newer: datetime | None, settings: NpmSettings) -> None:
        self.client = client
        self.exclude_newer = exclude_newer
        self._settings = settings
        self._documents: FetchCache[NpmRelease] = FetchCache()

    def release(self, registry: str, spec: str) -> NpmRelease:
        package, _ = split_npm_spec(spec)
        url = f"{registry.rstrip('/')}/{quote(package, safe='@')}"
        authorization = self._settings.authorization(registry)
        return self._documents.get(url, lambda url: self._fetch(url, authorization))

    def _fetch(self, url: str, authorization: str | None) -> NpmRelease:
        response = self.client.get(
            url,
            headers={
                # the abbreviated document omits the `time` map of upload times, so a cutoff needs the full one
                "Accept": _ACCEPT if self.exclude_newer is None else "application/json",
                **({} if authorization is None else {"Authorization": authorization}),
            },
            follow_redirects=True,
        )
        response.raise_for_status()
        times = {} if self.exclude_newer is None else table(response.json(), "time")
        latest = table(response.json(), "dist-tags").get("latest")
        return NpmRelease(
            tuple(
                version
                for version, meta in json_field(response, "versions", dict).items()
                if not (isinstance(meta, dict) and meta.get("deprecated"))
                and accepts_upload(self.exclude_newer, parse_timestamp(times.get(version)))
            ),
            latest if isinstance(latest, str) else None,
        )


__all__ = [
    "NpmRegistry",
    "NpmRelease",
]

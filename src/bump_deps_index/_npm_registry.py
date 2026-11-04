from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import quote

from ._cutoff import accepts_upload
from ._parsed import json_field, parse_timestamp, table
from ._semver import split_npm_spec

if TYPE_CHECKING:
    from datetime import datetime

    from ._config._npm import NpmSettings
    from ._http._session import Session


class NpmRegistry:
    def __init__(self, session: Session, exclude_newer: datetime | None, settings: NpmSettings) -> None:
        self._session = session
        self.exclude_newer = exclude_newer
        self._settings = settings

    def release(self, registry: str, spec: str) -> NpmRelease:
        package, _ = split_npm_spec(spec)
        response = self._session.get(
            f"{registry.rstrip('/')}/{quote(package, safe='@')}",
            # the abbreviated document omits the `time` map of upload times, so a cutoff needs the full one
            accept=(
                "application/vnd.npm.install-v1+json; q=1.0, application/json; q=0.8"
                if self.exclude_newer is None
                else "application/json"
            ),
            authorization=self._settings.authorization(registry),
        )
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


@dataclass(frozen=True, slots=True, kw_only=True)
class NpmRelease:
    versions: tuple[str, ...]
    latest: str | None


__all__ = [
    "NpmRegistry",
]

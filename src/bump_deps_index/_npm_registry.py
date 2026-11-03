from __future__ import annotations

from typing import TYPE_CHECKING, Final, NamedTuple
from urllib.parse import quote

from bump_deps_index._parsed import json_field, parse_timestamp, table
from bump_deps_index._semver import split_npm_spec

if TYPE_CHECKING:
    from bump_deps_index._pypi import SimpleIndex

_ACCEPT: Final[str] = "application/vnd.npm.install-v1+json; q=1.0, application/json; q=0.8"


class NpmRelease(NamedTuple):
    versions: tuple[str, ...]
    """Versions the index accepts: not deprecated, and uploaded before the cutoff when there is one."""
    latest: str | None
    """The `latest` dist-tag."""


def npm_release(index: SimpleIndex, registry: str, spec: str, authorization: str | None) -> NpmRelease:
    package, _ = split_npm_spec(spec)
    url = f"{registry.rstrip('/')}/{quote(package, safe='@')}"
    return index.npm_releases.get(url, lambda url: _fetch_release(index, url, authorization))


def _fetch_release(index: SimpleIndex, url: str, authorization: str | None) -> NpmRelease:
    response = index.client.get(
        url,
        headers={
            # the abbreviated document omits the `time` map of upload times, so a cutoff needs the full one
            "Accept": _ACCEPT if index.exclude_newer is None else "application/json",
            **({} if authorization is None else {"Authorization": authorization}),
        },
        follow_redirects=True,
    )
    response.raise_for_status()
    times = {} if index.exclude_newer is None else table(response.json(), "time")
    latest = table(response.json(), "dist-tags").get("latest")
    return NpmRelease(
        tuple(
            version
            for version, meta in json_field(response, "versions", dict).items()
            if not (isinstance(meta, dict) and meta.get("deprecated"))
            and index.accepts_upload(parse_timestamp(times.get(version)))
        ),
        latest if isinstance(latest, str) else None,
    )


__all__ = [
    "NpmRelease",
    "npm_release",
]

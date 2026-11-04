from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import quote

from bump_deps_index._ecosystems._common._candidates import Candidate, Candidates, Lookup, Registry, accepted_versions
from bump_deps_index._lookup import IndexLookup
from bump_deps_index._parsed import json_field, parse_timestamp, table

from ._semver import is_prerelease, rank_versions

if TYPE_CHECKING:
    from bump_deps_index._config._project import IndexSettings, Scope
    from bump_deps_index._http._session import Session


class NpmRegistry(Registry):
    def __init__(self, session: Session, settings: IndexSettings) -> None:
        self._session = session
        self._settings = settings

    def candidates(self, lookup: Lookup) -> Candidates:
        exclude_newer = self._settings.exclude_newer
        registry = lookup.indexes.url
        response = self._session.get(
            f"{registry.rstrip('/')}/{quote(lookup.name, safe='@')}",
            # the abbreviated document omits the `time` map of upload times, so a cutoff needs the full one
            accept=(
                "application/vnd.npm.install-v1+json; q=1.0, application/json; q=0.8"
                if exclude_newer is None
                else "application/json"
            ),
            authorization=self._settings.npm.authorization(registry),
        )
        times = {} if exclude_newer is None else table(response.json(), "time")
        latest = table(response.json(), "dist-tags").get("latest")
        versions = json_field(response, "versions", dict)
        candidates = (
            Candidate(
                version=version,
                uploaded=parse_timestamp(times.get(version)),
                withdrawn=isinstance(meta := versions[version], dict) and bool(meta.get("deprecated")),
            )
            for version in rank_versions(versions)
        )
        return Candidates(
            versions=tuple(
                accepted_versions(
                    candidates, exclude_newer=exclude_newer, pre_release=lookup.pre_release, is_prerelease=is_prerelease
                )
            ),
            preferred=latest if isinstance(latest, str) else None,
        )


def npm_indexes(requirement: str, _name: str, scope: Scope) -> IndexLookup:
    # the whole spec, not the name, picks the scope, which differs for a spec such as `@a@1`
    return IndexLookup(url=scope.settings.npm.registry(requirement, scope.settings.npm_registry))


__all__ = [
    "NpmRegistry",
    "npm_indexes",
]

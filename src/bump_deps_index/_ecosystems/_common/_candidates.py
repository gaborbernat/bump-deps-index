from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from packaging.utils import canonicalize_name

from bump_deps_index._cutoff import accepts_upload

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator
    from datetime import datetime

    from packaging.version import Version

    from bump_deps_index._config._project import IndexSettings
    from bump_deps_index._lookup import IndexLookup, PkgType


class Registry(ABC):
    @abstractmethod
    def candidates(self, lookup: Lookup) -> Candidates:
        raise NotImplementedError


@dataclass(frozen=True, slots=True, kw_only=True)
class Lookup:
    requirement: str
    name: str
    pkg_type: PkgType
    pre_release: bool
    python_floor: Version | None
    indexes: IndexLookup
    # the PEP 735 group the requirement is listed in, None when the file has no groups
    group: str | None
    # the cutoff resolved for this lookup, None when it is uncooled
    exclude_newer: datetime | None


@dataclass(frozen=True, slots=True, kw_only=True)
class Candidates:
    # newest first; may be lazy, so read it once
    versions: Iterable[str]
    # the release the registry recommends, such as the npm `latest` dist-tag
    preferred: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class Candidate:
    version: str
    uploaded: datetime | None
    # yanked on PyPI, deprecated on npm
    withdrawn: bool


def exclude_newer_for(
    settings: IndexSettings, name: str, *, canonical: Callable[[str], str], group: str | None
) -> datetime | None:
    # membership decides, not the value: a None in a table exempts its packages from the next cutoff down
    packages = {canonical(package): cutoff for package, cutoff in settings.exclude_newer_package.items()}
    if (key := canonical(name)) in packages:
        return packages[key]
    groups = {canonicalize_name(listed): cutoff for listed, cutoff in settings.exclude_newer_group.items()}
    if group is not None and (group_key := canonicalize_name(group)) in groups:
        return groups[group_key]
    return settings.exclude_newer


def accepted_versions(
    candidates: Iterable[Candidate],
    *,
    exclude_newer: datetime | None,
    pre_release: bool,
    is_prerelease: Callable[[str], bool],
) -> Iterator[str]:
    return (
        candidate.version
        for candidate in candidates
        if not candidate.withdrawn
        and accepts_upload(exclude_newer, candidate.uploaded)
        and (pre_release or not is_prerelease(candidate.version))
    )


__all__ = [
    "Candidate",
    "Candidates",
    "Lookup",
    "Registry",
    "accepted_versions",
    "exclude_newer_for",
]

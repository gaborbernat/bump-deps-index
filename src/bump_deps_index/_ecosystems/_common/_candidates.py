from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from bump_deps_index._cutoff import accepts_upload

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator
    from datetime import datetime

    from packaging.version import Version

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
]

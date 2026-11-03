from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, NamedTuple
from urllib.parse import urlsplit

from packaging.requirements import Requirement

from bump_deps_index._pep440 import bump_python
from bump_deps_index._semver import bump_js

if TYPE_CHECKING:
    from packaging.version import Version

    from bump_deps_index._npm_registry import NpmRegistry
    from bump_deps_index._pypi import IndexLookup, SimpleIndex


class PkgType(StrEnum):
    PYTHON = "Python"
    JS = "JavaScript"


class Lookup(NamedTuple):
    requirement: str
    pkg_type: PkgType
    pre_release: bool
    python_floor: Version | None
    indexes: IndexLookup


def update(index: SimpleIndex, npm: NpmRegistry, lookup: Lookup, authorization: str | None) -> str:
    if lookup.pkg_type is PkgType.JS:
        release = npm.release(lookup.indexes.url, lookup.requirement, authorization)
        return bump_js(lookup.requirement, release.versions, release.latest, pre_release=lookup.pre_release)
    if (requirement := Requirement(lookup.requirement)).url is not None:
        return lookup.requirement
    versions = index.versions(
        lookup.indexes,
        requirement.name,
        python_version=lookup.python_floor,
        pre_release=lookup.pre_release,
    )
    return bump_python(lookup.requirement, requirement, versions, pre_release=lookup.pre_release)


def package_type(spec: str) -> PkgType:
    try:
        requirement = Requirement(spec)
    except ValueError:
        return PkgType.JS
    return PkgType.PYTHON if requirement.url is None or urlsplit(requirement.url).scheme else PkgType.JS


__all__ = [
    "Lookup",
    "PkgType",
    "package_type",
    "update",
]

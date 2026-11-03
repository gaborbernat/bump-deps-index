from __future__ import annotations

from typing import TYPE_CHECKING

from packaging.requirements import Requirement

from bump_deps_index._lookup import PkgType
from bump_deps_index._pep440 import bump_python
from bump_deps_index._semver import bump_js

if TYPE_CHECKING:
    from bump_deps_index._lookup import Lookup
    from bump_deps_index._npm_registry import NpmRegistry
    from bump_deps_index._pypi import SimpleIndex


def update(index: SimpleIndex, npm: NpmRegistry, lookup: Lookup) -> str:
    if lookup.pkg_type is PkgType.JS:
        release = npm.release(lookup.indexes.url, lookup.requirement)
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


__all__ = [
    "update",
]

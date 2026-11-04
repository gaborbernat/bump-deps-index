from __future__ import annotations

from typing import TYPE_CHECKING

from packaging.requirements import Requirement

from ._lookup import PkgType
from ._pep440 import bump_python
from ._semver import bump_js

if TYPE_CHECKING:
    from ._lookup import Lookup
    from ._npm_registry import NpmRegistry
    from ._pypi import SimpleIndex


def update(index: SimpleIndex, npm: NpmRegistry, lookup: Lookup) -> str:
    match lookup.pkg_type:
        case PkgType.JS:
            release = npm.release(lookup.indexes.url, lookup.requirement, pre_release=lookup.pre_release)
            return bump_js(lookup.requirement, release.versions, release.latest)
        case _:  # PkgType has two members, the other being Python
            if (requirement := Requirement(lookup.requirement)).url is not None:
                return lookup.requirement
            versions = index.versions(
                lookup.indexes,
                requirement.name,
                python_version=lookup.python_floor,
                pre_release=lookup.pre_release,
            )
            return bump_python(lookup.requirement, requirement, versions)


__all__ = [
    "update",
]

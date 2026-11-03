from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from packaging.requirements import InvalidRequirement, Requirement

if TYPE_CHECKING:
    from packaging.version import Version


@dataclass(frozen=True, slots=True, kw_only=True)
class IndexLookup:
    url: str
    # uv indexes checked before `url`; uv takes a package from the first one that has it
    first: tuple[str, ...] = ()
    # pip extra indexes, whose releases pip merges with those of `url`
    extra: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class Lookup:
    requirement: str
    pkg_type: PkgType
    pre_release: bool
    python_floor: Version | None
    indexes: IndexLookup


def package_type(spec: str) -> PkgType:
    try:
        requirement = Requirement(spec)
    except InvalidRequirement:
        return PkgType.JS
    return PkgType.PYTHON if requirement.url is None or urlsplit(requirement.url).scheme else PkgType.JS


class PkgType(StrEnum):
    PYTHON = "Python"
    JS = "JavaScript"


__all__ = [
    "IndexLookup",
    "Lookup",
    "PkgType",
    "package_type",
]

"""Package registries and version bumps, one per ecosystem."""

from __future__ import annotations

from typing import Final

from bump_deps_index._lookup import PkgType

from ._base import Ecosystem
from ._npm._registry import NpmRegistry
from ._npm._semver import bump_js
from ._python._index import SimpleIndex
from ._python._pep440 import bump_python

ECOSYSTEMS: Final[dict[PkgType, Ecosystem]] = {
    PkgType.PYTHON: Ecosystem(registry=SimpleIndex, bump=bump_python),
    PkgType.JS: Ecosystem(registry=NpmRegistry, bump=bump_js),
}

__all__ = [
    "ECOSYSTEMS",
]

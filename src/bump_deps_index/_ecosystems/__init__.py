"""Package registries and version bumps, one per ecosystem."""

from __future__ import annotations

from typing import Final

from bump_deps_index._config._project import entry_indexes, named_indexes
from bump_deps_index._lookup import PkgType

from ._base import Ecosystem
from ._npm._registry import NpmRegistry, npm_indexes
from ._npm._semver import bump_js, npm_name
from ._python._index import SimpleIndex, python_name
from ._python._pep440 import bump_python

ECOSYSTEMS: Final[dict[PkgType, Ecosystem]] = {
    PkgType.PYTHON: Ecosystem(
        registry=SimpleIndex,
        bump=bump_python,
        name=python_name,
        route=named_indexes,
        entry_route=entry_indexes,
        index_url=lambda settings: settings.index_url,
    ),
    PkgType.JS: Ecosystem(
        registry=NpmRegistry,
        bump=bump_js,
        name=npm_name,
        route=npm_indexes,
        entry_route=npm_indexes,
        index_url=lambda settings: settings.npm_registry,
    ),
}

__all__ = [
    "ECOSYSTEMS",
]

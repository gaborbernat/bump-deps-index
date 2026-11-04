from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from bump_deps_index._config._project import entry_indexes, named_indexes
from bump_deps_index._lookup import PkgType

from ._npm._registry import NpmRegistry, npm_indexes
from ._npm._semver import bump_js, npm_name
from ._python._index import SimpleIndex, python_name
from ._python._pep440 import bump_python

if TYPE_CHECKING:
    from collections.abc import Callable

    from bump_deps_index._config._project import Declared, IndexSettings, Scope
    from bump_deps_index._http._session import Session
    from bump_deps_index._lookup import IndexLookup

    from ._common._candidates import Candidates, Registry


@dataclass(frozen=True, slots=True, kw_only=True)
class Ecosystem:
    registry: Callable[[Session, IndexSettings], Registry]
    bump: Callable[[str, Candidates], str]
    # raises InvalidRequirement for a Python spec that is not a requirement
    name: Callable[[str], str]
    # for a package named on the command line
    route: Callable[[str, str, Scope], IndexLookup]
    # for a requirement declared in a file; None skips it
    entry_route: Callable[[str, str, Declared], IndexLookup | None]
    # the default index shown in "Using ... index"
    index_url: Callable[[IndexSettings], str]


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
    "Ecosystem",
]

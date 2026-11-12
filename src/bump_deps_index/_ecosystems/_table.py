from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from packaging.utils import canonicalize_name

from bump_deps_index.model import PkgType

from ._npm import NpmRegistry, bump_js, npm_indexes, npm_name
from ._python import SimpleIndex, bump_python, python_name

if TYPE_CHECKING:
    from collections.abc import Callable

    from bump_deps_index.model import Declared, IndexLookup, IndexSettings, Scope, Session

    from .model import Candidates, Registry


def ecosystem_table(
    named_indexes: Callable[[str, str, Scope], IndexLookup],
    entry_indexes: Callable[[str, str, Declared], IndexLookup | None],
) -> dict[PkgType, Ecosystem]:
    return {
        PkgType.PYTHON: Ecosystem(
            registry=lambda session, _settings: SimpleIndex(session),
            bump=bump_python,
            name=python_name,
            canonical=canonicalize_name,
            route=named_indexes,
            entry_route=entry_indexes,
            index_url=lambda settings: settings.index_url,
        ),
        PkgType.JS: Ecosystem(
            registry=NpmRegistry,
            bump=bump_js,
            name=npm_name,
            # npm does not normalize names, so only the exact spelling matches a settings entry
            canonical=lambda name: name,
            route=npm_indexes,
            entry_route=npm_indexes,
            index_url=lambda settings: settings.npm_registry,
        ),
    }


@dataclass(frozen=True, slots=True, kw_only=True)
class Ecosystem:
    registry: Callable[[Session, IndexSettings], Registry]
    bump: Callable[[str, Candidates], str]
    # raises InvalidRequirement for a Python spec that is not a requirement
    name: Callable[[str], str]
    # the form two spellings of one package share, for matching the per-package and per-group settings
    canonical: Callable[[str], str]
    # for a package named on the command line
    route: Callable[[str, str, Scope], IndexLookup]
    # for a requirement declared in a file; None skips it
    entry_route: Callable[[str, str, Declared], IndexLookup | None]
    # the default index shown in "Using ... index"
    index_url: Callable[[IndexSettings], str]


__all__ = [
    "Ecosystem",
    "ecosystem_table",
]

"""Shared dependency records and lookup contracts."""

from __future__ import annotations

__lazy_modules__ = [
    f"{__spec__.parent}._cutoff",  # ty: ignore[missing-union-attribute]  # imported modules have a spec
    f"{__spec__.parent}._lookup",  # ty: ignore[missing-union-attribute]  # imported modules have a spec
    f"{__spec__.parent}._parsed",  # ty: ignore[missing-union-attribute]  # imported modules have a spec
]

from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeAlias

from ._cutoff import accepts_upload
from ._lookup import IndexLookup, PkgType, package_type
from ._parsed import Parsed, json_field, mappings, parse_timestamp, strings, table

if TYPE_CHECKING:
    from ._config import Declared as ConfigDeclared
    from ._config import IndexSettings as ConfigIndexSettings
    from ._config import Scope as ConfigScope
    from ._config import UvIndexes as ConfigUvIndexes
    from ._http import Session as HttpSession

    Declared: TypeAlias = ConfigDeclared
    IndexSettings: TypeAlias = ConfigIndexSettings
    Scope: TypeAlias = ConfigScope
    UvIndexes: TypeAlias = ConfigUvIndexes
    Session: TypeAlias = HttpSession


@dataclass(frozen=True, slots=True, kw_only=True)
class Entry:
    spec: str
    pkg_type: PkgType
    requires_python: str | None = None
    # a PEP 723 script brings its own uv sources and indexes, since `uv run --script` resolves it outside the project
    uv: UvIndexes | None = None
    # an index the file sets for its own requirements, such as `--index-url` in a requirements file
    index_url: str | None = None
    # the extra indexes a requirements file sets with `--extra-index-url`
    extra_index_urls: tuple[str, ...] = ()
    # the PEP 735 group of the entry, `project` for the project's dependencies and extras; None where a format has none
    group: str | None = None


__all__ = [
    "Entry",
    "IndexLookup",
    "Parsed",
    "PkgType",
    "accepts_upload",
    "json_field",
    "mappings",
    "package_type",
    "parse_timestamp",
    "strings",
    "table",
]

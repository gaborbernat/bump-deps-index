"""Shared dependency records and lookup contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeAlias

from ._cutoff import accepts_upload
from ._lookup import IndexLookup, PkgType, package_type
from ._parsed import Parsed, json_field, mappings, parse_timestamp, strings, table

if TYPE_CHECKING:
    from ._config import Declared as _Declared
    from ._config import IndexSettings as _IndexSettings
    from ._config import Scope as _Scope
    from ._config import UvIndexes as _UvIndexes
    from ._http import Session as _Session

    Declared: TypeAlias = _Declared
    IndexSettings: TypeAlias = _IndexSettings
    Scope: TypeAlias = _Scope
    UvIndexes: TypeAlias = _UvIndexes
    Session: TypeAlias = _Session


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

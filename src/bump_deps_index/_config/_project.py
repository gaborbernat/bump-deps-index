from __future__ import annotations

import sys
from dataclasses import dataclass
from tomllib import load as load_toml
from typing import TYPE_CHECKING

from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import Version

from bump_deps_index.model import IndexLookup, table

from ._uv import UvIndexes, uv_project_indexes

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import datetime
    from pathlib import Path

    from bump_deps_index.model import Entry

    from ._npm import NpmSettings


def get_project(directory: Path) -> Project:
    pyproject = next(
        (path for folder in (directory, *directory.parents) if (path := folder / "pyproject.toml").is_file()), None
    )
    if pyproject is None:
        return Project()
    try:
        with pyproject.open("rb") as file_handler:
            config = load_toml(file_handler)
        project = table(config, "project")
        name, requires_python = project.get("name"), project.get("requires-python")
        return Project(
            pyproject=pyproject,
            name=canonicalize_name(name) if isinstance(name, str) else None,
            python_floor=python_floor(requires_python if isinstance(requires_python, str) else None),
            uv=uv_project_indexes(pyproject.parent, config),
        )
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"ignoring project metadata from {pyproject}, so its uv settings are not read: {exc!r}\n")
        return Project(pyproject=pyproject)


def python_floor(requires_python: str | None) -> Version | None:
    specifiers = SpecifierSet(requires_python or "")
    bounds = [
        _lower_bound(specifier.operator, specifier.version)
        for specifier in specifiers
        if specifier.operator in {"==", ">", ">=", "~="}
    ]
    if not bounds:
        return None
    floor = max(bounds)
    for excluded in specifiers:
        if (
            excluded.operator == "!="
            and excluded.version.endswith(".*")
            and floor in SpecifierSet(f"=={excluded.version}")
        ):
            prefix = Version(excluded.version.removesuffix(".*")).release
            floor = _release((*prefix[:-1], prefix[-1] + 1))
    excluded_versions = {
        Version(specifier.version)
        for specifier in specifiers
        if specifier.operator == "!=" and not specifier.version.endswith(".*")
    }
    while floor in excluded_versions:
        floor = _next_release(floor)
    return floor if specifiers.contains(floor, prereleases=True) else None


def _lower_bound(operator: str, raw_version: str) -> Version:
    version = Version(raw_version.removesuffix(".*"))
    if operator != ">":
        return version
    if version.is_prerelease or version.is_devrelease:
        return _release(version.release)
    return _next_release(version)


def _release(parts: Iterable[int]) -> Version:
    return Version(".".join(str(part) for part in parts))


def _next_release(version: Version) -> Version:
    release = (*version.release, *(0 for _ in range(3 - len(version.release))))
    return _release((*release[:-1], release[-1] + 1))


@dataclass(frozen=True, slots=True, kw_only=True)
class Project:
    pyproject: Path | None = None
    name: str | None = None
    python_floor: Version | None = None
    uv: UvIndexes | None = None


def named_indexes(_requirement: str, name: str, scope: Scope) -> IndexLookup:
    # a package from git, a path or a URL gets the default index
    python_lookup = _python_indexes(name, scope.uv, scope.settings.index_url, scope.settings.pip_extras)
    return python_lookup or IndexLookup(url=scope.settings.index_url)


def _python_indexes(name: str, uv: UvIndexes | None, default: str, pip_extras: tuple[str, ...]) -> IndexLookup | None:
    package = canonicalize_name(name)
    if uv is None:  # pip installs the file, and merges its extra indexes with the default one
        return IndexLookup(url=default, extra=pip_extras)
    if package not in uv.sources:
        return IndexLookup(url=default, first=uv.first)
    # uv looks up a package a source pins to an index on that index alone, and skips one from git, a path or a URL
    return None if (pinned := uv.sources[package]) is None else IndexLookup(url=pinned)


def entry_indexes(_requirement: str, name: str, declared: Declared) -> IndexLookup | None:
    entry = declared.entry
    # skip the project itself, though a script may depend on it
    if entry.uv is None and canonicalize_name(name) == declared.project.name:
        return None
    return _python_indexes(
        name,
        declared.uv if entry.uv is None else entry.uv,
        entry.index_url or declared.settings.index_url,
        (*declared.settings.pip_extras, *entry.extra_index_urls),
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class Scope:
    settings: IndexSettings
    project: Project
    # the project's uv indexes where uv resolves, None where pip installs
    uv: UvIndexes | None


@dataclass(frozen=True, slots=True, kw_only=True)
class Declared(Scope):
    entry: Entry


@dataclass(frozen=True, slots=True, kw_only=True)
class IndexSettings:
    index_url: str
    pip_extras: tuple[str, ...]
    npm_registry: str
    npm: NpmSettings
    exclude_newer: datetime | None
    # per package, keyed by the name as written; None exempts the package from the group and global cutoffs
    exclude_newer_package: dict[str, datetime | None]
    # per PEP 735 group, keyed by the name as written; `project` names the project's dependencies and extras
    exclude_newer_group: dict[str, datetime | None]


__all__ = [
    "Declared",
    "IndexSettings",
    "Project",
    "Scope",
    "entry_indexes",
    "get_project",
    "named_indexes",
    "python_floor",
]

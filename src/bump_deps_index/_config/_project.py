from __future__ import annotations

import sys
from tomllib import load as load_toml
from typing import TYPE_CHECKING, NamedTuple

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name

from bump_deps_index._lookup import IndexLookup, PkgType
from bump_deps_index._parsed import table
from bump_deps_index._pep440 import python_floor

from ._uv import UvIndexes, uv_project_indexes

if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path

    from packaging.version import Version

    from bump_deps_index._loaders import Entry

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
            pyproject,
            canonicalize_name(name) if isinstance(name, str) else None,
            python_floor(requires_python if isinstance(requires_python, str) else None),
            uv_project_indexes(pyproject.parent, config),
        )
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"ignoring project metadata from {pyproject}, so its uv settings are not read: {exc!r}\n")
        return Project(pyproject)


def named_indexes(package: str, pkg_type: PkgType, project: Project, settings: IndexSettings) -> IndexLookup:
    if pkg_type is PkgType.JS:
        return IndexLookup(settings.npm.registry(package, settings.npm_registry))
    # `package_type` parsed the requirement; a package from git, a path or a URL gets the default index
    python_lookup = _python_indexes(Requirement(package).name, project.uv, settings.index_url, settings.pip_extras)
    return python_lookup or IndexLookup(settings.index_url)


def _python_indexes(name: str, uv: UvIndexes | None, default: str, pip_extras: tuple[str, ...]) -> IndexLookup | None:
    package = canonicalize_name(name)
    if uv is None:  # pip installs the file, and merges its extra indexes with the default one
        return IndexLookup(default, extra=pip_extras)
    if package not in uv.sources:
        return IndexLookup(default, first=uv.first)
    # uv looks up a package a source pins to an index on that index alone, and skips one from git, a path or a URL
    return None if (pinned := uv.sources[package]) is None else IndexLookup(pinned)


def entry_indexes(
    name: str, entry: Entry, project: Project, own_uv: UvIndexes | None, settings: IndexSettings
) -> IndexLookup | None:
    if entry.pkg_type is PkgType.JS:
        return IndexLookup(settings.npm.registry(name, settings.npm_registry))
    try:
        requirement = Requirement(name)
    except InvalidRequirement:  # skip entries without a project name, such as local paths and URLs
        return None
    # skip the project itself, though a script may depend on it
    if entry.uv is None and canonicalize_name(requirement.name) == project.name:
        return None
    return _python_indexes(
        requirement.name,
        own_uv if entry.uv is None else entry.uv,
        entry.index_url or settings.index_url,
        (*settings.pip_extras, *entry.extra_index_urls),
    )


class Project(NamedTuple):
    pyproject: Path | None = None
    name: str | None = None
    python_floor: Version | None = None
    uv: UvIndexes | None = None


class IndexSettings(NamedTuple):
    index_url: str
    pip_extras: tuple[str, ...]
    npm_registry: str
    npm: NpmSettings
    exclude_newer: datetime | None


__all__ = [
    "IndexSettings",
    "Project",
    "entry_indexes",
    "get_project",
    "named_indexes",
]

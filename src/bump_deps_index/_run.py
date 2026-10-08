from __future__ import annotations

import ssl
import sys
from concurrent.futures import ThreadPoolExecutor
from configparser import Error as ConfigParserError
from itertools import chain
from pathlib import Path
from tomllib import load as load_toml
from typing import TYPE_CHECKING, NamedTuple

from httpx import Client, HTTPError, Limits
from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name
from truststore import SSLContext
from yaml import YAMLError

from bump_deps_index._config import npm_settings, pip_extra_indexes, uv_project_indexes
from bump_deps_index._loaders import get_loaders
from bump_deps_index._parsed import table
from bump_deps_index._pep440 import python_floor
from bump_deps_index._pypi import IndexLookup, SimpleIndex
from bump_deps_index._redact import redact_text, redact_url
from bump_deps_index._spec import Lookup, PkgType, package_type, update

if TYPE_CHECKING:
    from collections.abc import Sequence

    from packaging.version import Version

    from bump_deps_index._cli import Options
    from bump_deps_index._config import NpmSettings, UvIndexes
    from bump_deps_index._loaders import Entry, Loader


def run(opt: Options) -> bool:
    """Update dependencies selected by the CLI options."""
    pre_release = {"yes": True, "no": False, "file-default": None}[opt.pre_release]
    settings = _IndexSettings(opt.index_url, pip_extra_indexes(), opt.npm_registry, npm_settings())
    if opt.pkgs:
        return _run_packages(opt.pkgs, settings, pre_release=False if pre_release is None else pre_release)
    return _run_files(opt.filenames, settings, pre_release=pre_release)


class _IndexSettings(NamedTuple):
    index_url: str
    pip_extras: tuple[str, ...]
    npm_registry: str
    npm: NpmSettings


def _run_packages(packages: Sequence[str], settings: _IndexSettings, *, pre_release: bool) -> bool:
    # a package you name gets the floor and the index pins of the project you run in
    project = _get_project(Path.cwd())
    lookups = [_named_lookup(package, project, settings, pre_release=pre_release) for package in packages]
    return _resolve(settings, list(dict.fromkeys(lookups)))[1]


def _named_lookup(raw: str, project: _Project, settings: _IndexSettings, *, pre_release: bool) -> Lookup:
    package = raw.strip()
    if (pkg_type := package_type(package)) is PkgType.JS:
        indexes = IndexLookup(settings.npm.registry(package, settings.npm_registry))
    else:  # `package_type` parsed the requirement; a package from git, a path or a URL gets the default index
        python = _python_indexes(Requirement(package).name, project.uv, settings.index_url, settings.pip_extras)
        indexes = python or IndexLookup(settings.index_url)
    return Lookup(package, pkg_type, pre_release, project.python_floor, indexes)


def _run_files(filenames: Sequence[Path], settings: _IndexSettings, *, pre_release: bool | None) -> bool:
    successful = bool(filenames)
    if not successful:
        sys.stderr.write("no supported dependency files found\n")
    plans: list[tuple[Path, Loader, list[Lookup]]] = []
    for filename in filenames:
        if not filename.is_file():
            sys.stderr.write(f"{filename} does not exist\n")
            successful = False
        elif (loader := next((i for i in get_loaders() if i.supports(filename)), None)) is None:
            sys.stderr.write(f"we do not support {filename}\n")
            successful = False
        elif (lookups := _load_lookups(loader, filename, settings, pre_release=pre_release)) is None:
            successful = False
        else:
            plans.append((filename, loader, lookups))
    # resolve the files in one batch to send one lookup per package across files
    results, resolved = _resolve(settings, list(dict.fromkeys(chain.from_iterable(lookups for *_, lookups in plans))))
    for filename, loader, lookups in plans:
        changes = {
            lookup.requirement: new
            for lookup in lookups
            if (new := results.get(lookup, lookup.requirement)) != lookup.requirement
        }
        loader.update_file(filename, changes)
    return successful and resolved


def _load_lookups(
    loader: Loader, filename: Path, settings: _IndexSettings, *, pre_release: bool | None
) -> list[Lookup] | None:
    try:
        entries = list(loader.load(filename))
        # prefer a PEP 723 script's own `requires-python` over the project's, since you run the script outside it
        floors = {entry.requires_python: python_floor(entry.requires_python) for entry in entries}
    except (OSError, ValueError, YAMLError, ConfigParserError) as exc:
        sys.stderr.write(f"failed to read {filename} with {exc!r}\n")
        return None
    project = _get_project(filename.resolve().parent)
    # uv reads `[tool.uv]` for the project's own pyproject.toml; pip installs the other files
    own_uv = project.uv if filename.resolve() == project.pyproject else None
    pre_release = loader.default_pre_release if pre_release is None else pre_release
    lookups: dict[Lookup, None] = {}
    for entry in entries:
        if (name := entry.spec.strip()) and (indexes := _entry_indexes(name, entry, project, own_uv, settings)):
            floor = project.python_floor if entry.requires_python is None else floors[entry.requires_python]
            lookups[Lookup(name, entry.pkg_type, pre_release, floor, indexes)] = None
    return list(lookups)


def _entry_indexes(
    name: str, entry: Entry, project: _Project, own_uv: UvIndexes | None, settings: _IndexSettings
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


def _python_indexes(name: str, uv: UvIndexes | None, default: str, pip_extras: tuple[str, ...]) -> IndexLookup | None:
    package = canonicalize_name(name)
    if uv is None:  # pip installs the file, and merges its extra indexes with the default one
        return IndexLookup(default, extra=pip_extras)
    if package not in uv.sources:
        return IndexLookup(default, first=uv.first)
    # uv looks up a package a source pins to an index on that index alone, and skips one from git, a path or a URL
    return None if (pinned := uv.sources[package]) is None else IndexLookup(pinned)


def _resolve(settings: _IndexSettings, lookups: Sequence[Lookup]) -> tuple[dict[Lookup, str], bool]:
    if not lookups:
        return {}, True
    for pkg_type, registry in ((PkgType.PYTHON, settings.index_url), (PkgType.JS, settings.npm_registry)):
        if any(lookup.pkg_type is pkg_type for lookup in lookups):
            sys.stdout.write(f"Using {pkg_type} index: {redact_url(registry)}\n")
    changes: dict[Lookup, str] = {}
    successful = True
    parallel = min(len(lookups), 10)
    with (
        Client(
            verify=SSLContext(ssl.PROTOCOL_TLS_CLIENT),
            limits=Limits(max_keepalive_connections=parallel, max_connections=parallel),
        ) as client,
        ThreadPoolExecutor(max_workers=parallel) as executor,
    ):
        index = SimpleIndex(client)
        futures = {
            executor.submit(
                update,
                index,
                lookup,
                settings.npm.authorization(lookup.indexes.url) if lookup.pkg_type is PkgType.JS else None,
            ): lookup
            for lookup in lookups
        }
        # report in submission order to keep the output stable between runs
        for future, lookup in futures.items():
            try:
                result = future.result()
            except (HTTPError, IndexError, KeyError, TypeError, ValueError) as exc:
                successful = False
                sys.stderr.write(f"failed {lookup.requirement} with {redact_text(repr(exc))}\n")
            else:
                changes[lookup] = result
                arrow = f" -> {result}" if result != lookup.requirement else ""
                sys.stdout.write(redact_text(f"{lookup.requirement}{arrow}\n"))
    return changes, successful


def _get_project(directory: Path) -> _Project:
    pyproject = next(
        (path for folder in (directory, *directory.parents) if (path := folder / "pyproject.toml").is_file()), None
    )
    if pyproject is None:
        return _Project()
    try:
        with pyproject.open("rb") as file_handler:
            cfg = load_toml(file_handler)
        project = table(cfg, "project")
        name, requires_python = project.get("name"), project.get("requires-python")
        return _Project(
            pyproject,
            canonicalize_name(name) if isinstance(name, str) else None,
            python_floor(requires_python if isinstance(requires_python, str) else None),
            uv_project_indexes(pyproject.parent, cfg),
        )
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"ignoring project metadata from {pyproject} due to {exc!r}\n")
        return _Project(pyproject)


class _Project(NamedTuple):
    pyproject: Path | None = None
    name: str | None = None
    python_floor: Version | None = None
    uv: UvIndexes | None = None


__all__ = [
    "run",
]

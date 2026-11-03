from __future__ import annotations

import ssl
import sys
from concurrent.futures import ThreadPoolExecutor
from configparser import Error as ConfigParserError
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING

from httpx import Client, HTTPError, Limits
from truststore import SSLContext
from yaml import YAMLError

from ._config._npm import npm_settings
from ._config._pip import pip_extra_indexes
from ._config._project import IndexSettings, entry_indexes, get_project, named_indexes, python_floor
from ._loaders._registry import get_loaders
from ._lookup import Lookup, PkgType, package_type
from ._npm_registry import NpmRegistry
from ._pypi import SimpleIndex
from ._redact import redact_text, redact_url
from ._update import update

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ._cli import Options
    from ._config._project import Project
    from ._loaders._base import Loaded, Loader


def run(options: Options) -> bool:
    settings = IndexSettings(
        index_url=options.index_url,
        pip_extras=pip_extra_indexes(),
        npm_registry=options.npm_registry,
        npm=npm_settings(),
        exclude_newer=options.exclude_newer,
    )
    if options.pkgs:
        return _run_packages(
            options.pkgs, settings, pre_release=False if options.pre_release is None else options.pre_release
        )
    if (filenames := options.filenames) is None:  # discover only now, so passing packages never reads local scripts
        found = set(chain.from_iterable(loader.files for loader in get_loaders()))
        filenames = sorted(file.relative_to(Path.cwd()) for file in found)
    return _run_files(filenames, settings, pre_release=options.pre_release)


def _run_packages(packages: Sequence[str], settings: IndexSettings, *, pre_release: bool) -> bool:
    # a package you name gets the floor and the index pins of the project you run in
    project = get_project(Path.cwd())
    lookups = [_named_lookup(package, project, settings, pre_release=pre_release) for package in packages]
    return _resolve(settings, list(dict.fromkeys(lookups)))[1]


def _named_lookup(raw: str, project: Project, settings: IndexSettings, *, pre_release: bool) -> Lookup:
    package = raw.strip()
    pkg_type = package_type(package)
    indexes = named_indexes(package, pkg_type, project, settings)
    return Lookup(
        requirement=package,
        pkg_type=pkg_type,
        pre_release=pre_release,
        python_floor=project.python_floor,
        indexes=indexes,
    )


def _resolve(settings: IndexSettings, lookups: Sequence[Lookup]) -> tuple[dict[Lookup, str], bool]:
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
        index = SimpleIndex(client, settings.exclude_newer)
        npm = NpmRegistry(client, settings.exclude_newer, settings.npm)
        futures = {
            executor.submit(
                update,
                index,
                npm,
                lookup,
            ): lookup
            for lookup in lookups
        }
        # report in submission order to keep the output stable between runs
        for future, lookup in futures.items():
            try:
                result = future.result()
            except (HTTPError, TypeError, ValueError) as exc:
                successful = False
                sys.stderr.write(
                    f"failed to look up {lookup.requirement}, so it was not updated: {redact_text(repr(exc))}\n"
                )
            else:
                changes[lookup] = result
                sys.stdout.write(
                    redact_text(f"{lookup.requirement}{f' -> {result}' if result != lookup.requirement else ''}\n")
                )
    return changes, successful


def _run_files(filenames: Sequence[Path], settings: IndexSettings, *, pre_release: bool | None) -> bool:
    successful = bool(filenames)
    if not successful:
        sys.stderr.write("no supported dependency files found in the working directory; pass --file or packages\n")
    plans: list[tuple[Path, Loader, Loaded, list[Lookup]]] = []
    for filename in filenames:
        if not filename.is_file():
            sys.stderr.write(f"{filename} does not exist; pass a file that exists to --file\n")
            successful = False
        elif (loader := next((i for i in get_loaders() if i.supports(filename)), None)) is None:
            sys.stderr.write(f"{filename} is not a supported dependency file, so it was skipped\n")
            successful = False
        elif (plan := _load_lookups(loader, filename, settings, pre_release=pre_release)) is None:
            successful = False
        else:
            plans.append((filename, loader, *plan))
    # resolve the files in one batch to send one lookup per package across files
    results, resolved = _resolve(settings, list(dict.fromkeys(chain.from_iterable(lookups for *_, lookups in plans))))
    for filename, loader, loaded, lookups in plans:
        changes = {
            lookup.requirement: new
            for lookup in lookups
            if (new := results.get(lookup, lookup.requirement)) != lookup.requirement
        }
        loader.update_file(filename, changes, loaded)
    return successful and resolved


def _load_lookups(
    loader: Loader, filename: Path, settings: IndexSettings, *, pre_release: bool | None
) -> tuple[Loaded, list[Lookup]] | None:
    try:
        loaded = loader.load(filename)
        # prefer a PEP 723 script's own `requires-python` over the project's, since you run the script outside it
        floors = {entry.requires_python: python_floor(entry.requires_python) for entry in loaded.entries}
    except (OSError, ValueError, YAMLError, ConfigParserError) as exc:
        sys.stderr.write(f"failed to read {filename}, so it was skipped: {exc!r}\n")
        return None
    project = get_project(filename.resolve().parent)
    # uv reads `[tool.uv]` for the project's own pyproject.toml; pip installs the other files
    own_uv = project.uv if filename.resolve() == project.pyproject else None
    pre_release = loader.default_pre_release if pre_release is None else pre_release
    lookups: dict[Lookup, None] = {}
    for entry in loaded.entries:
        if (name := entry.spec.strip()) and (indexes := entry_indexes(name, entry, project, own_uv, settings)):
            floor = project.python_floor if entry.requires_python is None else floors[entry.requires_python]
            lookups[
                Lookup(
                    requirement=name,
                    pkg_type=entry.pkg_type,
                    pre_release=pre_release,
                    python_floor=floor,
                    indexes=indexes,
                )
            ] = None
    return loaded, list(lookups)


__all__ = [
    "run",
]

from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from configparser import Error as ConfigParserError
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING

from httpx import HTTPError, Limits
from packaging.requirements import InvalidRequirement
from yaml import YAMLError

from ._config._npm import npm_settings
from ._config._pip import pip_extra_indexes
from ._config._project import Declared, IndexSettings, Scope, get_project, python_floor
from ._ecosystems._common._candidates import Lookup
from ._ecosystems._common._registry import get_loaders
from ._ecosystems._table import ECOSYSTEMS
from ._http._hook_manifest import hook_languages
from ._http._session import Session, new_client
from ._lookup import PkgType, package_type
from ._redact import redact_text, redact_url

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping, Sequence

    from ._cli import Options
    from ._ecosystems._common._candidates import Registry
    from ._ecosystems._common._loader import Loaded, Loader


def run(options: Options) -> bool:
    settings = IndexSettings(
        index_url=options.index_url,
        pip_extras=pip_extra_indexes(),
        npm_registry=options.npm_registry,
        npm=npm_settings(),
        exclude_newer=options.exclude_newer,
        exclude_newer_package=options.exclude_newer_package,
    )
    if options.pkgs:
        return _run_packages(
            options.pkgs, settings, pre_release=False if options.pre_release is None else options.pre_release
        )
    if (filenames := options.filenames) is None:  # discover only now, so passing packages never reads local scripts
        found = set(chain.from_iterable(loader.files for loader in get_loaders(hook_languages)))
        filenames = sorted(file.relative_to(Path.cwd()) for file in found)
    return _run_files(filenames, settings, pre_release=options.pre_release)


def _run_packages(packages: Sequence[str], settings: IndexSettings, *, pre_release: bool) -> bool:
    # a package you name gets the floor and the index pins of the project you run in
    project = get_project(Path.cwd())
    scope = Scope(settings=settings, project=project, uv=project.uv)
    lookups = [_named_lookup(package, scope, pre_release=pre_release) for package in packages]
    return _report(settings, list(dict.fromkeys(lookups)))[1]


def _named_lookup(raw: str, scope: Scope, *, pre_release: bool) -> Lookup:
    package = raw.strip()
    ecosystem = ECOSYSTEMS[pkg_type := package_type(package)]
    name = ecosystem.name(package)
    return Lookup(
        requirement=package,
        name=name,
        pkg_type=pkg_type,
        pre_release=pre_release,
        python_floor=scope.project.python_floor,
        indexes=ecosystem.route(package, name, scope),
    )


def _report(settings: IndexSettings, lookups: Sequence[Lookup]) -> tuple[dict[Lookup, str], bool]:
    for pkg_type, ecosystem in ECOSYSTEMS.items():
        if any(lookup.pkg_type is pkg_type for lookup in lookups):
            sys.stdout.write(f"Using {pkg_type} index: {redact_url(ecosystem.index_url(settings))}\n")
    changes: dict[Lookup, str] = {}
    successful = True
    for lookup, outcome in _resolve(settings, lookups):
        if isinstance(outcome, str):
            changes[lookup] = outcome
            sys.stdout.write(
                redact_text(f"{lookup.requirement}{f' -> {outcome}' if outcome != lookup.requirement else ''}\n")
            )
        else:
            successful = False
            sys.stderr.write(
                f"failed to look up {lookup.requirement}, so it was not updated: {redact_text(repr(outcome))}\n"
            )
    return changes, successful


def _resolve(
    settings: IndexSettings, lookups: Sequence[Lookup]
) -> Iterator[tuple[Lookup, str | HTTPError | TypeError | ValueError]]:
    if not lookups:
        return
    parallel = min(len(lookups), 10)
    with (
        new_client(limits=Limits(max_keepalive_connections=parallel, max_connections=parallel)) as client,
        ThreadPoolExecutor(max_workers=parallel) as executor,
    ):
        session = Session(client)
        registries = {pkg_type: ecosystem.registry(session, settings) for pkg_type, ecosystem in ECOSYSTEMS.items()}
        futures = [(lookup, executor.submit(_bump, registries, lookup)) for lookup in lookups]
        # yield in submission order to keep the report stable between runs
        for lookup, future in futures:
            try:
                yield lookup, future.result()
            except (HTTPError, TypeError, ValueError) as exc:
                yield lookup, exc


def _bump(registries: Mapping[PkgType, Registry], lookup: Lookup) -> str:
    return ECOSYSTEMS[lookup.pkg_type].bump(lookup.requirement, registries[lookup.pkg_type].candidates(lookup))


def _run_files(filenames: Sequence[Path], settings: IndexSettings, *, pre_release: bool | None) -> bool:
    successful = bool(filenames)
    if not successful:
        sys.stderr.write("no supported dependency files found in the working directory; pass --file or packages\n")
    plans: list[tuple[Path, Loader, Loaded, list[Lookup]]] = []
    for filename in filenames:
        if not filename.is_file():
            sys.stderr.write(f"{filename} does not exist; pass a file that exists to --file\n")
            successful = False
        elif (loader := next((i for i in get_loaders(hook_languages) if i.supports(filename)), None)) is None:
            sys.stderr.write(f"{filename} is not a supported dependency file, so it was skipped\n")
            successful = False
        elif (plan := _load_lookups(loader, filename, settings, pre_release=pre_release)) is None:
            successful = False
        else:
            plans.append((filename, loader, *plan))
    # resolve the files in one batch to send one lookup per package across files
    results, resolved = _report(settings, list(dict.fromkeys(chain.from_iterable(lookups for *_, lookups in plans))))
    for filename, loader, loaded, lookups in plans:
        changes = {
            lookup.requirement: new
            for lookup in lookups
            if (new := results.get(lookup, lookup.requirement)) != lookup.requirement
        }
        loader.update_file(filename, loaded, changes)
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
        if not (requirement := entry.spec.strip()):
            continue
        ecosystem = ECOSYSTEMS[entry.pkg_type]
        try:
            name = ecosystem.name(requirement)
        except InvalidRequirement:  # skip entries without a project name, such as local paths and URLs
            continue
        declared = Declared(settings=settings, project=project, uv=own_uv, entry=entry)
        if indexes := ecosystem.entry_route(requirement, name, declared):
            floor = project.python_floor if entry.requires_python is None else floors[entry.requires_python]
            lookups[
                Lookup(
                    requirement=requirement,
                    name=name,
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

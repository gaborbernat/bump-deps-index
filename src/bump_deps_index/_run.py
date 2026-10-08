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
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import Version
from truststore import SSLContext
from yaml import YAMLError

from bump_deps_index._config import npm_settings, pip_extra_indexes, uv_project_indexes
from bump_deps_index._loaders import get_loaders

from ._spec import PkgType, UpdateConfig, package_type, redact_text, redact_url
from ._spec import update as update_spec

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ._cli import Options
    from ._config import NpmSettings, UvIndexes
    from ._loaders import Loader


def run(opt: Options) -> bool:
    """Update dependencies selected by the CLI options."""
    pre_release = {"yes": True, "no": False, "file-default": None}[opt.pre_release]

    indexes = _IndexSettings(npm_settings(), pip_extra_indexes())
    if opt.pkgs:
        # a package you name gets the floor and the index pins of the project you run in
        project = _get_project(Path.cwd())
        pre_release = False if pre_release is None else pre_release
        specs = list({
            _named_spec(package, project, opt, indexes, pre_release=pre_release): None
            for package in (raw.strip() for raw in opt.pkgs)
        })
        _, successful = _calculate_update(opt, indexes.npm, specs)
        return successful

    successful = bool(opt.filenames)
    if not successful:
        sys.stderr.write("no supported dependency files found\n")
    plans: list[tuple[Path, Loader, list[_Spec]]] = []
    for filename in opt.filenames:
        if not filename.is_file():
            sys.stderr.write(f"{filename} does not exist\n")
            successful = False
        elif (loader := next((i for i in get_loaders() if i.supports(filename)), None)) is None:
            sys.stderr.write(f"we do not support {filename}\n")
            successful = False
        elif (specs := _load_specs(loader, filename, pre_release=pre_release, opt=opt, indexes=indexes)) is None:
            successful = False
        else:
            plans.append((filename, loader, specs))

    # resolve the files in one batch to send one lookup per package across files
    results, resolved = _calculate_update(
        opt, indexes.npm, list(dict.fromkeys(chain.from_iterable(specs for _, _, specs in plans)))
    )
    for filename, loader, specs in plans:
        changes = {
            spec.requirement: new for spec in specs if (new := results.get(spec, spec.requirement)) != spec.requirement
        }
        loader.update_file(filename, changes)
    return successful and resolved


def _named_spec(package: str, project: _Project, opt: Options, indexes: _IndexSettings, *, pre_release: bool) -> _Spec:
    if package_type(package) is PkgType.JS:
        registry = indexes.npm.registry(package, opt.npm_registry)
        return _Spec(package, PkgType.JS, pre_release, project.python_floor, registry)
    # `package_type` parsed the requirement before it chose Python; a package from git, a path or a URL gets the default
    lookup = _python_indexes(Requirement(package).name, project.uv, opt.index_url, indexes.pip_extras)
    return _Spec(package, PkgType.PYTHON, pre_release, project.python_floor, *(lookup or (opt.index_url,)))


def _python_indexes(
    name: str, uv: UvIndexes | None, default: str, pip_extras: tuple[str, ...]
) -> tuple[str, tuple[str, ...], tuple[str, ...]] | None:
    package = canonicalize_name(name)
    if uv is None:  # pip installs the file, and merges its extra indexes with the default one
        return default, (), pip_extras
    if package not in uv.sources:
        return default, uv.first, ()
    # uv looks up a package a source pins to an index on that index alone, and skips one from git, a path or a URL
    return None if (pinned := uv.sources[package]) is None else (pinned, (), ())


def _calculate_update(opt: Options, npm: NpmSettings, specs: Sequence[_Spec]) -> tuple[dict[_Spec, str], bool]:
    changes: dict[_Spec, str] = {}
    successful = True
    if specs:
        for of_type, pkg_type, registry in (
            ("Python", PkgType.PYTHON, opt.index_url),
            ("JavaScript", PkgType.JS, opt.npm_registry),
        ):
            if any(spec.pkg_type is pkg_type for spec in specs):
                sys.stdout.write(f"Using {of_type} index: {redact_url(registry)}\n")
        parallel = min(len(specs), 10)
        with (
            Client(
                verify=SSLContext(ssl.PROTOCOL_TLS_CLIENT),
                limits=Limits(max_keepalive_connections=parallel, max_connections=parallel),
            ) as client,
            ThreadPoolExecutor(max_workers=parallel) as executor,
        ):
            future_to_spec = {
                executor.submit(
                    update_spec,
                    client,
                    spec.requirement,
                    spec.pkg_type,
                    UpdateConfig(
                        index_url=spec.index_url,
                        authorization=npm.authorization(spec.index_url) if spec.pkg_type is PkgType.JS else None,
                        pre_release=spec.pre_release,
                        python_version=spec.python_floor,
                        first_index_urls=spec.first_index_urls,
                        extra_index_urls=spec.extra_index_urls,
                    ),
                ): spec
                for spec in specs
            }
            # report in submission order to keep the output stable between runs
            for future, spec in future_to_spec.items():
                try:
                    result = future.result()
                except (HTTPError, IndexError, KeyError, TypeError, ValueError) as exc:
                    successful = False
                    sys.stderr.write(f"failed {spec.requirement} with {redact_text(repr(exc))}\n")
                else:
                    changes[spec] = result
                    sys.stdout.write(
                        redact_text(f"{spec.requirement}{f' -> {result}' if result != spec.requirement else ''}\n")
                    )
    return changes, successful


def _load_specs(
    loader: Loader,
    filename: Path,
    *,
    pre_release: bool | None,
    opt: Options,
    indexes: _IndexSettings,
) -> list[_Spec] | None:
    try:
        entries = list(loader.load(filename, pre_release=pre_release))
        # prefer a PEP 723 script's own `requires-python` over the project's, since you run the script outside it
        floors = {entry.requires_python: _python_floor(entry.requires_python) for entry in entries}
    except (OSError, ValueError, YAMLError, ConfigParserError) as exc:
        sys.stderr.write(f"failed to read {filename} with {exc!r}\n")
        return None
    project = _get_project(filename.resolve().parent)
    # uv reads `[tool.uv]` for the project's own pyproject.toml; pip installs the other files
    own_uv = project.uv if filename.resolve() == project.pyproject else None
    specs: dict[_Spec, None] = {}
    for entry in entries:
        if not (name := entry.spec.strip()):
            continue
        if entry.pkg_type is PkgType.JS:
            lookup = (indexes.npm.registry(name, opt.npm_registry),)
        else:
            try:
                requirement = Requirement(name)
            except InvalidRequirement:  # skip entries without a project name, such as local paths and URLs
                continue
            # skip the project itself, though a script may depend on it, and packages from git, a path or a URL
            if (entry.uv is None and canonicalize_name(requirement.name) == project.name) or (
                lookup := _python_indexes(
                    requirement.name,
                    own_uv if entry.uv is None else entry.uv,
                    entry.index_url or opt.index_url,
                    (*indexes.pip_extras, *entry.extra_index_urls),
                )
            ) is None:
                continue
        floor = project.python_floor if entry.requires_python is None else floors[entry.requires_python]
        specs[_Spec(name, entry.pkg_type, entry.pre_release, floor, *lookup)] = None
    return list(specs)


def _get_project(directory: Path) -> _Project:
    pyproject = next(
        (path for folder in (directory, *directory.parents) if (path := folder / "pyproject.toml").is_file()), None
    )
    if pyproject is None:
        return _Project(None, None, None, None)
    try:
        with pyproject.open("rb") as file_handler:
            cfg = load_toml(file_handler)
        project = project if isinstance(project := cfg.get("project"), dict) else {}
        name, requires_python = project.get("name"), project.get("requires-python")
        return _Project(
            pyproject,
            canonicalize_name(name) if isinstance(name, str) else None,
            _python_floor(requires_python if isinstance(requires_python, str) else None),
            uv_project_indexes(pyproject.parent, cfg),
        )
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"ignoring project metadata from {pyproject} due to {exc!r}\n")
        return _Project(pyproject, None, None, None)


class _IndexSettings(NamedTuple):
    npm: NpmSettings
    pip_extras: tuple[str, ...]


class _Project(NamedTuple):
    pyproject: Path | None
    name: str | None
    python_floor: Version | None
    uv: UvIndexes | None


def _python_floor(requires_python: str | None) -> Version | None:
    bounds = [
        _lower_bound(specifier.operator, specifier.version)
        for specifier in SpecifierSet(requires_python or "")
        if specifier.operator in {"==", ">", ">=", "~="}
    ]
    if not bounds:
        return None
    floor = max(bounds)
    specifiers = SpecifierSet(requires_python or "")
    for excluded in specifiers:
        if (
            excluded.operator == "!="
            and excluded.version.endswith(".*")
            and floor in SpecifierSet(f"=={excluded.version}")
        ):
            prefix = Version(excluded.version.removesuffix(".*")).release
            floor = Version(".".join(str(part) for part in (*prefix[:-1], prefix[-1] + 1)))
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
        return Version(".".join(str(part) for part in version.release))
    return _next_release(version)


def _next_release(version: Version) -> Version:
    release = (*version.release, *(0 for _ in range(3 - len(version.release))))
    return Version(".".join(str(part) for part in (*release[:-1], release[-1] + 1)))


class _Spec(NamedTuple):
    requirement: str
    pkg_type: PkgType
    pre_release: bool
    python_floor: Version | None
    index_url: str
    first_index_urls: tuple[str, ...] = ()
    extra_index_urls: tuple[str, ...] = ()


__all__ = [
    "run",
]

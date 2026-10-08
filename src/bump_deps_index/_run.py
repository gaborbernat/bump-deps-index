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

from bump_deps_index._config import npm_settings, uv_sources
from bump_deps_index._loaders import get_loaders

from ._spec import PkgType, UpdateConfig, package_type, redact_text, redact_url
from ._spec import update as update_spec

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ._cli import Options
    from ._config import NpmSettings
    from ._loaders import Loader


def run(opt: Options) -> bool:
    """Update dependencies selected by the CLI options."""
    pre_release = {"yes": True, "no": False, "file-default": None}[opt.pre_release]

    npm = npm_settings()
    if opt.pkgs:
        python_floor = _get_project(Path.cwd()).python_floor
        pre_release = False if pre_release is None else pre_release
        specs = list({
            _Spec(
                package,
                pkg_type := package_type(package),
                pre_release,
                python_floor,
                opt.index_url if pkg_type is PkgType.PYTHON else npm.registry(package, opt.npm_registry),
            ): None
            for package in (raw.strip() for raw in opt.pkgs)
        })
        _, successful = _calculate_update(opt, npm, specs)
        return successful

    if not opt.filenames:
        sys.stderr.write("no supported dependency files found\n")
    successful = True
    plans: list[tuple[Path, Loader, list[_Spec]]] = []
    for filename in opt.filenames:
        if not filename.is_file():
            sys.stderr.write(f"{filename} does not exist\n")
            successful = False
        elif (loader := next((i for i in get_loaders() if i.supports(filename)), None)) is None:
            sys.stderr.write(f"we do not support {filename}\n")
            successful = False
        elif (specs := _load_specs(loader, filename, pre_release=pre_release, opt=opt, npm=npm)) is None:
            successful = False
        else:
            plans.append((filename, loader, specs))

    # resolve the files in one batch to send one lookup per package across files
    results, resolved = _calculate_update(
        opt, npm, list(dict.fromkeys(chain.from_iterable(specs for _, _, specs in plans)))
    )
    for filename, loader, specs in plans:
        loader.update_file(filename, {spec.requirement: results[spec] for spec in specs if spec in results})
    return successful and resolved


class _Spec(NamedTuple):
    requirement: str
    pkg_type: PkgType
    pre_release: bool
    python_floor: Version | None
    index_url: str


class _Project(NamedTuple):
    name: str | None
    python_floor: Version | None
    sources: dict[str, str | None]


def _get_project(directory: Path) -> _Project:
    pyproject = next(
        (path for folder in (directory, *directory.parents) if (path := folder / "pyproject.toml").is_file()), None
    )
    if pyproject is None:
        return _Project(None, None, {})
    try:
        with pyproject.open("rb") as file_handler:
            cfg = load_toml(file_handler)
        # treat a wrongly typed field as missing; the run still works for the files around it
        project = project if isinstance(project := cfg.get("project"), dict) else {}
        name, requires_python = project.get("name"), project.get("requires-python")
        return _Project(
            canonicalize_name(name) if isinstance(name, str) else None,
            _python_floor(requires_python if isinstance(requires_python, str) else None),
            uv_sources(pyproject.parent, cfg),
        )
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"ignoring project metadata from {pyproject} due to {exc!r}\n")
        return _Project(None, None, {})


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
    loader: Loader, filename: Path, *, pre_release: bool | None, opt: Options, npm: NpmSettings
) -> list[_Spec] | None:
    try:
        entries = list(loader.load(filename, pre_release=pre_release))
        # prefer a PEP 723 script's own `requires-python` over the project's, since you run the script outside it
        floors = {requires: _python_floor(requires) for *_, requires in entries if requires is not None}
    except (OSError, ValueError, YAMLError, ConfigParserError) as exc:
        sys.stderr.write(f"failed to read {filename} with {exc!r}\n")
        return None
    project = _get_project(filename.resolve().parent)
    specs: dict[_Spec, None] = {}
    for raw, pkg_type, accept_prereleases, requires_python in entries:
        if not (name := raw.strip()):
            continue
        if pkg_type is PkgType.JS:
            index = npm.registry(name, opt.npm_registry)
        else:
            try:
                requirement = Requirement(name)
            except InvalidRequirement:  # skip entries without a project name, such as local paths and URLs
                continue
            # skip the project itself and packages uv installs from git, a path or a URL instead of an index
            if (package := canonicalize_name(requirement.name)) == project.name or (
                index := project.sources.get(package, opt.index_url)
            ) is None:
                continue
        floor = project.python_floor if requires_python is None else floors[requires_python]
        specs[_Spec(name, pkg_type, accept_prereleases, floor, index)] = None
    return list(specs)


__all__ = [
    "run",
]

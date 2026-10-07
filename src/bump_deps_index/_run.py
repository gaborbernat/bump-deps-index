from __future__ import annotations

import ssl
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from configparser import Error as ConfigParserError
from itertools import chain
from pathlib import Path
from tomllib import load as load_toml
from typing import TYPE_CHECKING

from httpx import Client, HTTPError, Limits
from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import Version
from truststore import SSLContext
from yaml import YAMLError

from bump_deps_index._loaders import get_loaders

from ._spec import PkgType, UpdateConfig, package_type, redact_text, redact_url
from ._spec import update as update_spec

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ._cli import Options
    from ._loaders import Loader


_Spec = tuple[str, PkgType, bool, Version | None]


def run(opt: Options) -> bool:
    """Update dependencies selected by the CLI options."""
    pre_release = {"yes": True, "no": False, "file-default": None}[opt.pre_release]

    if opt.pkgs:
        _, python_version = _get_project(Path.cwd())
        pre_release = False if pre_release is None else pre_release
        specs = list({
            (package.strip(), package_type(package.strip()), pre_release, python_version): None for package in opt.pkgs
        })
        _, successful = _calculate_update(opt.index_url, opt.npm_registry, specs)
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
        elif (specs := _load_specs(loader, filename, pre_release=pre_release)) is None:
            successful = False
        else:
            plans.append((filename, loader, specs))

    # resolve the files in one batch to send one lookup per package across files
    results, resolved = _calculate_update(
        opt.index_url, opt.npm_registry, list(dict.fromkeys(chain.from_iterable(specs for _, _, specs in plans)))
    )
    for filename, loader, specs in plans:
        loader.update_file(filename, {spec[0]: results[spec] for spec in specs if spec in results})
    return successful and resolved


def _get_project(directory: Path) -> tuple[str | None, Version | None]:
    pyproject = next(
        (path for folder in (directory, *directory.parents) if (path := folder / "pyproject.toml").is_file()), None
    )
    if pyproject is None:
        return None, None
    try:
        with pyproject.open("rb") as file_handler:
            project = load_toml(file_handler).get("project", {})
        name = project.get("name")
        return canonicalize_name(name) if name is not None else None, _python_floor(project.get("requires-python"))
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"ignoring project metadata from {pyproject} due to {exc!r}\n")
        return None, None


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


def _calculate_update(index_url: str, npm_registry: str, specs: Sequence[_Spec]) -> tuple[dict[_Spec, str], bool]:
    changes: dict[_Spec, str] = {}
    successful = True
    if specs:
        for of_type, pkg_type, registry in (
            ("Python", PkgType.PYTHON, index_url),
            ("JavaScript", PkgType.JS, npm_registry),
        ):
            if any(spec[1] is pkg_type for spec in specs):
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
                    spec[0],
                    spec[1],
                    UpdateConfig(
                        index_url=index_url,
                        npm_registry=npm_registry,
                        pre_release=spec[2],
                        python_version=spec[3],
                    ),
                ): spec
                for spec in specs
            }
            for future in as_completed(future_to_spec):
                spec = future_to_spec[future]
                try:
                    result = future.result()
                except (HTTPError, IndexError, KeyError, ValueError) as exc:
                    successful = False
                    sys.stderr.write(f"failed {spec[0]} with {redact_text(repr(exc))}\n")
                else:
                    changes[spec] = result
                    sys.stdout.write(redact_text(f"{spec[0]}{f' -> {result}' if result != spec[0] else ''}\n"))
    return changes, successful


def _load_specs(loader: Loader, filename: Path, *, pre_release: bool | None) -> list[_Spec] | None:
    try:
        entries = list(loader.load(filename, pre_release=pre_release))
        # prefer a PEP 723 script's own `requires-python` over the project's, since you run the script outside it
        floors = {requires: _python_floor(requires) for *_, requires in entries if requires is not None}
    except (OSError, ValueError, YAMLError, ConfigParserError) as exc:
        sys.stderr.write(f"failed to read {filename} with {exc!r}\n")
        return None
    project, project_floor = _get_project(filename.resolve().parent)
    specs: dict[_Spec, None] = {}
    for raw, pkg_type, accept_prereleases, requires_python in entries:
        if not (name := raw.strip()):
            continue
        if pkg_type is PkgType.PYTHON:
            try:
                requirement = Requirement(name)
            except InvalidRequirement:  # skip entries without a project name, such as local paths and URLs
                continue
            if canonicalize_name(requirement.name) == project:
                continue
        floor = project_floor if requires_python is None else floors[requires_python]
        specs[name, pkg_type, accept_prereleases, floor] = None
    return list(specs)


__all__ = [
    "run",
]

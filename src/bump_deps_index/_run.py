from __future__ import annotations

import ssl
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from tomllib import load as load_toml
from typing import TYPE_CHECKING

from httpx import Client, HTTPError, Limits
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import Version
from truststore import SSLContext

from bump_deps_index._loaders import get_loaders

from ._spec import PkgType, UpdateConfig, package_type
from ._spec import update as update_spec

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from ._cli import Options


def run(opt: Options) -> bool:
    """Update dependencies selected by the CLI options."""
    pre_release = {"yes": True, "no": False, "file-default": None}[opt.pre_release]
    project, python_version = get_project()

    if opt.pkgs:
        pre_release = False if pre_release is None else pre_release
        specs = list({(package.strip(), package_type(package.strip()), pre_release): None for package in opt.pkgs})
        _, successful = calculate_update(opt.index_url, opt.npm_registry, specs, python_version)
        return successful

    successful = True
    for filename in opt.filenames:
        for loader in get_loaders():
            if loader.supports(filename):
                specs = list({
                    (name.strip(), package_type_, accept_prereleases)
                    for name, package_type_, accept_prereleases in loader.load(filename, pre_release=pre_release)
                    if name.strip()
                    and (package_type(name.strip()) is PkgType.JS or Requirement(name.strip()).name != project)
                })
                changes, file_successful = calculate_update(opt.index_url, opt.npm_registry, specs, python_version)
                loader.update_file(filename, changes)
                successful &= file_successful
                break
        else:
            msg = f"we do not support {filename}"
            raise NotImplementedError(msg)
    return successful


def get_project() -> tuple[str | None, Version | None]:
    if not (pyproject := Path.cwd() / "pyproject.toml").exists():
        return None, None
    with pyproject.open("rb") as file_handler:
        cfg = load_toml(file_handler)
    project = cfg.get("project", {})
    name = project.get("name")
    return canonicalize_name(name) if name is not None else None, _python_floor(project.get("requires-python"))


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


def calculate_update(
    index_url: str,
    npm_registry: str,
    specs: Sequence[tuple[str, PkgType, bool]],
    python_version: Version | None,
) -> tuple[Mapping[str, str], bool]:
    changes: dict[str, str] = {}
    successful = True
    if specs:
        parallel = min(len(specs), 10)
        with (
            Client(
                verify=SSLContext(ssl.PROTOCOL_TLS_CLIENT),
                limits=Limits(max_keepalive_connections=parallel, max_connections=parallel),
            ) as client,
            ThreadPoolExecutor(max_workers=parallel) as executor,
        ):
            future_to_url = {
                executor.submit(
                    update_spec,
                    client,
                    package,
                    pkg_type,
                    UpdateConfig(
                        index_url=index_url,
                        npm_registry=npm_registry,
                        pre_release=pre_release,
                        python_version=python_version,
                    ),
                ): package
                for package, pkg_type, pre_release in specs
            }
            for future in as_completed(future_to_url):
                spec = future_to_url[future]
                try:
                    result = future.result()
                except (HTTPError, IndexError, KeyError, ValueError) as exc:
                    successful = False
                    sys.stderr.write(f"failed {spec} with {exc!r}\n")
                else:
                    changes[spec] = result
                    sys.stdout.write(f"{spec}{f' -> {result}' if result != spec else ''}\n")
    return changes, successful


__all__ = [
    "run",
]

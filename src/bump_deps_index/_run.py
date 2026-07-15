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

from ._spec import PkgType, UpdateConfig
from ._spec import update as update_spec

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from ._cli import Options


def run(opt: Options) -> None:
    """
    Run via config object.

    :param opt: the configuration namespace
    """
    pre_release = {"yes": True, "no": False, "file-default": None}[opt.pre_release]
    project, python_version = get_project()

    if opt.pkgs:
        pre_release = False if pre_release is None else pre_release
        specs: list[tuple[str, PkgType, bool]] = list({
            (i.strip(), PkgType.JS if "@" in i else PkgType.PYTHON, pre_release): None for i in opt.pkgs
        })
        calculate_update(opt.index_url, opt.npm_registry, specs, python_version)
        return

    for filename in opt.filenames:
        for loader in get_loaders():
            if loader.supports(filename):
                specs = list({
                    (name.strip(), typ, pkg)
                    for name, typ, pkg in loader.load(filename, pre_release=pre_release)
                    if name.strip() and ("@" in name or Requirement(name.strip()).name != project)
                })
                changes = calculate_update(opt.index_url, opt.npm_registry, specs, python_version)
                loader.update_file(filename, changes)
                break
        else:
            msg = f"we do not support {filename}"  # pragma: no cover
            raise NotImplementedError(msg)  # pragma: no cover


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
    return max(bounds, default=None)


def _lower_bound(operator: str, raw_version: str) -> Version:
    version = Version(raw_version.removesuffix(".*"))
    if operator != ">":
        return version
    release = (*version.release, *(0 for _ in range(3 - len(version.release))))
    return Version(".".join(str(part) for part in (*release[:-1], release[-1] + 1)))


def calculate_update(
    index_url: str,
    npm_registry: str,
    specs: Sequence[tuple[str, PkgType, bool]],
    python_version: Version | None,
) -> Mapping[str, str]:
    changes: dict[str, str] = {}
    if specs:
        parallel = min(len(specs), 10)
        client = Client(
            verify=SSLContext(ssl.PROTOCOL_TLS_CLIENT),
            limits=Limits(max_keepalive_connections=parallel, max_connections=parallel),
        )
        with ThreadPoolExecutor(max_workers=parallel) as executor:
            # Start the load operations and mark each future with its URL
            future_to_url = {
                executor.submit(
                    update_spec,
                    client,
                    pkg,
                    pkg_type,
                    UpdateConfig(
                        index_url=index_url,
                        npm_registry=npm_registry,
                        pre_release=pre_release,
                        python_version=python_version,
                    ),
                ): pkg
                for pkg, pkg_type, pre_release in specs
            }
            for future in as_completed(future_to_url):
                spec = future_to_url[future]
                try:
                    res = future.result()
                except (HTTPError, IndexError, KeyError, ValueError) as exc:
                    sys.stderr.write(f"failed {spec} with {exc!r}\n")
                else:
                    changes[spec] = res
                    sys.stdout.write(f"{spec}{f' -> {res}' if res != spec else ''}\n")
    return changes


__all__ = [
    "run",
]

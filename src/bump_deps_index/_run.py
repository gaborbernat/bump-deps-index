from __future__ import annotations

import ssl
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

from httpx import Client, Limits
from truststore import SSLContext

from bump_deps_index._loaders import get_loaders

from ._spec import PkgType
from ._spec import update as update_spec

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

    from ._cli import Options


def run(opt: Options) -> None:
    """
    Run via config object.

    :param opt: the configuration namespace
    """
    pre_release = {"yes": True, "no": False, "file-default": None}[opt.pre_release]

    if opt.pkgs:
        pre_release = False if pre_release is None else pre_release
        specs: list[tuple[str, PkgType, bool]] = list({
            (i.strip(), PkgType.JS if "@" in i else PkgType.PYTHON, pre_release): None for i in opt.pkgs
        })
        calculate_update(opt.index_url, opt.npm_registry, specs)
        return

    for filename in opt.filenames:
        for loader in get_loaders():
            if loader.supports(filename):
                specs = list({
                    (name.strip(), typ, pkg)
                    for name, typ, pkg in loader.load(filename, pre_release=pre_release)
                    if name.strip()
                })
                changes = calculate_update(opt.index_url, opt.npm_registry, specs)
                update_file(filename, changes)
                break
        else:
            msg = f"we do not support {filename}"  # pragma: no cover
            raise NotImplementedError(msg)  # pragma: no cover


def update_file(filename: Path, changes: Mapping[str, str]) -> None:
    text = filename.read_text(encoding="utf-8")
    for src, dst in changes.items():
        text = text.replace(src, dst)
    filename.write_text(text, encoding="utf-8")


def calculate_update(
    index_url: str,
    npm_registry: str,
    specs: Sequence[tuple[str, PkgType, bool]],
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
                executor.submit(update_spec, client, index_url, npm_registry, pkg, pkg_type, pre_release): pkg
                for pkg, pkg_type, pre_release in specs
            }
            for future in as_completed(future_to_url):
                spec = future_to_url[future]
                try:
                    res = future.result()
                except Exception as exc:  # noqa: BLE001
                    print(f"failed {spec} with {exc!r}", file=sys.stderr)  # noqa: T201
                else:
                    changes[spec] = res
                    print(f"{spec}{f' -> {res}' if res != spec else ''}")  # noqa: T201
    return changes


__all__ = [
    "run",
]

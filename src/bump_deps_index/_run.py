from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from configparser import RawConfigParser
from typing import TYPE_CHECKING, Protocol, cast

from yaml import safe_load as load_yaml

from ._spec import PkgType
from ._spec import update as update_spec

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping, Sequence
    from pathlib import Path

    from ._cli import Options

from tomllib import load as load_toml


class _Loader(Protocol):
    def __call__(self, filename: Path, *, pre_release: bool | None) -> Iterator[tuple[str, PkgType, bool]]: ...


def run(opt: Options) -> None:
    """
    Run via config object.

    :param opt: the configuration namespace
    """
    if opt.pkgs:
        specs: dict[tuple[str, PkgType, bool], None] = {
            (i.strip(), PkgType.JS if "@" in i else PkgType.PYTHON, opt.pre_release == "yes"): None for i in opt.pkgs
        }
        calculate_update(opt.index_url, opt.npm_registry, list(specs))
    else:
        mapping: dict[str, _Loader] = {
            "pyproject.toml": load_from_pyproject_toml,
            ".pre-commit-config.yaml": load_from_pre_commit,
            "tox.ini": load_from_tox_ini,
            "setup.cfg": load_from_setup_cfg,
        }
        for filename in opt.filenames:
            is_req_txt = filename.suffix == ".txt"
            if filename.name not in mapping and not is_req_txt:
                msg = f"we do not support {filename}"  # pragma: no cover
                raise NotImplementedError(msg)  # pragma: no cover
            loader = mapping.get(filename.name, load_from_requirements_txt)
            pre_release = {"yes": True, "no": False, "file-default": None}[opt.pre_release]
            specs = {(i.strip(), t, p): None for i, t, p in loader(filename, pre_release=pre_release) if i.strip()}
            changes = calculate_update(opt.index_url, opt.npm_registry, list(specs))
            update_file(filename, changes)


def load_from_requirements_txt(filename: Path, *, pre_release: bool | None) -> Iterator[tuple[str, PkgType, bool]]:
    pre = False if pre_release is None else pre_release
    yield from _generate(filename.read_text().split("\n"), pkg_type=PkgType.PYTHON, pre_release=pre)


def load_from_pyproject_toml(filename: Path, *, pre_release: bool | None) -> Iterator[tuple[str, PkgType, bool]]:
    with filename.open("rb") as file_handler:
        cfg = load_toml(file_handler)
    yield from _generate(cfg.get("build-system", {}).get("requires", []), pkg_type=PkgType.PYTHON)
    yield from _generate(cfg.get("project", {}).get("dependencies", []), pkg_type=PkgType.PYTHON)
    pre = False if pre_release is None else pre_release
    for entries in cfg.get("project", {}).get("optional-dependencies", {}).values():
        yield from _generate(entries, pkg_type=PkgType.PYTHON, pre_release=pre)


def _generate(
    generator: Iterable[str],
    pkg_type: PkgType,
    pre_release: bool = False,  # noqa: FBT001, FBT002
) -> Iterator[tuple[str, PkgType, bool]]:
    for value in generator:
        yield value, pkg_type, pre_release


def load_from_tox_ini(filename: Path, *, pre_release: bool | None) -> Iterator[tuple[str, PkgType, bool]]:
    cfg = NoTransformConfigParser()
    cfg.read(filename)
    pre = False if pre_release is None else pre_release
    for section in cfg.sections():
        if section.startswith("testenv"):
            values = cast(list[str], cfg[section].get("deps", "").split("\n"))
            yield from _generate(values, pkg_type=PkgType.PYTHON, pre_release=pre)


def load_from_pre_commit(filename: Path, *, pre_release: bool | None) -> Iterator[tuple[str, PkgType, bool]]:
    with filename.open("rt") as file_handler:
        cfg = load_yaml(file_handler)
    pre = True if pre_release is None else pre_release
    for repo in cfg.get("repos", []) if isinstance(cfg, dict) else []:
        for hook in repo["hooks"]:
            for pkg in hook.get("additional_dependencies", []):
                yield pkg, PkgType.JS if "@" in pkg else PkgType.PYTHON, pre


def load_from_setup_cfg(filename: Path, *, pre_release: bool | None) -> Iterator[tuple[str, PkgType, bool]]:
    cfg = NoTransformConfigParser()
    cfg.read(filename)
    if cfg.has_section("options"):
        yield from _generate(cfg["options"].get("install_requires", "").split("\n"), pkg_type=PkgType.PYTHON)
    pre = False if pre_release is None else pre_release
    if cfg.has_section("options.extras_require"):
        for group in cfg["options.extras_require"].values():
            yield from _generate(group.split("\n"), pkg_type=PkgType.PYTHON, pre_release=pre)


class NoTransformConfigParser(RawConfigParser):
    def optionxform(self, s: str) -> str:  # noqa: PLR6301
        """Disable default lower-casing."""
        return s


def update_file(filename: Path, changes: Mapping[str, str]) -> None:
    text = filename.read_text()
    for src, dst in changes.items():
        text = text.replace(src, dst)
    filename.write_text(text)


def calculate_update(
    index_url: str,
    npm_registry: str,
    specs: Sequence[tuple[str, PkgType, bool]],
) -> Mapping[str, str]:
    changes: dict[str, str] = {}
    if specs:
        with ThreadPoolExecutor(max_workers=min(len(specs), 10)) as executor:
            # Start the load operations and mark each future with its URL
            future_to_url = {
                executor.submit(update_spec, index_url, npm_registry, pkg, pkg_type, pre_release): pkg
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

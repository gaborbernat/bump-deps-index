from __future__ import annotations

import sys
from collections.abc import Iterator, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from configparser import RawConfigParser
from pathlib import Path

from yaml import Loader
from yaml import load as load_yaml

from ._cli import Options
from ._spec import update as update_spec

if sys.version_info >= (3, 11):  # pragma: no cover (py311+)
    from tomllib import load as load_toml
else:  # pragma: no cover (py311+)
    from tomli import load as load_toml


def run(opt: Options) -> None:
    """
    Run via config object.

    :param opt: the configuration namespace
    """
    if opt.filename is None:
        specs: dict[str, None] = {i.strip(): None for i in opt.pkgs}
    else:
        mapping = {
            "pyproject.toml": load_from_pyproject_toml,
            ".pre-commit-config.yaml": load_from_pre_commit,
            "tox.ini": load_from_tox_ini,
            "setup.cfg": load_from_setup_cfg,
        }
        if opt.filename.name not in mapping:
            raise NotImplementedError(f"we do not support {opt.filename}")
        loader = mapping[opt.filename.name]
        specs = {i.strip(): None for i in loader(opt.filename) if i.strip()}
    changes = calculate_update(opt.index_url, list(specs))
    if opt.filename is not None:
        update_file(opt.filename, changes)


def load_from_pyproject_toml(filename: Path) -> Iterator[str]:
    with filename.open("rb") as file_handler:
        cfg = load_toml(file_handler)
    yield from cfg.get("build-system", {}).get("requires", [])
    yield from cfg.get("project", {}).get("dependencies", [])
    for entries in cfg.get("project", {}).get("optional-dependencies", {}).values():
        yield from entries


def load_from_tox_ini(filename: Path) -> Iterator[str]:
    cfg = NoTransformConfigParser()
    cfg.read(filename)
    for section in cfg.sections():
        if section.startswith("testenv"):
            yield from cfg[section].get("deps", "").split("\n")


def load_from_pre_commit(filename: Path) -> Iterator[str]:
    with filename.open("rt") as file_handler:
        cfg = load_yaml(file_handler, Loader)
    for repo in cfg.get("repos", []) if isinstance(cfg, dict) else []:
        for hook in repo["hooks"]:
            yield from (i for i in hook.get("additional_dependencies", []) if "@" not in i)  # JS dependency


def load_from_setup_cfg(filename: Path) -> Iterator[str]:
    cfg = NoTransformConfigParser()
    cfg.read(filename)
    if cfg.has_section("options"):
        yield from cfg["options"].get("install_requires", "").split("\n")
    if cfg.has_section("options.extras_require"):
        for group in cfg["options.extras_require"].values():
            yield from group.split("\n")


class NoTransformConfigParser(RawConfigParser):
    def optionxform(self, s: str) -> str:
        """disable default lower-casing"""
        return s


def update_file(filename: Path, changes: Mapping[str, str]) -> None:
    text = filename.read_text()
    for src, dst in changes.items():
        text = text.replace(src, dst)
    filename.write_text(text)


def calculate_update(index_url: str, specs: Sequence[str]) -> Mapping[str, str]:
    changes: dict[str, str] = {}
    if specs:
        with ThreadPoolExecutor(max_workers=min(len(specs), 10)) as executor:
            # Start the load operations and mark each future with its URL
            future_to_url = {executor.submit(update_spec, index_url, spec): spec for spec in specs}
            for future in as_completed(future_to_url):
                spec = future_to_url[future]
                try:
                    res = future.result()
                except Exception as exc:
                    print(f"failed {spec} with {exc!r}", file=sys.stderr)
                else:
                    changes[spec] = res
                    print(f"{spec}{f' -> {res}' if res != spec else ''}")
    return changes


__all__ = [
    "run",
]

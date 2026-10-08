from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING, NamedTuple
from urllib.parse import quote, urlsplit

from packaging.utils import canonicalize_name

from bump_deps_index._parsed import mappings, strings, table

from ._files import read_toml, user_uv_settings

if TYPE_CHECKING:
    from pathlib import Path

    from bump_deps_index._parsed import Parsed


def uv_project_indexes(folder: Path, pyproject: dict[str, Parsed]) -> UvIndexes:
    # a workspace member inherits the sources and indexes of the workspace root, and overrides them
    folders = [*_workspace_root(folder), (folder, table(pyproject, "tool", "uv"))]
    layers = [(uv, read_toml(path / "uv.toml")) for path, uv in folders]
    # uv reads `uv.toml` over the `[tool.uv]` table next to it
    return UvIndexes(_sources(layers), _first_indexes([uv for layer in reversed(layers) for uv in reversed(layer)]))


def _workspace_root(folder: Path) -> list[tuple[Path, dict[str, Parsed]]]:
    for parent in folder.parents:
        if "workspace" in (uv := table(read_toml(parent / "pyproject.toml"), "tool", "uv")):
            return [(parent, uv)]
    return []


def _sources(layers: list[tuple[dict[str, Parsed], dict[str, Parsed]]]) -> dict[str, str | None]:
    named = {
        name: url
        for uv, uv_toml in layers
        for index in (*_indexes(uv), *_indexes(uv_toml))
        if isinstance(name := index.get("name"), str) and (url := _index_url(index))
    }
    sources: dict[str, str | None] = {}
    for package, source in (item for uv, _ in layers for item in table(uv, "sources").items()):
        # a list splits the source by environment markers
        entry = next(iter(source), None) if isinstance(source, list) else source
        index = entry.get("index") if isinstance(entry, dict) else None
        sources[canonicalize_name(package)] = named.get(index) if isinstance(index, str) else None
    return sources


def _first_indexes(settings: list[dict[str, Parsed]]) -> tuple[str, ...]:
    # uv ranks the indexes of the environment above those of the project, and those above the user's
    env = [
        _env_index(entry) for name in ("UV_INDEX", "UV_EXTRA_INDEX_URL") for entry in os.environ.get(name, "").split()
    ]
    return tuple(dict.fromkeys([*env, *(url for uv in [*settings, user_uv_settings()] for url in _extra_indexes(uv))]))


def _env_index(entry: str) -> str:
    # `UV_INDEX` takes `<name>=<url>` entries, and a named index reads its credentials from the environment
    if "=" not in entry.partition("://")[0]:
        return entry
    name, _, url = entry.partition("=")
    return _with_credentials(name, url)


def _extra_indexes(uv: dict[str, Parsed]) -> list[str]:
    # uv reads an explicit index only for the packages a source pins to it
    return [
        *(
            url
            for index in _indexes(uv)
            if index.get("default") is not True and index.get("explicit") is not True and (url := _index_url(index))
        ),
        *strings(uv.get("extra-index-url")),
    ]


class UvIndexes(NamedTuple):
    sources: dict[str, str | None]
    """The index each source pins a package to, or None for a package from git, a path or a URL."""
    first: tuple[str, ...]
    """The indexes uv checks before its default one; it takes a package from the first that has it."""


def script_uv_indexes(metadata: dict[str, Parsed]) -> tuple[UvIndexes, str | None]:
    # `uv run --script` reads the `[tool.uv]` table of the script, outside any project
    uv = table(metadata, "tool", "uv")
    return UvIndexes(_sources([(uv, {})]), _first_indexes([uv])), default_index(uv)


def uv_settings(folder: Path) -> dict[str, Parsed]:
    # uv reads `uv.toml` over the `[tool.uv]` table next to it
    if (uv_toml := folder / "uv.toml").is_file():
        return read_toml(uv_toml)
    return table(read_toml(folder / "pyproject.toml"), "tool", "uv")


def default_index(uv: dict[str, Parsed]) -> str | None:
    default = next((url for index in _indexes(uv) if index.get("default") is True and (url := _index_url(index))), None)
    return default or (url if isinstance(url := uv.get("index-url"), str) else None)


def _indexes(uv: dict[str, Parsed]) -> list[dict[str, Parsed]]:
    return mappings(uv.get("index"))


def _index_url(index: dict[str, Parsed]) -> str | None:
    if not isinstance(url := index.get("url"), str):
        return None
    return _with_credentials(name, url) if isinstance(name := index.get("name"), str) else url


def _with_credentials(name: str, url: str) -> str:
    # uv reads the credentials of a named index from `UV_INDEX_<NAME>_USERNAME` and `UV_INDEX_<NAME>_PASSWORD`
    prefix = f"UV_INDEX_{re.sub(r'[^A-Za-z0-9]', '_', name).upper()}"
    username, password = (os.environ.get(f"{prefix}_{part}", "") for part in ("USERNAME", "PASSWORD"))
    if not (username or password):
        return url
    parsed = urlsplit(url)
    userinfo = f"{quote(username, safe='')}:{quote(password, safe='')}"
    return parsed._replace(netloc=f"{userinfo}@{parsed.netloc.rpartition('@')[2]}").geturl()


__all__ = [
    "UvIndexes",
    "default_index",
    "script_uv_indexes",
    "uv_project_indexes",
    "uv_settings",
]

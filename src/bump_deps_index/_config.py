from __future__ import annotations

import os
import re
from configparser import ConfigParser
from configparser import Error as ConfigParserError
from dataclasses import dataclass
from pathlib import Path
from tomllib import TOMLDecodeError
from tomllib import load as load_toml
from typing import TYPE_CHECKING, Final
from urllib.parse import quote, urlsplit

from packaging.utils import canonicalize_name

from bump_deps_index._parsed import expand_env, table

if TYPE_CHECKING:
    from collections.abc import Mapping

    from bump_deps_index._parsed import Parsed

# npm prefers a token over a basic credential for the same registry, so the token comes last to override it
_NPM_CREDENTIALS: Final[dict[str, str]] = {":_auth": "Basic", ":_authToken": "Bearer"}


def python_index_url() -> str:
    names = ("PIP_INDEX_URL", "UV_DEFAULT_INDEX", "UV_INDEX_URL")
    if env := next((value for name in names if (value := os.environ.get(name))), None):
        return env
    # rank the project's uv settings above the user's pip and uv settings, as the more specific choice
    cwd = Path.cwd()
    project = next((url for folder in (cwd, *cwd.parents) if (url := _default_index(_uv_settings(folder)))), None)
    user = _default_index(_read_toml(_config_home() / "uv" / "uv.toml"))
    return project or _pip_index() or user or "https://pypi.org/simple"


def _uv_settings(folder: Path) -> dict[str, Parsed]:
    # uv reads `uv.toml` over the `[tool.uv]` table next to it
    if (uv_toml := folder / "uv.toml").is_file():
        return _read_toml(uv_toml)
    return table(_read_toml(folder / "pyproject.toml"), "tool", "uv")


def _pip_index() -> str | None:
    home, config_home = Path.home(), _config_home()
    # pip skips the user files when `PIP_CONFIG_FILE` names a file, the null device included
    config_file = os.environ.get("PIP_CONFIG_FILE", "")
    user = [
        home / ".pip" / "pip.conf",
        home / "Library" / "Application Support" / "pip" / "pip.conf",
        config_home / "pip" / "pip.conf",
        config_home / "pip" / "pip.ini",
    ]
    skip_user = config_file == os.devnull or (bool(config_file) and Path(config_file).is_file())
    # pip lets a later file override an earlier one, and an `[install]` value beat a `[global]` one in any file
    cfg = ConfigParser(interpolation=None)
    for file in [*([] if skip_user else user), *filter(None, [config_file])]:
        try:
            cfg.read(file, encoding="utf-8")
        except (ConfigParserError, UnicodeDecodeError):
            continue
    # pip reads `index_url` as `index-url`
    return next(
        (
            url
            for section in ("install", "global")
            for key in ("index-url", "index_url")
            if (url := cfg.get(section, key, fallback=None))
        ),
        None,
    )


def _config_home() -> Path:
    if "APPDATA" in os.environ:
        return Path(os.environ["APPDATA"])
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")


def npm_registry() -> str:
    return _npm_env("NPM_CONFIG_REGISTRY") or _npmrc().get("registry") or "https://registry.npmjs.org"


def npm_settings() -> NpmSettings:
    values = _npmrc()
    return NpmSettings(
        registry_by_scope={
            key.removesuffix(":registry"): value
            for key, value in values.items()
            if key.startswith("@") and key.endswith(":registry")
        },
        authorization_by_key={
            key.removesuffix(suffix): f"{scheme} {value}"
            for suffix, scheme in _NPM_CREDENTIALS.items()
            for key, value in values.items()
            if key.startswith("//") and key.endswith(suffix)
        },
    )


def _npmrc() -> dict[str, str]:
    user = Path(_npm_env("NPM_CONFIG_USERCONFIG") or Path.home() / ".npmrc")
    # the project file overrides the user file
    return {**_read_npmrc(user), **_read_npmrc(Path.cwd() / ".npmrc")}


def _npm_env(name: str) -> str | None:
    # npm reads its settings from the environment in any letter case, such as `npm_config_registry`
    return next((value for key, value in os.environ.items() if key.upper() == name and value), None)


def _read_npmrc(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return {}
    # npm keeps the last assignment of a key
    return {
        key.strip(): _npmrc_value(value)
        for key, separator, value in (line.partition("=") for line in lines)
        if separator and not key.lstrip().startswith(("#", ";"))
    }


def _npmrc_value(raw: str) -> str:
    value = raw.strip()
    # npm drops a `;` or `#` comment after an unquoted value, and substitutes `${NAME}` from the environment
    if len(value) > 1 and value[0] in {"'", '"'} and value.endswith(value[0]):
        value = value[1:-1]
    else:
        value = re.split(r"[;#]", value, maxsplit=1)[0].rstrip()
    return expand_env(value)


@dataclass(frozen=True)
class NpmSettings:
    registry_by_scope: Mapping[str, str]
    authorization_by_key: Mapping[str, str]

    def registry(self, spec: str, default: str) -> str:
        return self.registry_by_scope.get(spec.partition("/")[0], default) if spec.startswith("@") else default

    def authorization(self, registry: str) -> str | None:
        parsed = urlsplit(registry)
        host, parts = parsed.netloc.rpartition("@")[2], [part for part in parsed.path.split("/") if part]
        # npm walks up the registry path one segment at a time and sends the first credential it finds
        for depth in range(len(parts), -1, -1):
            key = "".join((f"//{host}", *(f"/{part}" for part in parts[:depth])))
            if value := self.authorization_by_key.get(f"{key}/") or self.authorization_by_key.get(key):
                return value
        return None


def uv_sources(folder: Path, pyproject: dict[str, Parsed]) -> dict[str, str | None]:
    # a workspace member inherits the sources and indexes of the workspace root, and overrides them
    layers = [*_workspace_root(folder), (folder, table(pyproject, "tool", "uv"))]
    return _sources([(uv, _read_toml(path / "uv.toml")) for path, uv in layers])


def _workspace_root(folder: Path) -> list[tuple[Path, dict[str, Parsed]]]:
    for parent in folder.parents:
        if "workspace" in (uv := table(_read_toml(parent / "pyproject.toml"), "tool", "uv")):
            return [(parent, uv)]
    return []


def _read_toml(path: Path) -> dict[str, Parsed]:
    # skip a malformed file like a missing one; a crash here stops the tool before the run starts
    try:
        with path.open("rb") as file_handler:
            return load_toml(file_handler)
    except (OSError, TOMLDecodeError):
        return {}


def script_uv_settings(metadata: dict[str, Parsed]) -> tuple[dict[str, str | None], str | None]:
    # `uv run --script` reads the `[tool.uv]` table of the script, outside any project
    uv = table(metadata, "tool", "uv")
    return _sources([(uv, {})]), _default_index(uv)


def _sources(layers: list[tuple[dict[str, Parsed], dict[str, Parsed]]]) -> dict[str, str | None]:
    named = {
        name: url
        for uv, uv_toml in layers
        for index in (*_indexes(uv), *_indexes(uv_toml))
        if isinstance(name := index.get("name"), str) and (url := _index_url(index))
    }
    sources: dict[str, str | None] = {}
    for package, source in (item for uv, _ in layers for item in table(uv, "sources").items()):
        # a list splits the source by environment markers, take its first entry
        entry = next(iter(source), None) if isinstance(source, list) else source
        index = entry.get("index") if isinstance(entry, dict) else None
        sources[canonicalize_name(package)] = named.get(index) if isinstance(index, str) else None
    return sources


def _default_index(uv: dict[str, Parsed]) -> str | None:
    default = next((url for index in _indexes(uv) if index.get("default") is True and (url := _index_url(index))), None)
    return default or (url if isinstance(url := uv.get("index-url"), str) else None)


def _indexes(uv: dict[str, Parsed]) -> list[dict[str, Parsed]]:
    return (
        [index for index in indexes if isinstance(index, dict)] if isinstance(indexes := uv.get("index"), list) else []
    )


def _index_url(index: dict[str, Parsed]) -> str | None:
    if not isinstance(url := index.get("url"), str):
        return None
    if not isinstance(name := index.get("name"), str):
        return url
    # uv reads the credentials of a named index from `UV_INDEX_<NAME>_USERNAME` and `UV_INDEX_<NAME>_PASSWORD`
    prefix = f"UV_INDEX_{re.sub(r'[^A-Za-z0-9]', '_', name).upper()}"
    if not (username := os.environ.get(f"{prefix}_USERNAME")):
        return url
    parsed = urlsplit(url)
    password = quote(os.environ.get(f"{prefix}_PASSWORD", ""), safe="")
    return parsed._replace(netloc=f"{quote(username, safe='')}:{password}@{parsed.netloc.rpartition('@')[2]}").geturl()


__all__ = [
    "NpmSettings",
    "npm_registry",
    "npm_settings",
    "python_index_url",
    "script_uv_settings",
    "uv_sources",
]

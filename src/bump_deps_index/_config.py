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

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import TypeAlias

    TomlValue: TypeAlias = "str | int | float | bool | list[TomlValue] | dict[str, TomlValue]"
    TomlTable: TypeAlias = dict[str, TomlValue]

_ENV_REFERENCE: Final = re.compile(r"\$\{(?P<name>\w+)\}")
_NPM_CREDENTIALS: Final = {":_authToken": "Bearer", ":_auth": "Basic"}


def python_index_url() -> str:
    names = ("PIP_INDEX_URL", "UV_DEFAULT_INDEX", "UV_INDEX_URL")
    if env := next((value for name in names if (value := os.environ.get(name))), None):
        return env
    # rank the project's uv settings above the user's pip and uv settings, as the more specific choice
    cwd = Path.cwd()
    project = next((url for folder in (cwd, *cwd.parents) if (url := _default_index(_uv_settings(folder)))), None)
    user = _default_index(_read_toml(_config_home() / "uv" / "uv.toml"))
    return project or _pip_index() or user or "https://pypi.org/simple"


def npm_registry() -> str:
    return os.environ.get("NPM_CONFIG_REGISTRY") or _npmrc().get("registry") or "https://registry.npmjs.org"


def npm_settings() -> NpmSettings:
    values = _npmrc()
    return NpmSettings(
        registry_by_scope={
            key.removesuffix(":registry"): value
            for key, value in values.items()
            if key.startswith("@") and key.endswith(":registry")
        },
        authorization_by_prefix={
            key.removesuffix(suffix): f"{scheme} {value}"
            for key, value in values.items()
            for suffix, scheme in _NPM_CREDENTIALS.items()
            if key.startswith("//") and key.endswith(suffix)
        },
    )


@dataclass(frozen=True)
class NpmSettings:
    registry_by_scope: Mapping[str, str]
    authorization_by_prefix: Mapping[str, str]

    def registry(self, spec: str, default: str) -> str:
        return self.registry_by_scope.get(spec.partition("/")[0], default) if spec.startswith("@") else default

    def authorization(self, registry: str) -> str | None:
        parsed = urlsplit(registry)
        # npm sends the credential with the longest `//host/path/` key that starts the registry URL
        key = f"//{parsed.netloc.rpartition('@')[2]}{parsed.path.rstrip('/')}/"
        prefix = max((prefix for prefix in self.authorization_by_prefix if key.startswith(prefix)), key=len, default="")
        return self.authorization_by_prefix.get(prefix)


def uv_sources(folder: Path, pyproject: TomlTable) -> dict[str, str | None]:
    uv = _table(pyproject, "tool", "uv")
    named = {
        name: url
        for index in (*_indexes(uv), *_indexes(_read_toml(folder / "uv.toml")))
        if isinstance(name := index.get("name"), str) and (url := _index_url(index))
    }
    sources: dict[str, str | None] = {}
    for package, source in _table(uv, "sources").items():
        # a list splits the source by environment markers, take its first entry
        entry = next(iter(source), None) if isinstance(source, list) else source
        index = entry.get("index") if isinstance(entry, dict) else None
        sources[canonicalize_name(package)] = named.get(index) if isinstance(index, str) else None
    return sources


def _uv_settings(folder: Path) -> TomlTable:
    # uv reads `uv.toml` over the `[tool.uv]` table next to it
    if (uv_toml := folder / "uv.toml").is_file():
        return _read_toml(uv_toml)
    return _table(_read_toml(folder / "pyproject.toml"), "tool", "uv")


def _read_toml(path: Path) -> TomlTable:
    # skip a malformed file like a missing one; a crash here stops the tool before the run starts
    try:
        with path.open("rb") as file_handler:
            return load_toml(file_handler)
    except (OSError, TOMLDecodeError):
        return {}


def _table(value: TomlValue, *keys: str) -> TomlTable:
    for key in keys:
        value = value.get(key, {}) if isinstance(value, dict) else {}
    return value if isinstance(value, dict) else {}


def _default_index(uv: TomlTable) -> str | None:
    default = next((url for index in _indexes(uv) if index.get("default") is True and (url := _index_url(index))), None)
    return default or (url if isinstance(url := uv.get("index-url"), str) else None)


def _indexes(uv: TomlTable) -> list[TomlTable]:
    return (
        [index for index in indexes if isinstance(index, dict)] if isinstance(indexes := uv.get("index"), list) else []
    )


def _index_url(index: TomlTable) -> str | None:
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


def _config_home() -> Path:
    if "APPDATA" in os.environ:
        return Path(os.environ["APPDATA"])
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")


def _pip_index() -> str | None:
    home, config_home = Path.home(), _config_home()
    # pip lets later files override earlier ones, so check them from the last loaded to the first
    for file in filter(
        None,
        [
            os.environ.get("PIP_CONFIG_FILE", ""),
            config_home / "pip" / "pip.ini",
            home / "Library" / "Application Support" / "pip" / "pip.conf",
            config_home / "pip" / "pip.conf",
            home / ".pip" / "pip.conf",
        ],
    ):
        cfg = ConfigParser(interpolation=None)
        try:
            cfg.read(file, encoding="utf-8")
        except (ConfigParserError, UnicodeDecodeError):
            continue
        if url := cfg.get("install", "index-url", fallback=None) or cfg.get("global", "index-url", fallback=None):
            return url
    return None


def _npmrc() -> dict[str, str]:
    user = Path(os.environ.get("NPM_CONFIG_USERCONFIG") or Path.home() / ".npmrc")
    # the project file overrides the user file
    return {**_read_npmrc(user), **_read_npmrc(Path.cwd() / ".npmrc")}


def _read_npmrc(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return {}
    # npm keeps the last assignment of a key, and substitutes `${NAME}` from the environment
    return {
        key.strip(): _ENV_REFERENCE.sub(lambda match: os.environ.get(match["name"], ""), value.strip().strip("\"'"))
        for key, separator, value in (line.partition("=") for line in lines)
        if separator and not key.lstrip().startswith(("#", ";"))
    }


__all__ = [
    "NpmSettings",
    "npm_registry",
    "npm_settings",
    "python_index_url",
    "uv_sources",
]

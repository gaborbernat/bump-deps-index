from __future__ import annotations

import os
import re
from base64 import b64decode, b64encode
from configparser import ConfigParser
from configparser import Error as ConfigParserError
from dataclasses import dataclass
from pathlib import Path
from tomllib import TOMLDecodeError
from tomllib import load as load_toml
from typing import TYPE_CHECKING, Final, NamedTuple
from urllib.parse import quote, urlsplit

from packaging.utils import canonicalize_name
from typing_extensions import override

from bump_deps_index._parsed import mappings, strings, table

if TYPE_CHECKING:
    from collections.abc import Mapping

    from bump_deps_index._parsed import Parsed

# npm reads `${NAME}` from the environment and keeps it as written when unset, and reads `${NAME?}` as empty then
_NPM_ENV_REFERENCE: Final[re.Pattern[str]] = re.compile(r"\$\{(?P<name>[^${}?]+)(?P<optional>\?)?\}")
# the token comes last to override a basic credential for the same registry
_NPM_CREDENTIALS: Final[dict[str, str]] = {":_auth": "Basic", ":_authToken": "Bearer"}


def python_index_url() -> str:
    names = ("PIP_INDEX_URL", "UV_DEFAULT_INDEX", "UV_INDEX_URL")
    if env := next((value for name in names if (value := os.environ.get(name))), None):
        return env
    # rank the project's uv settings above the user's pip and uv settings, as the more specific choice
    cwd = Path.cwd()
    project = next((url for folder in (cwd, *cwd.parents) if (url := _default_index(_uv_settings(folder)))), None)
    user = _default_index(_read_toml(_config_home() / "uv" / "uv.toml"))
    return project or _pip_setting("index-url") or user or "https://pypi.org/simple"


def pip_extra_indexes() -> tuple[str, ...]:
    return (*os.environ.get("PIP_EXTRA_INDEX_URL", "").split(), *_pip_setting("extra-index-url").split())


def _uv_settings(folder: Path) -> dict[str, Parsed]:
    # uv reads `uv.toml` over the `[tool.uv]` table next to it
    if (uv_toml := folder / "uv.toml").is_file():
        return _read_toml(uv_toml)
    return table(_read_toml(folder / "pyproject.toml"), "tool", "uv")


def _pip_setting(name: str) -> str:
    config_file = os.environ.get("PIP_CONFIG_FILE", "")
    # pip skips the user files when `PIP_CONFIG_FILE` names a file, the null device included
    skip_user = config_file == os.devnull or (bool(config_file) and Path(config_file).is_file())
    home, config_home = Path.home(), _config_home()
    user = [
        home / ".pip" / "pip.conf",
        home / "Library" / "Application Support" / "pip" / "pip.conf",
        config_home / "pip" / "pip.conf",
        config_home / "pip" / "pip.ini",
    ]
    # pip lets a later file override an earlier one, and an `[install]` value beats a `[global]` one in any file
    cfg = _PipConfigParser(interpolation=None, strict=False)
    for file in [*([] if skip_user else user), *filter(None, [config_file])]:
        try:
            cfg.read(file, encoding="utf-8")
        except (ConfigParserError, UnicodeDecodeError):
            continue
    return cfg.get("install", name, fallback="") or cfg.get("global", name, fallback="")


class _PipConfigParser(ConfigParser):
    @override
    def optionxform(self, optionstr: str) -> str:
        """Read `index_url` as `index-url`, as pip does, so the later of the two spellings wins."""
        return optionstr.lower().replace("_", "-")


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
        authorization_by_key=_npm_authorizations(values),
    )


def _npmrc() -> dict[str, str]:
    user = Path(_npm_env("NPM_CONFIG_USERCONFIG") or Path.home() / ".npmrc")
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
    return _NPM_ENV_REFERENCE.sub(
        lambda match: os.environ.get(match["name"], "" if match["optional"] else match[0]), value
    )


def _npm_authorizations(values: dict[str, str]) -> dict[str, str]:
    # npm sends a token over a `_auth` value, and that over a `username` with a base64 `_password`
    found: dict[str, str] = {}
    for key, username in values.items():
        prefix = key.removesuffix(":username")
        if key.startswith("//") and key != prefix and (basic := _basic(username, values.get(f"{prefix}:_password"))):
            found[prefix] = f"Basic {basic}"
    for suffix, scheme in _NPM_CREDENTIALS.items():
        found |= {
            key.removesuffix(suffix): f"{scheme} {value}"
            for key, value in values.items()
            if key.startswith("//") and key.endswith(suffix)
        }
    return found


def _basic(username: str, encoded_password: str | None) -> str | None:
    try:
        password = b64decode(encoded_password or "").decode()
    except ValueError:  # skip a password that is not base64, as you could not log in with it
        return None
    return b64encode(f"{username}:{password}".encode()).decode() if password else None


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


def uv_project_indexes(folder: Path, pyproject: dict[str, Parsed]) -> UvIndexes:
    # a workspace member inherits the sources and indexes of the workspace root, and overrides them
    folders = [*_workspace_root(folder), (folder, table(pyproject, "tool", "uv"))]
    layers = [(uv, _read_toml(path / "uv.toml")) for path, uv in folders]
    # uv reads `uv.toml` over the `[tool.uv]` table next to it
    return UvIndexes(_sources(layers), _first_indexes([uv for layer in reversed(layers) for uv in reversed(layer)]))


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
    user = _read_toml(_config_home() / "uv" / "uv.toml")
    return tuple(dict.fromkeys([*env, *(url for uv in [*settings, user] for url in _extra_indexes(uv))]))


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
    return UvIndexes(_sources([(uv, {})]), _first_indexes([uv])), _default_index(uv)


def _default_index(uv: dict[str, Parsed]) -> str | None:
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
    "NpmSettings",
    "UvIndexes",
    "npm_registry",
    "npm_settings",
    "pip_extra_indexes",
    "python_index_url",
    "script_uv_indexes",
    "uv_project_indexes",
]

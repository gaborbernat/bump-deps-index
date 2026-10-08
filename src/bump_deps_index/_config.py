from __future__ import annotations

import os
import re
from configparser import ConfigParser
from configparser import Error as ConfigParserError
from pathlib import Path
from tomllib import TOMLDecodeError
from tomllib import load as load_toml
from typing import Final

_ENV_REFERENCE: Final = re.compile(r"\$\{(?P<name>\w+)\}")


def python_index_url() -> str:
    names = ("PIP_INDEX_URL", "UV_DEFAULT_INDEX", "UV_INDEX_URL")
    if env := next((value for name in names if (value := os.environ.get(name))), None):
        return env
    # rank the project's uv settings above the user's pip and uv settings, as the more specific choice
    cwd = Path.cwd()
    project = next(
        (
            url
            for folder in (cwd, *cwd.parents)
            if (url := _uv_index(folder / "uv.toml") or _uv_index(folder / "pyproject.toml", "tool", "uv"))
        ),
        None,
    )
    return project or _pip_index() or _uv_index(_config_home() / "uv" / "uv.toml") or "https://pypi.org/simple"


def npm_registry() -> str:
    if env := os.environ.get("NPM_CONFIG_REGISTRY"):
        return env
    user = Path(os.environ.get("NPM_CONFIG_USERCONFIG") or Path.home() / ".npmrc")
    return _npmrc_registry(Path.cwd() / ".npmrc") or _npmrc_registry(user) or "https://registry.npmjs.org"


def _uv_index(path: Path, *table: str) -> str | None:
    try:
        with path.open("rb") as file_handler:
            cfg = load_toml(file_handler)
    except (OSError, TOMLDecodeError):
        return None
    # skip a malformed file like a missing one; a crash here stops the tool before the run starts
    for key in table:
        cfg = cfg.get(key) if isinstance(cfg, dict) else None
    if not isinstance(cfg, dict):
        return None
    indexes = [index for index in cfg.get("index", []) if isinstance(index, dict)]
    return next((index.get("url") for index in indexes if index.get("default")), None) or cfg.get("index-url")


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


def _config_home() -> Path:
    if "APPDATA" in os.environ:
        return Path(os.environ["APPDATA"])
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")


def _npmrc_registry(path: Path) -> str | None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    # npm reads the last assignment, and substitutes `${NAME}` from the environment
    values = [value for key, _, value in (line.partition("=") for line in lines) if key.strip() == "registry"]
    if not values:
        return None
    return _ENV_REFERENCE.sub(lambda match: os.environ.get(match["name"], ""), values[-1].strip().strip("\"'"))


__all__ = [
    "npm_registry",
    "python_index_url",
]

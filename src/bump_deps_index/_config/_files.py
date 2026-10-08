from __future__ import annotations

import os
from pathlib import Path
from tomllib import TOMLDecodeError
from tomllib import load as load_toml
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bump_deps_index._parsed import Parsed


def read_toml(path: Path) -> dict[str, Parsed]:
    # skip a malformed file like a missing one; a crash here stops the tool before the run starts
    try:
        with path.open("rb") as file_handler:
            return load_toml(file_handler)
    except (OSError, TOMLDecodeError):
        return {}


def config_home() -> Path:
    if "APPDATA" in os.environ:
        return Path(os.environ["APPDATA"])
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")


def user_uv_settings() -> dict[str, Parsed]:
    return read_toml(config_home() / "uv" / "uv.toml")


__all__ = [
    "config_home",
    "read_toml",
    "user_uv_settings",
]

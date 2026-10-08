from __future__ import annotations

import os
from configparser import ConfigParser
from configparser import Error as ConfigParserError
from pathlib import Path

from typing_extensions import override

from ._files import config_home


def pip_extra_indexes() -> tuple[str, ...]:
    return (*os.environ.get("PIP_EXTRA_INDEX_URL", "").split(), *pip_setting("extra-index-url").split())


def pip_setting(name: str) -> str:
    config_file = os.environ.get("PIP_CONFIG_FILE", "")
    # pip skips the user files when `PIP_CONFIG_FILE` names a file, the null device included
    skip_user = config_file == os.devnull or (bool(config_file) and Path(config_file).is_file())
    home, config_dir = Path.home(), config_home()
    user = [
        home / ".pip" / "pip.conf",
        home / "Library" / "Application Support" / "pip" / "pip.conf",
        config_dir / "pip" / "pip.conf",
        config_dir / "pip" / "pip.ini",
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


__all__ = [
    "pip_extra_indexes",
    "pip_setting",
]

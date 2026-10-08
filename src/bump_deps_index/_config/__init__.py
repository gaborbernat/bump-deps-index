from __future__ import annotations

import os
from pathlib import Path

from ._files import user_uv_settings
from ._npm import NpmSettings, npm_registry, npm_settings
from ._pip import pip_extra_indexes, pip_setting
from ._uv import UvIndexes, default_index, script_uv_indexes, uv_project_indexes, uv_settings


def python_index_url() -> str:
    names = ("PIP_INDEX_URL", "UV_DEFAULT_INDEX", "UV_INDEX_URL")
    if env := next((value for name in names if (value := os.environ.get(name))), None):
        return env
    # rank the project's uv settings above the user's pip and uv settings, as the more specific choice
    cwd = Path.cwd()
    project = next((url for folder in (cwd, *cwd.parents) if (url := default_index(uv_settings(folder)))), None)
    user = default_index(user_uv_settings())
    return project or pip_setting("index-url") or user or "https://pypi.org/simple"


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

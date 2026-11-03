from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from ._files import user_uv_settings
from ._npm import NpmSettings, npm_registry, npm_settings
from ._pip import pip_extra_indexes, pip_setting
from ._project import IndexSettings, Project, entry_indexes, get_project, named_indexes
from ._uv import UvIndexes, default_index, script_uv_indexes, uv_project_indexes, uv_settings

if TYPE_CHECKING:
    from collections.abc import Callable

    from bump_deps_index._parsed import Parsed


def python_index_url() -> str:
    names = ("PIP_INDEX_URL", "UV_DEFAULT_INDEX", "UV_INDEX_URL")
    return _python_setting(names, default_index, "index-url") or "https://pypi.org/simple"


def _python_setting(
    names: tuple[str, ...], uv_value: Callable[[dict[str, Parsed]], str | Literal[False] | None], pip_name: str
) -> str | None:
    if env := next((value for name in names if (value := os.environ.get(name))), None):
        return env
    # rank the project's uv settings above the user's pip and uv settings, as the more specific choice
    cwd = Path.cwd()
    project = next(
        (value for folder in (cwd, *cwd.parents) if (value := uv_value(uv_settings(folder))) or value is False), None
    )
    if project is False:
        return None
    user = uv_value(user_uv_settings())
    return project or pip_setting(pip_name) or user or None


def python_exclude_newer() -> str | None:
    names = ("PIP_UPLOADED_PRIOR_TO", "UV_EXCLUDE_NEWER")
    # uv accepts `exclude-newer = false` to disable the cutoff, so a false stops the lookup and a non-string is ignored
    return _python_setting(
        names,
        lambda uv: False if (value := uv.get("exclude-newer")) is False else value if isinstance(value, str) else None,
        "uploaded-prior-to",
    )


__all__ = [
    "IndexSettings",
    "NpmSettings",
    "Project",
    "UvIndexes",
    "entry_indexes",
    "get_project",
    "named_indexes",
    "npm_registry",
    "npm_settings",
    "pip_extra_indexes",
    "python_exclude_newer",
    "python_index_url",
    "script_uv_indexes",
    "uv_project_indexes",
]

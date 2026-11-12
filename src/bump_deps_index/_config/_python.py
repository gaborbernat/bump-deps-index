from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from bump_deps_index.model import table

from ._files import user_uv_settings
from ._pip import pip_setting
from ._uv import default_index, uv_settings

if TYPE_CHECKING:
    from collections.abc import Callable

    from bump_deps_index.model import Parsed


def python_index_url() -> str:
    names = ("PIP_INDEX_URL", "UV_DEFAULT_INDEX", "UV_INDEX_URL")
    return _python_setting(names, default_index, "index-url") or "https://pypi.org/simple"


def _python_setting(
    names: tuple[str, ...], uv_value: Callable[[dict[str, Parsed]], str | Literal[False] | None], pip_name: str
) -> str | None:
    if from_env := next((value for name in names if (value := os.environ.get(name))), None):
        return from_env
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
    # uv accepts `exclude-newer = false` to disable the cutoff, so a false stops the lookup and a non-string is ignored
    return _python_setting(
        ("PIP_UPLOADED_PRIOR_TO", "UV_EXCLUDE_NEWER"),
        lambda uv: False if (value := uv.get("exclude-newer")) is False else value if isinstance(value, str) else None,
        "uploaded-prior-to",
    )


def python_exclude_newer_package() -> dict[str, str | Literal[False]]:
    # uv merges the user's table under the project's, so a package named in both takes the project's cutoff
    cwd = Path.cwd()
    project = next(
        (cutoffs for folder in (cwd, *cwd.parents) if (cutoffs := _package_cutoffs(uv_settings(folder)))), {}
    )
    return {**_package_cutoffs(user_uv_settings()), **project}


def _package_cutoffs(uv: dict[str, Parsed]) -> dict[str, str | Literal[False]]:
    return {
        name: value
        for name, value in table(uv, "exclude-newer-package").items()
        if value is False or isinstance(value, str)
    }


__all__ = [
    "python_exclude_newer",
    "python_exclude_newer_package",
    "python_index_url",
]

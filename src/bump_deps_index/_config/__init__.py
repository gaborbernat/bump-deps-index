"""Settings read from config files and the environment."""

from __future__ import annotations

from ._npm import npm_registry, npm_settings
from ._pip import pip_extra_indexes
from ._project import Declared, IndexSettings, Scope, entry_indexes, get_project, named_indexes, python_floor
from ._python import python_exclude_newer, python_exclude_newer_package, python_index_url
from ._uv import UvIndexes, script_uv_indexes

__all__ = [
    "Declared",
    "IndexSettings",
    "Scope",
    "UvIndexes",
    "entry_indexes",
    "get_project",
    "named_indexes",
    "npm_registry",
    "npm_settings",
    "pip_extra_indexes",
    "python_exclude_newer",
    "python_exclude_newer_package",
    "python_floor",
    "python_index_url",
    "script_uv_indexes",
]

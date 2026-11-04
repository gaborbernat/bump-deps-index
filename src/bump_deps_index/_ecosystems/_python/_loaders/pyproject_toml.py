from __future__ import annotations

from tomllib import load as load_toml
from typing import TYPE_CHECKING, ClassVar

from typing_extensions import override

from bump_deps_index._ecosystems._common._loader import Entry, Loaded, SingleFileLoader
from bump_deps_index._lookup import PkgType
from bump_deps_index._parsed import strings, table

from ._toml_text import replace_strings

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from bump_deps_index._parsed import Parsed


class PyProjectToml(SingleFileLoader):
    filename: ClassVar[str] = "pyproject.toml"

    @override
    def load(self, filename: Path) -> Loaded:
        with filename.open("rb") as file_handler:
            cfg: Parsed = load_toml(file_handler)
        project = table(cfg, "project")
        sections = [
            (None, table(cfg, "build-system").get("requires")),
            ("project", project.get("dependencies")),
            *(("project", value) for value in table(project, "optional-dependencies").values()),
            (None, table(cfg, "tool", "uv").get("dev-dependencies")),
            *table(cfg, "dependency-groups").items(),
        ]
        return Loaded(
            entries=[
                Entry(spec=spec, pkg_type=PkgType.PYTHON, group=group)
                for group, value in sections
                for spec in strings(value)
            ],
            rewrite=self._update_text,
        )

    def _update_text(self, text: str, changes: Mapping[str, str]) -> str:
        return replace_strings(text, changes, self._is_dependency)

    @staticmethod
    def _is_dependency(path: tuple[str, ...]) -> bool:
        match path:
            case (
                ("build-system", "requires", "[]")
                | ("project", "dependencies", "[]")
                | ("project", "optional-dependencies", _, "[]")
                | ("dependency-groups", _, "[]")
                | ("tool", "uv", "dev-dependencies", "[]")
            ):
                return True
        return False


__all__ = [
    "PyProjectToml",
]

from __future__ import annotations

from tomllib import load as load_toml
from typing import TYPE_CHECKING, ClassVar

from typing_extensions import override

from bump_deps_index._parsed import strings, table
from bump_deps_index._spec import PkgType

from ._base import Entry, SingleFileLoader
from ._toml_text import replace_strings

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping
    from pathlib import Path

    from bump_deps_index._parsed import Parsed


class PyProjectToml(SingleFileLoader):
    filename: ClassVar[str] = "pyproject.toml"

    @override
    def load(self, filename: Path) -> Iterator[Entry]:
        with filename.open("rb") as file_handler:
            cfg: Parsed = load_toml(file_handler)
        project = table(cfg, "project")
        for value in (
            table(cfg, "build-system").get("requires"),
            project.get("dependencies"),
            *table(project, "optional-dependencies").values(),
            table(cfg, "tool", "uv").get("dev-dependencies"),
            *table(cfg, "dependency-groups").values(),
        ):
            yield from (Entry(spec, PkgType.PYTHON) for spec in strings(value))

    @override
    def _update_text(self, filename: Path, text: str, changes: Mapping[str, str]) -> str:
        return replace_strings(text, changes, _is_dependency)


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

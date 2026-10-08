from __future__ import annotations

from pathlib import Path
from tomllib import load as load_toml
from typing import TYPE_CHECKING, ClassVar

from bump_deps_index._spec import PkgType

from ._base import Loader
from ._toml_text import replace_strings

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

    from ._base import Entry, Parsed


class PyProjectToml(Loader):
    _filename: ClassVar[str] = "pyproject.toml"

    @property
    def files(self) -> Iterator[Path]:
        if (path := Path.cwd() / self._filename).exists():
            yield path

    def supports(self, filename: Path) -> bool:
        return filename.name == self._filename

    @staticmethod
    def _update_text(text: str, changes: Mapping[str, str]) -> str:
        return replace_strings(text, changes, _is_dependency)

    def load(self, filename: Path, *, pre_release: bool | None) -> Iterator[Entry]:
        with filename.open("rb") as file_handler:
            cfg: Parsed = load_toml(file_handler)
        project = self._table(cfg, "project")
        for value in (
            self._table(cfg, "build-system").get("requires"),
            project.get("dependencies"),
            *self._table(project, "optional-dependencies").values(),
            self._table(cfg, "tool", "uv").get("dev-dependencies"),
            *self._table(cfg, "dependency-groups").values(),
        ):
            yield from self._generate(
                self._strings(value), pkg_type=PkgType.PYTHON, pre_release=False if pre_release is None else pre_release
            )


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

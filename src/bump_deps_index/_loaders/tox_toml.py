from __future__ import annotations

from functools import cached_property
from pathlib import Path
from tomllib import load as load_toml
from typing import TYPE_CHECKING, ClassVar

from bump_deps_index._spec import PkgType

from ._base import Loader

if TYPE_CHECKING:
    from collections.abc import Iterator


class ToxToml(Loader):
    _filename: ClassVar[str] = "tox.toml"

    @cached_property
    def files(self) -> Iterator[Path]:
        if (path := Path.cwd() / self._filename).exists():
            yield path

    def supports(self, filename: Path) -> bool:
        return filename.name == self._filename

    def load(self, filename: Path, *, pre_release: bool | None) -> Iterator[tuple[str, PkgType, bool]]:  # noqa: ARG002
        with filename.open("rb") as file_handler:
            cfg = load_toml(file_handler)
        yield from self._generate(cfg.get("requires", []), pkg_type=PkgType.PYTHON)


__all__ = [
    "ToxToml",
]

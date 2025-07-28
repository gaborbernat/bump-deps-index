from __future__ import annotations

from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING

from bump_deps_index._spec import PkgType

from ._base import Loader

if TYPE_CHECKING:
    from collections.abc import Iterator


class Requirements(Loader):
    def supports(self, filename: Path) -> bool:  # noqa: PLR6301
        return (
            filename.suffix in {".in", ".txt"}
            and filename.stem.split(".")[0] == "requirements"
            and not (filename.suffix == ".txt" and filename.with_suffix(".in").exists())
        )

    @cached_property
    def files(self) -> Iterator[Path]:
        content = list(Path.cwd().iterdir())
        requirements = {i for i in content if i.stem.split(".")[0] == "requirements" and i.suffix in {".in", ".txt"}}
        names = {i.name for i in requirements}
        for filename in requirements:
            if not (filename.suffix == ".txt" and filename.with_suffix(".in").name in names):
                yield filename

    def load(self, filename: Path, *, pre_release: bool | None) -> Iterator[tuple[str, PkgType, bool]]:
        pre = False if pre_release is None else pre_release
        lines = [i.strip() for i in filename.read_text(encoding="utf-8").split("\n") if not i.strip().startswith("#")]
        yield from self._generate(lines, pkg_type=PkgType.PYTHON, pre_release=pre)


__all__ = [
    "Requirements",
]

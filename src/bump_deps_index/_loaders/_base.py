from __future__ import annotations

from abc import ABC, abstractmethod
from functools import cached_property
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator
    from pathlib import Path

    from bump_deps_index._spec import PkgType


class Loader(ABC):
    @cached_property
    @abstractmethod
    def files(self) -> Iterator[Path]:
        raise NotImplementedError

    @abstractmethod
    def supports(self, filename: Path) -> bool:
        raise NotImplementedError

    @abstractmethod
    def load(self, filename: Path, *, pre_release: bool | None) -> Iterator[tuple[str, PkgType, bool]]:
        raise NotImplementedError

    @staticmethod
    def _generate(
        generator: Iterable[str],
        pkg_type: PkgType,
        pre_release: bool = False,  # noqa: FBT001, FBT002
    ) -> Iterator[tuple[str, PkgType, bool]]:
        for value in generator:
            yield value, pkg_type, pre_release

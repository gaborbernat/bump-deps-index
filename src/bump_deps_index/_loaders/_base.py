from __future__ import annotations

import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, NamedTuple

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

    from bump_deps_index._config import UvIndexes
    from bump_deps_index._spec import PkgType


class Loader(ABC):
    default_pre_release: ClassVar[bool] = False

    @property
    @abstractmethod
    def files(self) -> Iterator[Path]:
        raise NotImplementedError

    @abstractmethod
    def supports(self, filename: Path) -> bool:
        raise NotImplementedError

    @abstractmethod
    def load(self, filename: Path) -> Iterator[Entry]:
        raise NotImplementedError

    def update_file(self, filename: Path, changes: Mapping[str, str]) -> None:
        with filename.open(encoding="utf-8", newline="") as file_handler:
            raw = file_handler.read()
        text = re.sub(r"\r\n?", "\n", raw)
        if (updated := self._update_text(filename, text, changes)) == text:
            return
        lines = updated.split("\n")
        endings = _restore_endings(raw, text.split("\n"), lines)
        with filename.open("w", encoding="utf-8", newline="") as file_handler:
            file_handler.write("".join(f"{line}{end}" for line, end in zip(lines, endings, strict=True)))

    @abstractmethod
    def _update_text(self, filename: Path, text: str, changes: Mapping[str, str]) -> str:
        raise NotImplementedError


class SingleFileLoader(Loader, ABC):
    filename: ClassVar[str]

    @property
    def files(self) -> Iterator[Path]:
        if (path := Path.cwd() / self.filename).exists():
            yield path

    def supports(self, filename: Path) -> bool:
        return filename.name == self.filename


class Entry(NamedTuple):
    spec: str
    pkg_type: PkgType
    requires_python: str | None = None
    # a PEP 723 script brings its own uv sources and indexes, since `uv run --script` resolves it outside the project
    uv: UvIndexes | None = None
    # an index the file sets for its own requirements, such as `--index-url` in a requirements file
    index_url: str | None = None
    # the extra indexes a requirements file sets with `--extra-index-url`
    extra_index_urls: tuple[str, ...] = ()


def _restore_endings(raw: str, old: list[str], new: list[str]) -> list[str]:
    # give each line back its own ending; the lines around the edits keep theirs when a rewrite joins lines
    head = next((at for at, (left, right) in enumerate(zip(old, new, strict=False)) if left != right), len(new))
    pairs = zip(reversed(old[head:]), reversed(new[head:]), strict=False)
    tail = next((at for at, (left, right) in enumerate(pairs) if left != right), min(len(old), len(new)) - head)
    endings = [*re.findall(r"\r\n?|\n", raw), ""]
    return [
        *endings[:head],
        *_fit(endings[head : len(old) - tail], len(new) - head - tail),
        *endings[len(old) - tail :],
    ]


def _fit(endings: list[str], count: int) -> list[str]:
    # keep the endings in order and the last one last, so the end of the file keeps its final newline or lack of it
    first, last = (endings[0], endings[-1]) if endings else ("\n", "\n")  # an inserted line has no old ending
    return [*[*endings[:-1], *[first] * count][: count - 1], last][:count]


__all__ = [
    "Entry",
    "Loader",
    "SingleFileLoader",
]

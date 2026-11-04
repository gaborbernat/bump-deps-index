from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator, Mapping

    from bump_deps_index._config._uv import UvIndexes
    from bump_deps_index._lookup import PkgType


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
    def load(self, filename: Path) -> Loaded:
        raise NotImplementedError

    def update_file(self, filename: Path, loaded: Loaded, changes: Mapping[str, str]) -> None:
        with filename.open(encoding="utf-8", newline="") as file_handler:
            raw = file_handler.read()
        text = re.sub(r"\r\n?", "\n", raw)
        if (updated := loaded.rewrite(text, changes)) == text:
            return
        lines = updated.split("\n")
        endings = self._restore_endings(raw, text.split("\n"), lines)
        with filename.open("w", encoding="utf-8", newline="") as file_handler:
            file_handler.write("".join(f"{line}{end}" for line, end in zip(lines, endings, strict=True)))

    @staticmethod
    def _restore_endings(raw: str, old_lines: list[str], new_lines: list[str]) -> list[str]:
        # give each line back its own ending; the lines around the edits keep theirs when a rewrite joins lines
        head = next(
            (at for at, (left, right) in enumerate(zip(old_lines, new_lines, strict=False)) if left != right),
            len(new_lines),
        )
        pairs = zip(reversed(old_lines[head:]), reversed(new_lines[head:]), strict=False)
        tail = next(
            (at for at, (left, right) in enumerate(pairs) if left != right),
            min(len(old_lines), len(new_lines)) - head,
        )
        endings = [*re.findall(r"\r\n?|\n", raw), ""]
        return [
            *endings[:head],
            *Loader._fit(endings[head : len(old_lines) - tail], len(new_lines) - head - tail),
            *endings[len(old_lines) - tail :],
        ]

    @staticmethod
    def _fit(endings: list[str], count: int) -> list[str]:
        # keep the endings in order and the last one last, so the end of the file keeps its final newline or lack of it
        first, last = (endings[0], endings[-1]) if endings else ("\n", "\n")  # an inserted line has no old ending
        return [*[*endings[:-1], *[first] * count][: count - 1], last][:count]


class SingleFileLoader(Loader, ABC):
    filename: ClassVar[str]

    @property
    def files(self) -> Iterator[Path]:
        if (path := Path.cwd() / self.filename).exists():
            yield path

    def supports(self, filename: Path) -> bool:
        return filename.name == self.filename


@dataclass(frozen=True, slots=True, kw_only=True)
class Loaded:
    entries: list[Entry]
    # applies the changes to the file text the entries came from; a loader binds what it read while loading, such as the
    # pre-commit verdicts, since a hook's language may come from a remote manifest
    rewrite: Callable[[str, Mapping[str, str]], str]


@dataclass(frozen=True, slots=True, kw_only=True)
class Entry:
    spec: str
    pkg_type: PkgType
    requires_python: str | None = None
    # a PEP 723 script brings its own uv sources and indexes, since `uv run --script` resolves it outside the project
    uv: UvIndexes | None = None
    # an index the file sets for its own requirements, such as `--index-url` in a requirements file
    index_url: str | None = None
    # the extra indexes a requirements file sets with `--extra-index-url`
    extra_index_urls: tuple[str, ...] = ()
    # the PEP 735 group of the entry, `project` for the project's dependencies and extras; None where a format has none
    group: str | None = None


def splice(text: str, edits: Iterable[tuple[int, int, str]]) -> str:
    # apply from the end so each edit leaves the offsets of the earlier ones valid
    for start, end, encoded in sorted(edits, reverse=True):
        text = f"{text[:start]}{encoded}{text[end:]}"
    return text


__all__ = [
    "Entry",
    "Loaded",
    "Loader",
    "SingleFileLoader",
    "splice",
]

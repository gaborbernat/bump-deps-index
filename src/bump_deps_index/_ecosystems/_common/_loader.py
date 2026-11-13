from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Final

from bump_deps_index.model import Entry

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator, Mapping


_TEXT_PATTERN: Final[re.Pattern[str]] = re.compile(r"\r\n?")

_RESTORE_ENDINGS_PATTERN: Final[re.Pattern[str]] = re.compile(r"\r\n?|\n")


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
        text = _TEXT_PATTERN.sub("\n", raw)
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
        endings = [*_RESTORE_ENDINGS_PATTERN.findall(raw), ""]
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

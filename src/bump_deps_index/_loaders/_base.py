from __future__ import annotations

import re
from abc import ABC, abstractmethod
from difflib import SequenceMatcher
from typing import TYPE_CHECKING, Final, NamedTuple

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator, Mapping
    from pathlib import Path

    from bump_deps_index._spec import PkgType


# match the factor shape to skip the colons inside URL requirements
_FACTOR: Final[re.Pattern[str]] = re.compile(
    r"^(?P<prefix>[\w!{}.-]+(?:\s*,\s*[\w!{}.-]+)*\s*:\s*)(?P<requirement>\S.*)$"
)
# configparser splits a key line at its first `=` or `:`
_INI_KEY: Final[re.Pattern[str]] = re.compile(r"^(?P<key>[^=:]*)[=:]")
_INI_SECTION: Final[re.Pattern[str]] = re.compile(r"^\[(?P<header>.+)\]")


class Loader(ABC):
    @property
    @abstractmethod
    def files(self) -> Iterator[Path]:
        raise NotImplementedError

    @abstractmethod
    def supports(self, filename: Path) -> bool:
        raise NotImplementedError

    @abstractmethod
    def load(self, filename: Path, *, pre_release: bool | None) -> Iterator[Entry]:
        raise NotImplementedError

    def update_file(self, filename: Path, changes: Mapping[str, str]) -> None:
        with filename.open(encoding="utf-8", newline="") as file_handler:
            raw = file_handler.read()
        text = re.sub(r"\r\n?", "\n", raw)
        if (updated := self._update_text(text, changes)) == text:
            return
        lines, endings = updated.split("\n"), [*re.findall(r"\r\n?|\n", raw), ""]
        # give each line back its own ending; align the lines when a rewrite joins or splits some of them
        matcher = SequenceMatcher(None, text.split("\n"), lines, autojunk=False)
        new_endings = [
            ending
            for _, old_start, old_end, new_start, new_end in matcher.get_opcodes()
            for ending in _fit(endings[old_start:old_end], new_end - new_start)
        ]
        content = "".join(f"{line}{end}" for line, end in zip(lines, new_endings, strict=True))
        with filename.open("w", encoding="utf-8", newline="") as file_handler:
            file_handler.write(content)

    @abstractmethod
    def _update_text(self, text: str, changes: Mapping[str, str]) -> str:
        raise NotImplementedError

    @classmethod
    def _update_ini(cls, text: str, changes: Mapping[str, str], wanted: Callable[[str, str], bool]) -> str:
        # follow configparser: an indented line continues the open key, blank and comment lines keep it open
        result: list[str] = []
        section = key = ""
        key_indent = 0
        for line in text.split("\n"):
            stripped = line.strip()
            indent = len(line) - len(line.lstrip())
            if not stripped or stripped[0] in {"#", ";"}:
                result.append(line)
            elif key and indent > key_indent:
                result.append(cls._replace_requirement_line(line, changes) if wanted(section, key) else line)
            elif header := _INI_SECTION.match(stripped):
                section, key = header["header"], ""
                result.append(line)
            else:
                key, key_indent = re.split(r"[=:]", stripped, maxsplit=1)[0].strip(), indent
                result.append(cls._replace_key_line(line, changes) if wanted(section, key) else line)
        return "\n".join(result)

    @staticmethod
    def _replace_key_line(line: str, changes: Mapping[str, str]) -> str:
        value = _INI_KEY.sub("", line, count=1)
        return f"{line[: len(line) - len(value)]}{Loader._replace_requirement_line(value, changes)}"

    @staticmethod
    def _replace_requirement_line(line: str, changes: Mapping[str, str]) -> str:
        prefix = line[: len(line) - len(line.lstrip())]
        value_with_spacing, suffix = Loader._split_comment(line[len(prefix) :])
        value = value_with_spacing.rstrip()
        requirement = value.removesuffix("\\").rstrip()
        if requirement in changes:
            updated = changes[requirement]
        elif (factor := _FACTOR.match(requirement)) and factor["requirement"] in changes:
            updated = f"{factor['prefix']}{changes[factor['requirement']]}"
        else:
            return line
        continuation = value[len(requirement) :]
        spacing = value_with_spacing[len(value) :]
        return f"{prefix}{updated}{continuation}{spacing}{suffix}"

    @staticmethod
    def _strip_factor(value: str) -> str:
        return factor["requirement"] if (factor := _FACTOR.match(value.strip())) else value.strip()

    @staticmethod
    def _split_comment(value: str) -> tuple[str, str]:
        quote = ""
        for index, character in enumerate(value):
            if character in {"'", '"'} and (not quote or quote == character):
                quote = "" if quote == character else character
            elif character == "#" and not quote and index and value[index - 1].isspace():
                start = index - 1
                while start and value[start - 1].isspace():
                    start -= 1
                return value[:start], value[start:]
        return value, ""

    @staticmethod
    def _generate(
        generator: Iterable[str],
        pkg_type: PkgType,
        *,
        pre_release: bool = False,
    ) -> Iterator[Entry]:
        for value in generator:
            yield Entry(value, pkg_type, pre_release)


def _fit(endings: list[str], count: int) -> list[str]:
    # keep the endings in order and the last one last, so the end of the file keeps its final newline or lack of it
    first, last = (endings[0], endings[-1]) if endings else ("\n", "\n")  # an inserted line has no old ending
    return [*[*endings[:-1], *[first] * count][: count - 1], last][:count]


class Entry(NamedTuple):
    spec: str
    pkg_type: PkgType
    pre_release: bool
    requires_python: str | None = None
    # a PEP 723 script brings its own uv sources, since `uv run --script` resolves it outside the project
    sources: Mapping[str, str | None] | None = None
    # an index the file sets for its own requirements, such as `--index-url` in a requirements file
    index_url: str | None = None


__all__ = [
    "Entry",
    "Loader",
]

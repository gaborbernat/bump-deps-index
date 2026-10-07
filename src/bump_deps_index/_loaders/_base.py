from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping
    from pathlib import Path
    from typing import TypeAlias

    from bump_deps_index._spec import PkgType

    Entry: TypeAlias = tuple[str, PkgType, bool, str | None]


# match the factor shape to skip the colons inside URL requirements
_FACTOR: Final = re.compile(r"^(?P<prefix>[\w!{}.-]+(?:\s*,\s*[\w!{}.-]+)*\s*:\s*)(?P<requirement>\S.*)$")


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
        text = raw.replace("\r\n", "\n")
        if (updated := self._update_text(text, changes)) != text:
            with filename.open("w", encoding="utf-8", newline="") as file_handler:
                file_handler.write(updated.replace("\n", "\r\n" if raw.count("\r\n") * 2 >= raw.count("\n") else "\n"))

    @abstractmethod
    def _update_text(self, text: str, changes: Mapping[str, str]) -> str:
        raise NotImplementedError

    @staticmethod
    def _replace_quoted(text: str, changes: Mapping[str, str]) -> str:
        if not changes:
            return text
        values = "|".join(re.escape(value) for value in sorted(changes, key=len, reverse=True))
        pattern = re.compile(rf"(?P<quote>['\"])(?P<pad>[ \t]*)(?P<value>{values})(?P<end>[ \t]*)(?P=quote)")
        return pattern.sub(
            lambda match: f"{match['quote']}{match['pad']}{changes[match['value']]}{match['end']}{match['quote']}", text
        )

    @staticmethod
    def _replace_key_line(line: str, changes: Mapping[str, str]) -> str:
        key, separator, value = line.partition("=")
        return f"{key}{separator}{Loader._replace_requirement_line(value, changes)}"

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
    def _bracket_delta(line: str) -> int:
        # skip brackets inside strings and comments; `# see [docs` must not keep a dependency array open
        delta, quote, escaped = 0, "", False
        for character in line:
            if escaped:
                escaped = False
            elif quote:
                escaped = character == "\\" and quote == '"'
                quote = "" if character == quote else quote
            elif character in {'"', "'"}:
                quote = character
            elif character == "#":
                break
            else:
                delta += {"[": 1, "]": -1}.get(character, 0)
        return delta

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
        requires_python: str | None = None,
    ) -> Iterator[Entry]:
        for value in generator:
            yield value, pkg_type, pre_release, requires_python


__all__ = [
    "Entry",
    "Loader",
]

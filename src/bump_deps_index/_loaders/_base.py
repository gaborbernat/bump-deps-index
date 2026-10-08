from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Final, TypeAlias

from bump_deps_index._spec import PkgType

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator, Mapping
    from pathlib import Path

Entry: TypeAlias = tuple[str, PkgType, bool, str | None]
Parsed: TypeAlias = str | int | float | bool | list["Parsed"] | dict[str, "Parsed"] | None


# match the factor shape to skip the colons inside URL requirements
_FACTOR: Final = re.compile(r"^(?P<prefix>[\w!{}.-]+(?:\s*,\s*[\w!{}.-]+)*\s*:\s*)(?P<requirement>\S.*)$")
# configparser splits a key line at its first `=` or `:`
_INI_KEY: Final = re.compile(r"^(?P<key>[^=:]*)[=:]")
_INI_SECTION: Final = re.compile(r"^\[(?P<header>.+)\]")


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
            # the writers keep the line count, so each line gets back its own ending
            endings = [*re.findall(r"\r?\n", raw), ""]
            with filename.open("w", encoding="utf-8", newline="") as file_handler:
                file_handler.write(
                    "".join(f"{line}{end}" for line, end in zip(updated.split("\n"), endings, strict=True))
                )

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
    def _strings(value: Parsed) -> list[str]:
        # read a wrongly typed field as a missing one, so one malformed field does not stop the run
        return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []

    @staticmethod
    def _table(value: Parsed, *keys: str) -> dict[str, Parsed]:
        for key in keys:
            value = value.get(key) if isinstance(value, dict) else None
        return value if isinstance(value, dict) else {}

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
    "Parsed",
]

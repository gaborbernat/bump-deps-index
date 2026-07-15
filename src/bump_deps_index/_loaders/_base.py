from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping
    from pathlib import Path

    from bump_deps_index._spec import PkgType


class Loader(ABC):
    @property
    @abstractmethod
    def files(self) -> Iterator[Path]:
        raise NotImplementedError

    @abstractmethod
    def supports(self, filename: Path) -> bool:
        raise NotImplementedError

    @abstractmethod
    def load(self, filename: Path, *, pre_release: bool | None) -> Iterator[tuple[str, PkgType, bool]]:
        raise NotImplementedError

    @abstractmethod
    def update_file(self, filename: Path, changes: Mapping[str, str]) -> None:
        raise NotImplementedError

    @staticmethod
    def _replace_quoted(text: str, changes: Mapping[str, str]) -> str:
        if not changes:
            return text
        values = "|".join(re.escape(value) for value in sorted(changes, key=len, reverse=True))
        pattern = re.compile(rf"(?P<quote>['\"])(?P<value>{values})(?P=quote)")
        return pattern.sub(lambda match: f"{match['quote']}{changes[match['value']]}{match['quote']}", text)

    @staticmethod
    def _replace_requirement_line(line: str, changes: Mapping[str, str]) -> str:
        prefix = line[: len(line) - len(line.lstrip())]
        value_with_spacing, suffix = Loader._split_comment(line[len(prefix) :])
        value = value_with_spacing.rstrip()
        requirement = value.removesuffix("\\").rstrip()
        if requirement in changes:
            updated = changes[requirement]
        elif ":" in requirement and (factor_requirement := requirement.rpartition(":")[2].strip()) in changes:
            updated = f"{requirement[: requirement.rfind(':') + 1]} {changes[factor_requirement]}"
        else:
            return line
        continuation = value[len(requirement) :]
        spacing = value_with_spacing[len(value) :]
        return f"{prefix}{updated}{continuation}{spacing}{suffix}"

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
    ) -> Iterator[tuple[str, PkgType, bool]]:
        for value in generator:
            yield value, pkg_type, pre_release

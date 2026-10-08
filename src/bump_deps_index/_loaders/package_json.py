from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Final

from bump_deps_index._spec import PkgType

from ._base import Loader

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

    from ._base import Entry, Parsed

# skip `peerDependencies`, a raised lower bound there narrows what you declare compatible
_SECTIONS: Final = ("dependencies", "devDependencies", "optionalDependencies")


class PackageJson(Loader):
    _filename: ClassVar[str] = "package.json"

    @property
    def files(self) -> Iterator[Path]:
        if (path := Path.cwd() / self._filename).exists():
            yield path

    def supports(self, filename: Path) -> bool:
        return filename.name == self._filename

    @staticmethod
    def _update_text(text: str, changes: Mapping[str, str]) -> str:
        pieces: list[str] = []
        last = 0
        for start, end, path in _json_strings(text):
            match path:
                case (section, name) if section in _SECTIONS and (
                    new := changes.get(f"{name}@{json.loads(text[start - 1 : end + 1])}")
                ):
                    pieces += [text[last:start], json.dumps(new[len(name) + 1 :])[1:-1]]
                    last = end
        return "".join([*pieces, text[last:]])

    def load(self, filename: Path, *, pre_release: bool | None) -> Iterator[Entry]:
        with filename.open(encoding="utf-8") as file_handler:
            cfg: Parsed = json.load(file_handler)
        yield from self._generate(
            [
                f"{name}@{wanted}"
                for section in _SECTIONS
                for name, wanted in self._table(cfg, section).items()
                # skip aliases, paths, URLs and workspace links; the registry has no version for them
                if isinstance(wanted, str) and ":" not in wanted and "/" not in wanted
            ],
            pkg_type=PkgType.JS,
            pre_release=False if pre_release is None else pre_release,
        )


def _json_strings(text: str) -> Iterator[tuple[int, int, tuple[str, ...]]]:
    # walk the JSON the loader parsed, and yield each string value with the object keys above it
    containers: list[tuple[str, str]] = []
    expect_key = False
    at = 0
    while at < len(text):
        character = text[at]
        if character == '"':
            end = at + 1
            while text[end] != '"':
                end += 2 if text[end] == "\\" else 1
            if expect_key:
                containers[-1] = (containers[-1][0], json.loads(text[at : end + 1]))
                expect_key = False
            else:
                yield at + 1, end, tuple(key for kind, key in containers if kind == "{")
            at = end
        elif character in "{[":
            containers.append((character, ""))
            expect_key = character == "{"
        elif character in "}]":
            containers.pop()
        elif character == ",":
            expect_key = containers[-1][0] == "{"
        at += 1


__all__ = [
    "PackageJson",
]

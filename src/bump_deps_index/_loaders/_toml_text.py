from __future__ import annotations

from tomllib import loads as load_toml
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping

_SCALAR_END: Final = frozenset(",]}\n#")


def replace_strings(text: str, changes: Mapping[str, str], wanted: Callable[[tuple[str, ...]], bool]) -> str:
    pieces: list[str] = []
    last = 0
    for start, end, path in _TomlScanner(text).strings():
        value = _decode(text, start, end)
        if not wanted(path) or (new := changes.get(value.strip())) is None:
            continue
        pad, trail = value[: len(value) - len(value.lstrip())], value[len(value.rstrip()) :]
        encoded = f"{pad}{new}{trail}"
        if text[start - 1] == '"':
            encoded = encoded.replace("\\", "\\\\").replace('"', '\\"')
        pieces += [text[last:start], encoded]
        last = end
    return "".join([*pieces, text[last:]])


class _TomlScanner:
    # walks valid TOML, since the loader parsed the same text before any write
    def __init__(self, text: str) -> None:
        self._text, self._at = text, 0

    def strings(self) -> Iterator[tuple[int, int, tuple[str, ...]]]:
        table: tuple[str, ...] = ()
        while self._skip(newlines=True) < len(self._text):
            if self._text.startswith("[", self._at):
                width = 2 if self._text.startswith("[[", self._at) else 1
                self._at += width
                table = self._key()
                self._at += width
            else:
                key = self._key()
                self._at = self._text.index("=", self._at) + 1
                yield from self._value((*table, *key))

    def _value(self, path: tuple[str, ...]) -> Iterator[tuple[int, int, tuple[str, ...]]]:
        self._skip(newlines=False)
        character = self._text[self._at : self._at + 1]
        if character in {'"', "'"}:
            start, end, multi_line = self._string()
            if not multi_line:
                yield start, end, path
        elif character in {"[", "{"}:
            self._at += 1
            closing = "]" if character == "[" else "}"
            while self._skip(newlines=True) < len(self._text) and self._text[self._at] != closing:
                if character == "[":
                    yield from self._value(path)
                else:
                    key = self._key()
                    self._at = self._text.index("=", self._at) + 1
                    yield from self._value((*path, *key))
                if self._skip(newlines=True) < len(self._text) and self._text[self._at] == ",":
                    self._at += 1
            self._at += 1
        else:
            while self._at < len(self._text) and self._text[self._at] not in _SCALAR_END:
                self._at += 1

    def _key(self) -> tuple[str, ...]:
        parts: list[str] = []
        while True:
            self._skip(newlines=False)
            if self._text[self._at : self._at + 1] in {'"', "'"}:
                start, end, _ = self._string()
                parts.append(_decode(self._text, start, end))
            else:
                start = self._at
                while self._at < len(self._text) and (self._text[self._at].isalnum() or self._text[self._at] in "_-"):
                    self._at += 1
                parts.append(self._text[start : self._at])
            self._skip(newlines=False)
            if not self._text.startswith(".", self._at):
                return tuple(parts)
            self._at += 1

    def _string(self) -> tuple[int, int, bool]:
        quote = self._text[self._at]
        if multi_line := self._text.startswith(quote * 3, self._at):
            start = self._at + 3
            end = self._find(quote * 3, start, escapes=quote == '"')
            # a multi-line string may end with up to two quotes before its closing delimiter
            end += next((extra for extra in (2, 1) if self._text.startswith(quote * extra, end + 3)), 0)
            self._at = end + 3
        else:
            start = self._at + 1
            end = self._find(quote, start, escapes=quote == '"')
            self._at = end + 1
        return start, end, multi_line

    def _find(self, delimiter: str, start: int, *, escapes: bool) -> int:
        at = start
        while at < len(self._text) and not self._text.startswith(delimiter, at):
            at += 2 if escapes and self._text[at] == "\\" else 1
        return at

    def _skip(self, *, newlines: bool) -> int:
        blank = " \t\r\n" if newlines else " \t"
        while self._at < len(self._text):
            if self._text[self._at] in blank:
                self._at += 1
            elif self._text[self._at] == "#":
                self._at = self._find("\n", self._at, escapes=False)
            else:
                break
        return self._at


def _decode(text: str, start: int, end: int) -> str:
    # a basic string escapes `"` and `\`, a literal string holds its text as written
    raw = text[start:end]
    return raw if text[start - 1] == "'" else load_toml(f'v = "{raw}"')["v"]


__all__ = [
    "replace_strings",
]

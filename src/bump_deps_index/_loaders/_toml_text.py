from __future__ import annotations

import json
import re
from tomllib import loads as load_toml
from typing import TYPE_CHECKING, Final, NamedTuple

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping

_SCALAR_END: Final[frozenset[str]] = frozenset(",]}\n#")
# the key path marks an array item with `[]`, and an inline table with a string `replace` key as `{<kind>}`
_ARRAY: Final[str] = "[]"
_CONTROL: Final[re.Pattern[str]] = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def replace_strings(text: str, changes: Mapping[str, str], wanted: Callable[[tuple[str, ...]], bool]) -> str:
    pieces: list[str] = []
    last = 0
    for string in _TomlScanner(text).strings():
        value = _decode(text, string)
        if not wanted(string.path) or (new := changes.get(value.strip())) is None:
            continue
        encoded = f"{value[: len(value) - len(value.lstrip())]}{new}{value[len(value.rstrip()) :]}"
        if string.quote == '"':  # a single-line basic string needs escapes for quotes, backslashes and newlines
            encoded = json.dumps(encoded, ensure_ascii=False)[1:-1]
        elif string.quote == '"""':  # a multi-line basic string takes raw newlines and tabs, and escapes the rest
            escaped = encoded.replace("\\", "\\\\").replace('"', '\\"')
            encoded = _CONTROL.sub(lambda match: f"\\u{ord(match[0]):04x}", escaped)
        # TOML drops the newline that opens a multi-line string, so keep it as written
        lead = "\n" if len(string.quote) > 1 and text.startswith("\n", string.start) else ""
        pieces += [text[last : string.start], lead, encoded]
        last = string.end
    return "".join([*pieces, text[last:]])


class _TomlScanner:
    # walks valid TOML, since the loader parsed the same text before any write
    def __init__(self, text: str) -> None:
        self._text, self._at = text, 0

    def strings(self) -> Iterator[_String]:
        table: tuple[str, ...] = ()
        body: list[_String] = []
        while self._skip(newlines=True) < len(self._text):
            if self._text.startswith("[", self._at):
                yield from self._with_kind(table, body)
                array_table = self._text.startswith("[[", self._at)
                self._at += 2 if array_table else 1
                table, body = (*self._key(), *([_ARRAY] if array_table else [])), []
                self._at += 2 if array_table else 1
            else:
                key = self._key()
                self._at = self._text.index("=", self._at) + 1
                body.extend(self._value((*table, *key)))
        yield from self._with_kind(table, body)

    def _key(self) -> tuple[str, ...]:
        parts: list[str] = []
        while True:
            self._skip(newlines=False)
            if self._text[self._at : self._at + 1] in {'"', "'"}:
                parts.append(_decode(self._text, self._string(())))
            else:
                start = self._at
                while self._at < len(self._text) and (self._text[self._at].isalnum() or self._text[self._at] in "_-"):
                    self._at += 1
                parts.append(self._text[start : self._at])
            self._skip(newlines=False)
            if not self._text.startswith(".", self._at):
                return tuple(parts)
            self._at += 1

    def _value(self, path: tuple[str, ...]) -> Iterator[_String]:
        self._skip(newlines=False)
        character = self._text[self._at : self._at + 1]
        if character in {'"', "'"}:
            yield self._string(path)
        elif character == "[":
            self._at += 1
            while self._skip(newlines=True) < len(self._text) and self._text[self._at] != "]":
                yield from self._value((*path, _ARRAY))
                self._skip_comma()
            self._at += 1
        elif character == "{":
            yield from self._inline_table(path)
        else:
            while self._at < len(self._text) and self._text[self._at] not in _SCALAR_END:
                self._at += 1

    def _string(self, path: tuple[str, ...]) -> _String:
        character = self._text[self._at]
        quote = character * 3 if self._text.startswith(character * 3, self._at) else character
        start = at = self._at + len(quote)
        while at < len(self._text) and not self._text.startswith(quote, at):
            at += 2 if character == '"' and self._text[at] == "\\" else 1
        if len(quote) > 1:  # a multi-line string may end with up to two quotes before its closing delimiter
            at += next((extra for extra in (2, 1) if self._text.startswith(character * extra, at + 3)), 0)
        self._at = at + len(quote)
        return _String(start, at, path, quote)

    def _inline_table(self, path: tuple[str, ...]) -> Iterator[_String]:
        self._at += 1
        strings: list[_String] = []
        while self._skip(newlines=True) < len(self._text) and self._text[self._at] != "}":
            key = self._key()
            self._at = self._text.index("=", self._at) + 1
            strings.extend(self._value((*path, *key)))
            self._skip_comma()
        self._at += 1
        yield from self._with_kind(path, strings)

    def _with_kind(self, path: tuple[str, ...], strings: list[_String]) -> Iterator[_String]:
        # tox reads a substitution by its `replace` kind, so carry the kind in the path of its values
        kind = next((_decode(self._text, item) for item in strings if item.path == (*path, "replace")), None)
        for item in strings:
            yield item if kind is None else item._replace(path=(*path, f"{{{kind}}}", *item.path[len(path) :]))

    def _skip_comma(self) -> None:
        if self._skip(newlines=True) < len(self._text) and self._text[self._at] == ",":
            self._at += 1

    def _skip(self, *, newlines: bool) -> int:
        blank = " \t\r\n" if newlines else " \t"
        while self._at < len(self._text):
            if self._text[self._at] in blank:
                self._at += 1
            elif self._text[self._at] == "#":
                while self._at < len(self._text) and self._text[self._at] != "\n":
                    self._at += 1
            else:
                break
        return self._at


def _decode(text: str, string: _String) -> str:
    # a basic string escapes `"` and `\`, a literal string holds its text as written
    raw = text[string.start : string.end]
    return raw if string.quote == "'" else load_toml(f"v = {string.quote}{raw}{string.quote}")["v"]


class _String(NamedTuple):
    start: int
    end: int
    path: tuple[str, ...]
    quote: str


__all__ = [
    "replace_strings",
]

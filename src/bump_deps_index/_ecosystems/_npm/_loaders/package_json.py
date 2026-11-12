from __future__ import annotations

import json
from typing import TYPE_CHECKING, ClassVar, Final

from typing_extensions import override

from bump_deps_index.model import PkgType, table

from ...model import (  # ruff: ignore[relative-imports]  # shared contracts belong to the ecosystem owner
    Entry,
    Loaded,
    SingleFileLoader,
    splice,
)

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path
    from typing import TypeAlias

    from bump_deps_index.model import Parsed

    _JsonNode: TypeAlias = dict[str, "_JsonNode"] | tuple[int, int] | None

# skip `peerDependencies`, a raised lower bound there narrows what you declare compatible
_SECTIONS: Final[tuple[str, ...]] = ("dependencies", "devDependencies", "optionalDependencies")


class PackageJson(SingleFileLoader):
    filename: ClassVar[str] = "package.json"

    @override
    def load(self, filename: Path) -> Loaded:
        with filename.open(encoding="utf-8") as file_handler:
            cfg: Parsed = json.load(file_handler)
        return Loaded(
            entries=[
                Entry(spec=f"{name}@{spec.strip()}", pkg_type=PkgType.JS)
                for section in _SECTIONS
                for name, spec in table(cfg, section).items()
                # skip aliases, paths, URLs and workspace links, since the registry has no version for them, and an
                # empty range, which npm reads as `*`
                if isinstance(spec, str) and spec.strip() and ":" not in spec and "/" not in spec
            ],
            rewrite=self._update_text,
        )

    def _update_text(self, text: str, changes: Mapping[str, str]) -> str:
        tree, _ = self._json_node(text, 0)
        edits: list[tuple[int, int, str]] = []
        for section in _SECTIONS:
            entries = tree.get(section) if isinstance(tree, dict) else None
            for name, span in entries.items() if isinstance(entries, dict) else []:
                if not isinstance(span, tuple):
                    continue
                start, end = span
                if new := changes.get(f"{name}@{json.loads(text[start - 1 : end + 1]).strip()}"):
                    edits.append((start, end, json.dumps(new[len(name) + 1 :])[1:-1]))
        return splice(text, edits)

    @staticmethod
    def _json_node(text: str, at: int) -> tuple[_JsonNode, int]:
        at = PackageJson._skip_blank(text, at)
        if text[at] == '"':
            end = PackageJson._string_end(text, at)
            return (at + 1, end - 1), end
        if text[at] not in "{[":
            while at < len(text) and text[at] not in ",]} \t\r\n":
                at += 1
            return None, at
        closing = "}" if text[at] == "{" else "]"
        members: dict[str, _JsonNode] = {}
        at += 1
        while (at := PackageJson._skip_blank(text, at)) < len(text) and text[at] != closing:
            if closing == "}":
                key_end = PackageJson._string_end(text, at)
                # a later duplicate key wins, as it does for `json`
                members[json.loads(text[at:key_end])], at = PackageJson._json_node(text, text.index(":", key_end) + 1)
            else:
                _, at = PackageJson._json_node(text, at)
            if (at := PackageJson._skip_blank(text, at)) < len(text) and text[at] == ",":
                at += 1
        return (members if closing == "}" else None), at + 1

    @staticmethod
    def _skip_blank(text: str, at: int) -> int:
        while at < len(text) and text[at] in " \t\r\n":
            at += 1
        return at

    @staticmethod
    def _string_end(text: str, at: int) -> int:
        end = at + 1
        while text[end] != '"':
            end += 2 if text[end] == "\\" else 1
        return end + 1


__all__ = [
    "PackageJson",
]

from __future__ import annotations

from pathlib import Path
from tomllib import TOMLDecodeError
from tomllib import loads as load_toml
from typing import TYPE_CHECKING, Final

from typing_extensions import override

from bump_deps_index._config import script_uv_indexes
from bump_deps_index._parsed import strings
from bump_deps_index._spec import PkgType

from ._base import Entry, Loader
from ._toml_text import replace_strings

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

    from bump_deps_index._parsed import Parsed

_START: Final[str] = "# /// script"


class ScriptMetadata(Loader):
    @property
    @override
    def files(self) -> Iterator[Path]:
        yield from (path for path in Path.cwd().iterdir() if self.supports(path))

    @override
    def supports(self, filename: Path) -> bool:
        try:
            return filename.suffix == ".py" and _START in filename.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return False

    @override
    def load(self, filename: Path) -> Iterator[Entry]:
        metadata = _metadata(filename.read_text(encoding="utf-8"))
        uv, index_url = script_uv_indexes(metadata)
        requires_python = requires if isinstance(requires := metadata.get("requires-python"), str) else None
        for dependency in strings(metadata.get("dependencies")):
            yield Entry(dependency, PkgType.PYTHON, requires_python=requires_python, uv=uv, index_url=index_url)

    @override
    def _update_text(self, filename: Path, text: str, changes: Mapping[str, str]) -> str:
        lines = text.split("\n")
        if (span := _block(lines)) is None:
            return text
        block = lines[span[0] : span[1]]
        toml = replace_strings(
            "\n".join(line[2:] for line in block), changes, lambda path: path == ("dependencies", "[]")
        )
        lines[span[0] : span[1]] = [
            f"# {new}" if line.startswith("# ") else line for line, new in zip(block, toml.split("\n"), strict=True)
        ]
        return "\n".join(lines)


def _metadata(content: str) -> dict[str, Parsed]:
    lines = content.split("\n")
    if (span := _block(lines)) is None:
        return {}
    toml_lines: list[str] = []
    for line in lines[span[0] : span[1]]:
        if line.startswith("# "):
            toml_lines.append(line[2:])
        elif line.rstrip() == "#":
            toml_lines.append("")
        else:
            return {}
    try:
        return load_toml("\n".join(toml_lines))
    except TOMLDecodeError:
        return {}


def _block(lines: list[str]) -> tuple[int, int] | None:
    # the lines between the `# /// script` and `# ///` markers
    start = None
    for at, line in enumerate(lines):
        if line.rstrip() == _START:
            start = at + 1
        elif line.rstrip() == "# ///" and start is not None:
            return start, at
    return None


__all__ = [
    "ScriptMetadata",
]

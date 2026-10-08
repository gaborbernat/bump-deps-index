from __future__ import annotations

import io
from pathlib import Path
from tomllib import TOMLDecodeError
from tomllib import load as load_toml
from typing import TYPE_CHECKING

from bump_deps_index._spec import PkgType

from ._base import Loader
from ._toml_text import replace_strings

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

    from ._base import Entry, Parsed


class ScriptMetadata(Loader):
    @property
    def files(self) -> Iterator[Path]:
        for path in Path.cwd().iterdir():
            if path.is_file() and path.suffix == ".py":
                try:
                    if "# /// script" in path.read_text(encoding="utf-8"):
                        yield path
                except (OSError, UnicodeDecodeError):
                    continue

    def supports(self, filename: Path) -> bool:
        return filename.suffix == ".py" and self._has_script_metadata(filename)

    @staticmethod
    def _update_text(text: str, changes: Mapping[str, str]) -> str:
        lines = text.split("\n")
        start_idx = end_idx = None
        for i, line in enumerate(lines):
            if line.rstrip() == "# /// script":
                start_idx = i
            elif line.rstrip() == "# ///" and start_idx is not None:
                end_idx = i + 1
                break
        if start_idx is None or end_idx is None:
            return text
        # edit the TOML inside the comment block, then put each line back behind its `# `
        block = lines[start_idx + 1 : end_idx - 1]
        toml = replace_strings("\n".join(line[2:] for line in block), changes, lambda path: path == ("dependencies",))
        lines[start_idx + 1 : end_idx - 1] = [
            f"# {new}" if line.startswith("# ") else line for line, new in zip(block, toml.split("\n"), strict=True)
        ]
        return "\n".join(lines)

    def load(self, filename: Path, *, pre_release: bool | None) -> Iterator[Entry]:
        metadata = self._metadata(filename)
        yield from self._generate(
            self._strings(metadata.get("dependencies")),
            pkg_type=PkgType.PYTHON,
            pre_release=False if pre_release is None else pre_release,
            requires_python=requires if isinstance(requires := metadata.get("requires-python"), str) else None,
        )

    def _metadata(self, filename: Path) -> dict[str, Parsed]:
        if (toml_str := self._extract_toml_from_comments(filename.read_text(encoding="utf-8"))) is None:
            return {}
        try:
            return load_toml(io.BytesIO(toml_str.encode("utf-8")))
        except TOMLDecodeError:
            return {}

    @staticmethod
    def _extract_toml_from_comments(content: str) -> str | None:
        lines = content.split("\n")
        start_idx = end_idx = None
        for i, line in enumerate(lines):
            if line.rstrip() == "# /// script":
                start_idx = i + 1
            elif line.rstrip() == "# ///" and start_idx is not None:
                end_idx = i
                break
        if start_idx is None or end_idx is None:
            return None
        toml_lines: list[str] = []
        for line in lines[start_idx:end_idx]:
            if line.startswith("# "):
                toml_lines.append(line[2:])
            elif line.rstrip() == "#":
                toml_lines.append("")
            else:
                return None
        return "\n".join(toml_lines)

    @staticmethod
    def _has_script_metadata(file_path: Path) -> bool:
        try:
            return "# /// script" in file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return False


__all__ = [
    "ScriptMetadata",
]

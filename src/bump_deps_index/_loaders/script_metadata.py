from __future__ import annotations

import io
from functools import cached_property
from pathlib import Path
from tomllib import TOMLDecodeError
from tomllib import load as load_toml
from typing import TYPE_CHECKING

from bump_deps_index._spec import PkgType

from ._base import Loader

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping


class ScriptMetadata(Loader):
    """Loader for PEP-723 inline script metadata."""

    @cached_property
    def files(self) -> Iterator[Path]:
        """Find .py files with script metadata blocks."""
        for path in Path.cwd().iterdir():
            if path.is_file() and path.suffix == ".py":
                try:
                    if "# /// script" in path.read_text(encoding="utf-8"):
                        yield path
                except (OSError, UnicodeDecodeError):
                    continue

    def supports(self, filename: Path) -> bool:
        """Check if file is a Python script with metadata."""
        return filename.suffix == ".py" and self._has_script_metadata(filename)

    def update_file(self, filename: Path, changes: Mapping[str, str]) -> None:  # noqa: PLR6301
        """Update only the script metadata block, not the rest of the file."""
        content = filename.read_text(encoding="utf-8")
        lines = content.split("\n")
        start_idx = end_idx = None
        for i, line in enumerate(lines):
            if line.rstrip() == "# /// script":
                start_idx = i
            elif line.rstrip() == "# ///" and start_idx is not None:
                end_idx = i + 1
                break
        if start_idx is None or end_idx is None:
            return
        block = "\n".join(lines[start_idx:end_idx])
        for src, dst in changes.items():
            block = block.replace(src, dst)
        lines[start_idx:end_idx] = block.split("\n")
        filename.write_text("\n".join(lines), encoding="utf-8")

    def load(self, filename: Path, *, pre_release: bool | None) -> Iterator[tuple[str, PkgType, bool]]:  # noqa: ARG002
        """Extract dependencies from script metadata block."""
        if (toml_str := self._extract_toml_from_comments(filename.read_text(encoding="utf-8"))) is None:
            return
        try:
            yield from self._generate(
                load_toml(io.BytesIO(toml_str.encode("utf-8"))).get("dependencies", []), pkg_type=PkgType.PYTHON
            )
        except TOMLDecodeError:
            return

    @staticmethod
    def _extract_toml_from_comments(content: str) -> str | None:
        """Extract TOML content from # /// script block."""
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
        """Quick check if file contains script metadata marker."""
        try:
            return "# /// script" in file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return False


__all__ = [
    "ScriptMetadata",
]

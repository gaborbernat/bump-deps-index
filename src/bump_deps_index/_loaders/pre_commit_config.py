from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, NotRequired, TypedDict, cast

from yaml import safe_load as load_yaml

from bump_deps_index._spec import PkgType, package_type

from ._base import Loader

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping


class Hook(TypedDict):
    id: str
    args: NotRequired[list[str]]
    additional_dependencies: NotRequired[list[str]]


class RepoConfig(TypedDict):
    repo: str
    rev: NotRequired[str]
    hooks: list[Hook]


class PreCommitConfig(Loader):
    _filename: ClassVar[str] = ".pre-commit-config.yaml"

    @property
    def files(self) -> Iterator[Path]:
        if (path := Path.cwd() / self._filename).exists():
            yield path

    def supports(self, filename: Path) -> bool:
        return filename.name == self._filename

    def update_file(self, filename: Path, changes: Mapping[str, str]) -> None:
        lines = filename.read_text(encoding="utf-8").split("\n")
        result: list[str] = []
        dependency_indent: int | None = None
        for line in lines:
            stripped = line.strip()
            indent = len(line) - len(line.lstrip())
            if stripped.startswith("additional_dependencies:"):
                dependency_indent = indent
                result.append(self._replace_flow_values(self._replace_quoted(line, changes), changes))
                continue
            if (
                dependency_indent is not None
                and stripped
                and indent <= dependency_indent
                and not stripped.startswith("-")
            ):
                dependency_indent = None
            if dependency_indent is not None and stripped.startswith("-"):
                updated_line = self._replace_list_item(line, changes)
            else:
                updated_line = line
            result.append(updated_line)
        filename.write_text("\n".join(result), encoding="utf-8")

    @classmethod
    def _replace_list_item(cls, line: str, changes: Mapping[str, str]) -> str:
        prefix, _, value = line.partition("-")
        spacing = value[: len(value) - len(value.lstrip())]
        value_with_spacing, suffix = cls._split_comment(value[len(spacing) :])
        quoted = value_with_spacing.rstrip()
        quote = quoted[:1] if quoted[:1] in {"'", '"'} and quoted.endswith(quoted[:1]) else ""
        raw = quoted[1:-1] if quote else quoted
        trailing = value_with_spacing[len(quoted) :]
        return f"{prefix}-{spacing}{quote}{changes.get(raw, raw)}{quote}{trailing}{suffix}"

    @staticmethod
    def _replace_flow_values(line: str, changes: Mapping[str, str]) -> str:
        if not changes:
            return line
        values = "|".join(re.escape(value) for value in sorted(changes, key=len, reverse=True))
        pattern = re.compile(rf"(?P<prefix>\[\s*|,\s*)(?P<value>{values})(?=\s*(?:,|]))")
        return pattern.sub(lambda match: f"{match['prefix']}{changes[match['value']]}", line)

    def load(self, filename: Path, *, pre_release: bool | None) -> Iterator[tuple[str, PkgType, bool]]:
        with filename.open("rt", encoding="utf-8") as file_handler:
            cfg = load_yaml(file_handler)
        pre = True if pre_release is None else pre_release
        repos = cast("list[RepoConfig]", cfg.get("repos", []) if isinstance(cfg, dict) else [])
        for repo in repos:
            for hook in repo["hooks"]:
                for pkg in hook.get("additional_dependencies", []):
                    yield from self._generate([pkg], pkg_type=package_type(pkg), pre_release=pre)


__all__ = [
    "PreCommitConfig",
]

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, ClassVar, Final, TypeAlias

from typing_extensions import override
from yaml import MappingNode, Node, SafeLoader, ScalarNode, SequenceNode
from yaml import compose as compose_yaml
from yaml import safe_load as load_yaml

from bump_deps_index._lookup import PkgType, package_type
from bump_deps_index._parsed import mappings, strings

from ._base import Entry, Loaded, SingleFileLoader, splice

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from bump_deps_index._parsed import Parsed

_MERGE: Final[str] = "tag:yaml.org,2002:merge"
HookLanguages: TypeAlias = Callable[[str, str | None], Mapping[str, str]]


class PreCommitConfig(SingleFileLoader):
    filename: ClassVar[str] = ".pre-commit-config.yaml"
    default_pre_release: ClassVar[bool] = True

    def __init__(self, hook_languages: HookLanguages) -> None:
        self._hook_languages = hook_languages

    @override
    def load(self, filename: Path) -> Loaded:
        with filename.open("rt", encoding="utf-8") as file_handler:
            cfg: Parsed = load_yaml(file_handler)
        language_types: Final[dict[str, PkgType]] = {
            "python": PkgType.PYTHON,
            "python_venv": PkgType.PYTHON,
            "node": PkgType.JS,
        }
        entries: list[Entry] = []
        kept: list[bool] = []
        for repo in mappings(cfg.get("repos") if isinstance(cfg, dict) else None):
            hooks = mappings(repo.get("hooks"))
            languages = (
                self._hook_languages(str(repo.get("repo")), rev if isinstance(rev := repo.get("rev"), str) else None)
                if any("language" not in hook and hook.get("additional_dependencies") for hook in hooks)
                else {}
            )
            for hook in hooks:
                language = (
                    value if isinstance(value := hook.get("language"), str) else languages.get(str(hook.get("id")))
                )
                # skip golang, rust and other hooks; their dependencies are not on PyPI or npm
                skip = language is not None and language not in language_types
                if "additional_dependencies" in hook:
                    kept.append(not skip)
                if skip:
                    continue
                entries.extend(
                    Entry(spec=pkg, pkg_type=package_type(pkg) if language is None else language_types[language])
                    for pkg in strings(hook.get("additional_dependencies"))
                )
        return Loaded(entries=entries, kept=tuple(kept))

    @override
    def _update_text(self, text: str, changes: Mapping[str, str], kept: tuple[bool, ...]) -> str:
        # keyed by start: an alias yields its anchored node again, which must be edited once
        edits: dict[int, tuple[int, str]] = {}
        verdicts = iter(kept)
        for hook in self._hooks(self._value(compose_yaml(text, Loader=SafeLoader), "repos")):
            if (dependencies := self._value(hook, "additional_dependencies")) is None:
                continue
            if not next(verdicts) or not isinstance(dependencies, SequenceNode):
                continue
            for item in dependencies.value:
                if (
                    isinstance(item, ScalarNode)
                    and (new := changes.get(item.value)) is not None
                    and (encoded := self._encode(new, item.style, flow=dependencies.flow_style is True)) is not None
                ):
                    edits[self._scalar_start(text, item.start_mark.index)] = (item.end_mark.index, encoded)
        return splice(text, ((start, end, encoded) for start, (end, encoded) in edits.items()))

    @staticmethod
    def _hooks(repos: Node | None) -> Iterator[MappingNode]:
        for repo in repos.value if isinstance(repos, SequenceNode) else []:
            if isinstance(hooks := PreCommitConfig._value(repo, "hooks"), SequenceNode):
                yield from (hook for hook in hooks.value if isinstance(hook, MappingNode))

    @staticmethod
    def _value(node: Node | None, key: str) -> Node | None:
        # a later duplicate key wins, and an own key beats one a `<<` merge brings, as they do for the loader's dict
        pairs = node.value if isinstance(node, MappingNode) else []
        if found := next((value for name, value in reversed(pairs) if PreCommitConfig._is_key(name, key)), None):
            return found
        # the last `<<` key wins, and within one `<<` list the first map wins
        merged = (value for name, value in reversed(pairs) if name.tag == _MERGE)
        bases = (base for value in merged for base in (value.value if isinstance(value, SequenceNode) else [value]))
        return next(
            (found for base in bases if (found := PreCommitConfig._value(base, key)) is not None),
            None,
        )

    @staticmethod
    def _is_key(node: Node, key: str) -> bool:
        return isinstance(node, ScalarNode) and node.tag != _MERGE and node.value == key

    @staticmethod
    def _encode(value: str, style: str | None, *, flow: bool) -> str | None:
        if style == "'":
            quoted = value.replace("'", "''")
            return f"'{quoted}'"
        # a JSON string is a valid YAML double-quoted scalar; quote a plain one where a `,` would end it, as in `[a, b]`
        if style == '"' or (style is None and flow and any(character in value for character in ",[]{}")):
            return json.dumps(value)
        return value if style is None else None  # leave block scalars as written

    @staticmethod
    def _scalar_start(text: str, at: int) -> int:
        # a node starts at its `&anchor` or `!tag`; keep those, and any comment after them, and replace the value
        while text[at] in {"&", "!", "#"} or text[at].isspace():
            if text[at] == "#":
                at = text.index("\n", at)
            else:
                at += 1 if text[at].isspace() else len(text[at:].split(maxsplit=1)[0])
        return at


__all__ = [
    "HookLanguages",
    "PreCommitConfig",
]

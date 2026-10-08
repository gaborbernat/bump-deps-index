from __future__ import annotations

import json
import ssl
from typing import TYPE_CHECKING, ClassVar, Final
from urllib.parse import quote, urlsplit

from httpx import Client, HTTPError
from truststore import SSLContext
from typing_extensions import override
from yaml import MappingNode, Node, SafeLoader, ScalarNode, SequenceNode, YAMLError
from yaml import compose as compose_yaml
from yaml import safe_load as load_yaml

from bump_deps_index._parsed import mappings, strings
from bump_deps_index._spec import PkgType, package_type

from ._base import Entry, SingleFileLoader

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping
    from pathlib import Path

    from bump_deps_index._parsed import Parsed

_MERGE: Final[str] = "tag:yaml.org,2002:merge"
_LANGUAGE_TYPES: Final[dict[str, PkgType]] = {
    "python": PkgType.PYTHON,
    "python_venv": PkgType.PYTHON,
    "node": PkgType.JS,
}


class PreCommitConfig(SingleFileLoader):
    filename: ClassVar[str] = ".pre-commit-config.yaml"
    default_pre_release: ClassVar[bool] = True

    def __init__(self) -> None:
        # the writer reuses the loader's verdict per hook, since the language may come from a remote manifest
        self._kept_by_file: dict[Path, list[bool]] = {}

    @override
    def load(self, filename: Path) -> Iterator[Entry]:
        with filename.open("rt", encoding="utf-8") as file_handler:
            cfg: Parsed = load_yaml(file_handler)
        kept = self._kept_by_file[filename] = []
        for repo in mappings(cfg.get("repos") if isinstance(cfg, dict) else None):
            hooks = mappings(repo.get("hooks"))
            languages = (
                _hook_languages(str(repo.get("repo")), rev if isinstance(rev := repo.get("rev"), str) else None)
                if any("language" not in hook and hook.get("additional_dependencies") for hook in hooks)
                else {}
            )
            for hook in hooks:
                language = (
                    value if isinstance(value := hook.get("language"), str) else languages.get(str(hook.get("id")))
                )
                # skip golang, rust and other hooks; their dependencies are not on PyPI or npm
                skip = language is not None and language not in _LANGUAGE_TYPES
                if "additional_dependencies" in hook:
                    kept.append(not skip)
                if skip:
                    continue
                for pkg in strings(hook.get("additional_dependencies")):
                    yield Entry(pkg, package_type(pkg) if language is None else _LANGUAGE_TYPES[language])

    @override
    def _update_text(self, filename: Path, text: str, changes: Mapping[str, str]) -> str:
        edits: dict[int, tuple[int, str]] = {}
        kept = iter(self._kept_by_file[filename])
        for hook in _hooks(_value(compose_yaml(text, Loader=SafeLoader), "repos")):
            if (dependencies := _value(hook, "additional_dependencies")) is None:
                continue
            if not next(kept) or not isinstance(dependencies, SequenceNode):
                continue
            for item in dependencies.value:
                if (
                    isinstance(item, ScalarNode)
                    and (new := changes.get(item.value)) is not None
                    and (encoded := _encode(new, item.style, flow=dependencies.flow_style is True)) is not None
                ):
                    edits[_scalar_start(text, item.start_mark.index)] = (item.end_mark.index, encoded)
        for start, (end, encoded) in sorted(edits.items(), reverse=True):
            text = f"{text[:start]}{encoded}{text[end:]}"
        return text


def _hooks(repos: Node | None) -> Iterator[MappingNode]:
    for repo in repos.value if isinstance(repos, SequenceNode) else []:
        if isinstance(hooks := _value(repo, "hooks"), SequenceNode):
            yield from (hook for hook in hooks.value if isinstance(hook, MappingNode))


def _value(node: Node | None, key: str) -> Node | None:
    # a later duplicate key wins, and an own key beats one a `<<` merge brings, as they do for the loader's dict
    pairs = node.value if isinstance(node, MappingNode) else []
    if found := next((value for name, value in reversed(pairs) if _is_key(name, key)), None):
        return found
    # the last `<<` key wins, and within one `<<` list the first map wins
    merged = (value for name, value in reversed(pairs) if name.tag == _MERGE)
    bases = (base for value in merged for base in (value.value if isinstance(value, SequenceNode) else [value]))
    return next((found for base in bases if (found := _value(base, key)) is not None), None)


def _is_key(node: Node, key: str) -> bool:
    return isinstance(node, ScalarNode) and node.tag != _MERGE and node.value == key


def _encode(value: str, style: str | None, *, flow: bool) -> str | None:
    if style == "'":
        return "'{}'".format(value.replace("'", "''"))
    # a JSON string is a valid YAML double-quoted scalar; quote a plain one where a `,` would end it, as in `[a, b]`
    if style == '"' or (style is None and flow and any(character in value for character in ",[]{}")):
        return json.dumps(value)
    return value if style is None else None  # leave block scalars as written


def _scalar_start(text: str, at: int) -> int:
    # a node starts at its `&anchor` or `!tag`; keep those, and any comment after them, and replace the value
    while text[at] in {"&", "!", "#"} or text[at].isspace():
        if text[at] == "#":
            at = text.index("\n", at)
        else:
            at += 1 if text[at].isspace() else len(text[at:].split(maxsplit=1)[0])
    return at


def _hook_languages(repo: str, rev: str | None) -> dict[str, str]:
    if rev is None or (url := _manifest_url(repo, rev)) is None:
        return {}
    try:
        with Client(verify=SSLContext(ssl.PROTOCOL_TLS_CLIENT), timeout=10) as client:
            manifest = load_yaml(client.get(url, follow_redirects=True).raise_for_status().text)
    except (HTTPError, YAMLError):  # guess from the dependency shape when the manifest is out of reach
        return {}
    return {
        hook["id"]: hook["language"]
        for hook in (manifest if isinstance(manifest, list) else [])
        if isinstance(hook, dict) and isinstance(hook.get("id"), str) and isinstance(hook.get("language"), str)
    }


def _manifest_url(repo: str, rev: str) -> str | None:
    parsed = urlsplit(repo)
    path = parsed.path.strip("/").removesuffix(".git")
    if parsed.netloc == "github.com":
        return f"https://raw.githubusercontent.com/{path}/{quote(rev)}/.pre-commit-hooks.yaml"
    if parsed.netloc == "gitlab.com":
        return f"https://gitlab.com/{path}/-/raw/{quote(rev)}/.pre-commit-hooks.yaml"
    return None


__all__ = [
    "PreCommitConfig",
]

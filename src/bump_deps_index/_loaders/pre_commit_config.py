from __future__ import annotations

import re
import ssl
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Final
from urllib.parse import quote, urlsplit

from httpx import Client, HTTPError
from truststore import SSLContext
from yaml import YAMLError
from yaml import safe_load as load_yaml

from bump_deps_index._spec import PkgType, package_type

from ._base import Loader

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

    from ._base import Entry, Parsed

_LANGUAGE_TYPES: Final = {"python": PkgType.PYTHON, "python_venv": PkgType.PYTHON, "node": PkgType.JS}


class PreCommitConfig(Loader):
    _filename: ClassVar[str] = ".pre-commit-config.yaml"

    def __init__(self) -> None:
        # the writer matches text, so it needs to know which hooks the loader skipped to leave their lists alone
        self._kept_by_file: dict[Path, list[bool]] = {}
        self._kept: list[bool] = []

    def update_file(self, filename: Path, changes: Mapping[str, str]) -> None:
        self._kept = self._kept_by_file.get(filename, [])
        super().update_file(filename, changes)

    @property
    def files(self) -> Iterator[Path]:
        if (path := Path.cwd() / self._filename).exists():
            yield path

    def supports(self, filename: Path) -> bool:
        return filename.name == self._filename

    def _update_text(self, text: str, changes: Mapping[str, str]) -> str:
        result: list[str] = []
        dependency_indent: int | None = None
        flow_depth = 0
        kept_hooks, keep = iter(self._kept), True
        for line in text.split("\n"):
            stripped = line.strip()
            indent = len(line) - len(line.lstrip())
            head, key, value = line.partition("additional_dependencies:")
            # a key follows the `-` that opens a hook, or the `{` or `,` of an inline hook mapping
            if not flow_depth and key and (not head.strip(" -") or head.rstrip().endswith(("{", ","))):
                keep = next(kept_hooks, True)
                dependency_indent = None if head.strip(" -") or not keep else len(head)
                updated, flow_depth = self._replace_flow(value, changes, keep=keep, depth=0)
                result.append(f"{head}{key}{updated}")
                continue
            # a flow list continues from the line above, or opens on the line after its key
            if flow_depth or (dependency_indent is not None and indent > dependency_indent and stripped[:1] == "["):
                updated, flow_depth = self._replace_flow(line, changes, keep=keep, depth=flow_depth)
                dependency_indent = None
                result.append(updated)
                continue
            if (
                dependency_indent is not None
                and stripped
                and (indent < dependency_indent or (indent == dependency_indent and not stripped.startswith("-")))
            ):
                dependency_indent = None
            if dependency_indent is not None and stripped.startswith("-"):
                updated_line = self._replace_list_item(line, changes)
            else:
                updated_line = line
            result.append(updated_line)
        return "\n".join(result)

    @classmethod
    def _replace_flow(cls, part: str, changes: Mapping[str, str], *, keep: bool, depth: int) -> tuple[str, int]:
        code, comment = cls._split_comment(part)
        end, depth = _flow_list(code, depth)
        flow = cls._replace_flow_values(cls._replace_quoted(code[:end], changes), changes) if keep else code[:end]
        return f"{flow}{code[end:]}{comment}", depth

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
        pattern = re.compile(rf"(?P<prefix>^\s*|\[\s*|,\s*)(?P<value>{values})(?=\s*(?:,|]|#|$))")
        return pattern.sub(lambda match: f"{match['prefix']}{changes[match['value']]}", line)

    def load(self, filename: Path, *, pre_release: bool | None) -> Iterator[Entry]:
        with filename.open("rt", encoding="utf-8") as file_handler:
            cfg: Parsed = load_yaml(file_handler)
        pre = True if pre_release is None else pre_release
        kept = self._kept_by_file[filename] = []
        # read a malformed entry as a missing one, so one bad hook does not stop the run
        for repo in _mappings(cfg.get("repos") if isinstance(cfg, dict) else None):
            hooks = _mappings(repo.get("hooks"))
            # a remote hook takes its language from the manifest of its repository
            languages = (
                _hook_languages(str(repo.get("repo")), rev if isinstance(rev := repo.get("rev"), str) else None)
                if any("language" not in hook and hook.get("additional_dependencies") for hook in hooks)
                else {}
            )
            for hook in hooks:
                language = hook.get("language") or languages.get(str(hook.get("id")))
                # skip golang, rust and other hooks; their dependencies are not on PyPI or npm
                skip = language is not None and language not in _LANGUAGE_TYPES
                if "additional_dependencies" in hook:
                    kept.append(not skip)
                if skip:
                    continue
                dependencies = hook.get("additional_dependencies")
                for pkg in dependencies if isinstance(dependencies, list) else []:
                    if isinstance(pkg, str):
                        pkg_type = package_type(pkg) if language is None else _LANGUAGE_TYPES[str(language)]
                        yield from self._generate([pkg], pkg_type=pkg_type, pre_release=pre)


def _mappings(value: Parsed) -> list[dict[str, Parsed]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _flow_list(value: str, depth: int) -> tuple[int, int]:
    # end at the `]` that closes the list, to leave the keys after it in an inline hook mapping alone
    for at, character in enumerate(value):
        depth += {"[": 1, "]": -1}.get(character, 0)
        if character == "]" and depth == 0:
            return at + 1, 0
    return len(value), depth


def _hook_languages(repo: str, rev: str | None) -> dict[str, str]:
    if rev is None or (url := _manifest_url(repo, rev)) is None:
        return {}
    try:
        with Client(verify=SSLContext(ssl.PROTOCOL_TLS_CLIENT), timeout=10) as client:
            response = client.get(url, follow_redirects=True)
        manifest = load_yaml(response.raise_for_status().text)
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

from __future__ import annotations

import sys
from collections import deque
from dataclasses import dataclass
from enum import Enum, auto
from functools import cache
from html.parser import HTMLParser
from threading import Lock
from typing import TYPE_CHECKING, Final

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.version import Version

if TYPE_CHECKING:
    from httpx import Client


class PkgType(Enum):
    PYTHON = auto()
    JS = auto()


@dataclass(frozen=True)
class UpdateConfig:
    index_url: str
    npm_registry: str
    pre_release: bool
    python_version: Version | None


def update(client: Client, spec: str, pkg_type: PkgType, config: UpdateConfig) -> str:
    if pkg_type is PkgType.PYTHON:
        with _PY_LOCK:
            print_index("Python", config.index_url)
        return update_python(client, spec, config)
    with _JS_LOCK:
        print_index("JavaScript", config.npm_registry)
    return update_js(client, config.npm_registry, spec, pre_release=config.pre_release)


_PY_LOCK: Final[Lock] = Lock()
_JS_LOCK: Final[Lock] = Lock()


@cache
def print_index(of_type: str, registry: str) -> None:
    sys.stdout.write(f"Using {of_type} index: {registry}\n")


def update_js(client: Client, npm_registry: str, spec: str, *, pre_release: bool) -> str:
    ver_at = spec.rfind("@")
    package = spec[: len(spec) if ver_at in {-1, 0} else ver_at]
    version = get_js_pkgs(client, npm_registry, package, pre_release=pre_release)[0]
    ver = str(version)
    while ver.endswith(".0"):
        ver = ver[:-2]
    return f"{package}@{ver}"


def get_js_pkgs(client: Client, npm_registry: str, package: str, *, pre_release: bool) -> list[str]:
    info = client.get(f"{npm_registry}/{package}", follow_redirects=True).json()
    found: list[Version] = []
    for version_str in info["versions"]:
        try:
            version = Version(version_str)
        except ValueError:
            continue
        if pre_release or not version.is_prerelease:
            found.append(version)
    return [str(i) for i in sorted(found, reverse=True)]


def update_python(client: Client, spec: str, config: UpdateConfig) -> str:
    req = Requirement(spec)
    eq = any(s for s in req.specifier if s.operator == "==")
    for version in get_pkgs(
        client,
        config.index_url,
        req.name,
        pre_release=config.pre_release,
        python_version=config.python_version,
    ):
        if eq or all(s.contains(str(version)) for s in req.specifier):
            break
    else:
        return spec
    ver = str(version)
    ver = ver.partition("+")[0]  # strip build numbers
    while ver.endswith(".0"):
        ver = ver[:-2]
    c_ver = next(
        (s.version for s in req.specifier if (s.operator == ">=" and not eq) or (eq and s.operator == "==")),
        None,
    )
    if c_ver is None:
        new_ver = req.name
        if req.extras:
            new_ver = f"{new_ver}[{', '.join(req.extras)}]"
        new_ver = f"{new_ver}{',' if req.specifier else ''}>={ver}"
        if req.marker:
            new_ver = f"{new_ver};{req.marker}"
        new_req = str(Requirement(new_ver))
    else:
        op = "==" if eq else ">="
        new_req = str(req).replace(f"{op}{c_ver}", f"{op}{ver}")
    if "'" in spec:
        new_req = new_req.replace('"', "'")
    return new_req


class IndexParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._at_tag: deque[str] = deque()
        self._files: list[tuple[str, str | None]] = []
        self._attrs: list[tuple[str, str | None]] = []

    @property
    def files(self) -> frozenset[tuple[str, str | None]]:
        return frozenset(self._files)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._at_tag.append(tag)
        self._attrs = attrs

    def handle_endtag(self, tag: str) -> None:
        if self._at_tag and self._at_tag[-1] == tag:  # pragma: no branch
            self._at_tag.pop()
        self._attrs = []

    def handle_data(self, data: str) -> None:
        if (
            self._at_tag
            and self._at_tag[-1] == "a"
            and data.strip()
            and not any(k == "data-yanked" for k, _ in self._attrs)
        ):
            requires_python = next((value for key, value in self._attrs if key == "data-requires-python"), None)
            self._files.append((data.strip(), requires_python))


def get_pkgs(
    client: Client,
    index_url: str,
    package: str,
    *,
    pre_release: bool,
    python_version: Version | None = None,
) -> list[Version]:
    text = client.get(f"{index_url}/{package}/", follow_redirects=True).text
    versions: set[Version] = set()
    parser = IndexParser()
    parser.feed(text)
    for raw_file, requires_python in parser.files:
        if (
            python_version is not None
            and requires_python is not None
            and not SpecifierSet(requires_python).contains(python_version)
        ):
            continue
        file = raw_file
        file = file.removesuffix(".tar.bz2")
        file = file.removesuffix(".tar.gz")
        file = file.removesuffix(".whl")
        file = file.removesuffix(".zip")
        parts = file.split("-")
        for part in parts[1:]:
            if part.split(".")[0].isnumeric():
                break
        else:
            continue
        try:
            version = Version(part)
        except ValueError:
            pass
        else:
            versions.add(version)
    return sorted((v for v in versions if (True if pre_release else not v.is_prerelease)), reverse=True)


__all__ = [
    "PkgType",
    "UpdateConfig",
    "update",
]

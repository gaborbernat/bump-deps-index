from __future__ import annotations

import re
import sys
from collections import deque
from dataclasses import dataclass
from enum import Enum, auto
from functools import cache
from html.parser import HTMLParser
from threading import Lock
from typing import TYPE_CHECKING, Final
from urllib.parse import quote, urlsplit, urlunsplit

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import (
    InvalidSdistFilename,
    InvalidWheelFilename,
    canonicalize_name,
    parse_sdist_filename,
    parse_wheel_filename,
)
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
    sys.stdout.write(f"Using {of_type} index: {redact_url(registry)}\n")


def redact_url(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc.rpartition("@")[2], parsed.path, parsed.query, parsed.fragment))


def package_type(spec: str) -> PkgType:
    try:
        requirement = Requirement(spec)
    except ValueError:
        return PkgType.JS
    return PkgType.PYTHON if requirement.url is None or urlsplit(requirement.url).scheme else PkgType.JS


def update_js(client: Client, npm_registry: str, spec: str, *, pre_release: bool) -> str:
    ver_at = spec.rfind("@")
    package = spec[: len(spec) if ver_at in {-1, 0} else ver_at]
    version = get_js_pkgs(client, npm_registry, package, pre_release=pre_release)[0]
    return f"{package}@{version}"


_SEMVER: Final = re.compile(
    r"^v?(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<pre>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)


def _semver_key(version: str) -> tuple[int, int, int, int, tuple[tuple[int, int | str], ...]] | None:
    if (match := _SEMVER.fullmatch(version)) is None:
        return None
    pre = match["pre"]
    identifiers = tuple((0, int(value)) if value.isdecimal() else (1, value) for value in pre.split(".")) if pre else ()
    return int(match["major"]), int(match["minor"]), int(match["patch"]), int(pre is None), identifiers


def get_js_pkgs(client: Client, npm_registry: str, package: str, *, pre_release: bool) -> list[str]:
    response = client.get(f"{npm_registry.rstrip('/')}/{quote(package, safe='@')}", follow_redirects=True)
    response.raise_for_status()
    info = response.json()
    found = [
        (key, version)
        for version in info["versions"]
        if (key := _semver_key(version)) is not None and (pre_release or key[3] == 1)
    ]
    return [version for _, version in sorted(found, reverse=True)]


def update_python(client: Client, spec: str, config: UpdateConfig) -> str:
    requirement = Requirement(spec)
    if requirement.url is not None:
        return spec
    exact_operator = next(
        (specifier.operator for specifier in requirement.specifier if specifier.operator in {"==", "==="}), None
    )
    for version in get_pkgs(
        client,
        config.index_url,
        requirement.name,
        pre_release=config.pre_release,
        python_version=config.python_version,
    ):
        if exact_operator is not None or requirement.specifier.contains(version, prereleases=config.pre_release):
            break
    else:
        return spec
    candidate_version = str(version).partition("+")[0]
    while candidate_version.endswith(".0"):
        candidate_version = candidate_version[:-2]
    current_version = next(
        (
            specifier.version
            for specifier in requirement.specifier
            if (specifier.operator == ">=" and exact_operator is None) or specifier.operator == exact_operator
        ),
        None,
    )
    if current_version is None:
        new_spec = requirement.name
        if requirement.extras:
            new_spec = f"{new_spec}[{', '.join(sorted(requirement.extras))}]"
        new_spec = f"{new_spec}{requirement.specifier}{',' if requirement.specifier else ''}>={candidate_version}"
        if requirement.marker:
            new_spec = f"{new_spec};{requirement.marker}"
        new_requirement = str(Requirement(new_spec))
    else:
        operator = exact_operator or ">="
        new_requirement = str(requirement).replace(f"{operator}{current_version}", f"{operator}{candidate_version}")
    if "'" in spec:
        new_requirement = new_requirement.replace('"', "'")
    return new_requirement


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
        if self._at_tag and self._at_tag[-1] == tag:
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
    response = client.get(f"{index_url.rstrip('/')}/{canonicalize_name(package)}/", follow_redirects=True)
    response.raise_for_status()
    versions: set[Version] = set()
    parser = IndexParser()
    parser.feed(response.text)
    for raw_file, requires_python in parser.files:
        if (
            python_version is not None
            and requires_python is not None
            and not SpecifierSet(requires_python).contains(python_version)
        ):
            continue
        try:
            version = _version_from_file(raw_file)
        except (InvalidSdistFilename, InvalidWheelFilename, IndexError, ValueError):
            continue
        else:
            versions.add(version)
    return sorted((v for v in versions if (True if pre_release else not v.is_prerelease)), reverse=True)


def _version_from_file(filename: str) -> Version:
    if filename.endswith(".whl"):
        return parse_wheel_filename(filename)[1]
    if filename.endswith((".tar.gz", ".zip")):
        return parse_sdist_filename(filename)[1]
    file = filename.removesuffix(".tar.bz2").removesuffix(".whl")
    return Version(file.rsplit("-", 1)[1])


__all__ = [
    "PkgType",
    "UpdateConfig",
    "package_type",
    "redact_url",
    "update",
]

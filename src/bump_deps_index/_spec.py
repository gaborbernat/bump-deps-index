from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from functools import cache
from html.parser import HTMLParser
from threading import Lock
from typing import TYPE_CHECKING, Final
from urllib.parse import quote, urlsplit, urlunsplit
from weakref import WeakKeyDictionary

from packaging.requirements import Requirement
from packaging.specifiers import InvalidSpecifier, Specifier, SpecifierSet
from packaging.utils import (
    InvalidSdistFilename,
    InvalidWheelFilename,
    canonicalize_name,
    parse_sdist_filename,
    parse_wheel_filename,
)
from packaging.version import InvalidVersion, Version

if TYPE_CHECKING:
    from httpx import Client

_URL_CREDENTIALS: Final = re.compile(r"(?<=://)[^/\s@'\"]+@")
_SIMPLE_JSON: Final = "application/vnd.pypi.simple.v1+json"
_SIMPLE_ACCEPT: Final = f"{_SIMPLE_JSON}, application/vnd.pypi.simple.v1+html;q=0.2, text/html;q=0.01"
_NPM_ACCEPT: Final = "application/vnd.npm.install-v1+json; q=1.0, application/json; q=0.8"
_SEMVER: Final = re.compile(
    r"^v?(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<pre>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
_INDEX_CACHE: Final[WeakKeyDictionary[Client, dict[str, _IndexEntry]]] = WeakKeyDictionary()
_INDEX_CACHE_LOCK: Final[Lock] = Lock()


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
        return _update_python(client, spec, config)
    return _update_js(client, config.npm_registry, spec, pre_release=config.pre_release)


def _update_python(client: Client, spec: str, config: UpdateConfig) -> str:
    requirement = Requirement(spec)
    if requirement.url is not None:
        return spec
    specifiers = list(requirement.specifier)
    exact = next((specifier for specifier in specifiers if specifier.operator in {"==", "==="}), None)
    versions = _get_pkgs(
        client,
        config.index_url,
        requirement.name,
        pre_release=config.pre_release,
        python_version=config.python_version,
    )
    if exact is None:
        version = next((v for v in versions if requirement.specifier.contains(v, prereleases=config.pre_release)), None)
    else:
        version = versions[0] if versions and not _is_downgrade(exact.version, versions[0]) else None
    if version is None:
        return spec
    current = exact or next(
        (specifier for operator in (">=", "~=") for specifier in specifiers if specifier.operator == operator), None
    )
    if current is None:
        return _add_lower_bound(spec, requirement, _trim_version(version))
    new_version = _format_version(version, current)
    if _same_version(current, new_version):
        return spec
    return _replace_specifier(spec, current, new_version)


def _get_pkgs(
    client: Client,
    index_url: str,
    package: str,
    *,
    pre_release: bool,
    python_version: Version | None,
) -> list[Version]:
    versions: set[Version] = set()
    for raw_file, requires_python in _index_files(client, f"{index_url.rstrip('/')}/{canonicalize_name(package)}/"):
        if (
            python_version is not None
            and requires_python is not None
            and (specifier := _requires_python(requires_python)) is not None
            and not specifier.contains(python_version)
        ):
            continue
        try:
            version = _version_from_file(raw_file)
        except (InvalidSdistFilename, InvalidWheelFilename, IndexError, ValueError):
            continue
        else:
            versions.add(version)
    return sorted((v for v in versions if (True if pre_release else not v.is_prerelease)), reverse=True)


def _index_files(client: Client, url: str) -> list[tuple[str, str | None]]:
    # lock per URL to send one request per project across threads
    with _INDEX_CACHE_LOCK:
        entry = _INDEX_CACHE.setdefault(client, {}).setdefault(url, _IndexEntry())
    with entry.lock:
        if entry.files is None:
            entry.files = _fetch_index_files(client, url)
        return entry.files


@dataclass
class _IndexEntry:
    lock: Lock = field(default_factory=Lock)
    files: list[tuple[str, str | None]] | None = None


def _fetch_index_files(client: Client, url: str) -> list[tuple[str, str | None]]:
    response = client.get(url, headers={"Accept": _SIMPLE_ACCEPT}, follow_redirects=True)
    response.raise_for_status()
    if response.headers.get("content-type", "").startswith(_SIMPLE_JSON):
        return [
            (file["filename"], file.get("requires-python"))
            for file in response.json()["files"]
            if not file.get("yanked")
        ]
    parser = _IndexParser()
    parser.feed(response.text)
    return list(parser.files)


class _IndexParser(HTMLParser):
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


@cache
def _requires_python(value: str) -> SpecifierSet | None:
    try:
        return SpecifierSet(value)
    except InvalidSpecifier:  # accept invalid legacy metadata to match pip
        return None


def _version_from_file(filename: str) -> Version:
    if filename.endswith(".whl"):
        return parse_wheel_filename(filename)[1]
    if filename.endswith((".tar.gz", ".zip")):
        return parse_sdist_filename(filename)[1]
    file = filename.removesuffix(".tar.bz2").removesuffix(".whl")
    return Version(file.rsplit("-", 1)[1])


def _is_downgrade(pinned: str, version: Version) -> bool:
    try:
        return version < Version(pinned)
    except InvalidVersion:
        return False


def _trim_version(version: Version) -> str:
    result = str(version).partition("+")[0]
    while result.endswith(".0"):
        result = result[:-2]
    return result


def _add_lower_bound(spec: str, requirement: Requirement, version: str) -> str:
    new_spec = requirement.name
    if requirement.extras:
        new_spec = f"{new_spec}[{', '.join(sorted(requirement.extras))}]"
    new_spec = f"{new_spec}{requirement.specifier}{',' if requirement.specifier else ''}>={version}"
    if requirement.marker:
        new_spec = f"{new_spec};{requirement.marker}"
    new_requirement = str(Requirement(new_spec))
    if "'" in spec:
        new_requirement = new_requirement.replace('"', "'")
    return new_requirement


def _format_version(version: Version, current: Specifier) -> str:
    if current.operator == "===":
        return str(version)  # keep the full string for `===`, a string comparison
    if current.operator == "~=":
        if version.is_prerelease:
            return str(version).partition("+")[0]
        precision = max(2, len(Version(current.version).release))
        release = ".".join(str(part) for part in (*version.release, 0, 0)[:precision])
        return f"{version.epoch}!{release}" if version.epoch else release
    return _trim_version(version)


def _same_version(current: Specifier, new_version: str) -> bool:
    if current.operator == "===":
        return current.version == new_version
    return "*" not in current.version and Version(current.version) == Version(new_version)


def _replace_specifier(spec: str, current: Specifier, new_version: str) -> str:
    pattern = re.compile(
        rf"(?<![=!<>~]){re.escape(current.operator)}(?!=)(?P<space>\s*){re.escape(current.version)}(?![\w.*+!-])"
    )
    return pattern.sub(lambda match: f"{current.operator}{match['space']}{new_version}", spec, count=1)


def _update_js(client: Client, npm_registry: str, spec: str, *, pre_release: bool) -> str:
    ver_at = spec.rfind("@")
    package = spec[: len(spec) if ver_at in {-1, 0} else ver_at]
    version = _get_js_pkgs(client, npm_registry, package, pre_release=pre_release)[0]
    return f"{package}@{version}"


def _get_js_pkgs(client: Client, npm_registry: str, package: str, *, pre_release: bool) -> list[str]:
    response = client.get(
        f"{npm_registry.rstrip('/')}/{quote(package, safe='@')}",
        headers={"Accept": _NPM_ACCEPT},
        follow_redirects=True,
    )
    response.raise_for_status()
    found = [
        (key, version)
        for version, meta in response.json()["versions"].items()
        if (key := _semver_key(version)) is not None and (pre_release or key[3] == 1) and not meta.get("deprecated")
    ]
    return [version for _, version in sorted(found, reverse=True)]


def _semver_key(version: str) -> tuple[int, int, int, int, tuple[tuple[int, int | str], ...]] | None:
    if (match := _SEMVER.fullmatch(version)) is None:
        return None
    pre = match["pre"]
    identifiers = tuple((0, int(value)) if value.isdecimal() else (1, value) for value in pre.split(".")) if pre else ()
    return int(match["major"]), int(match["minor"]), int(match["patch"]), int(pre is None), identifiers


def package_type(spec: str) -> PkgType:
    try:
        requirement = Requirement(spec)
    except ValueError:
        return PkgType.JS
    return PkgType.PYTHON if requirement.url is None or urlsplit(requirement.url).scheme else PkgType.JS


def redact_url(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc.rpartition("@")[2], parsed.path, parsed.query, parsed.fragment))


def redact_text(text: str) -> str:
    return _URL_CREDENTIALS.sub("", text)


__all__ = [
    "PkgType",
    "UpdateConfig",
    "package_type",
    "redact_text",
    "redact_url",
    "update",
]

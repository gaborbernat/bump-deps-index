from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from functools import cache
from html.parser import HTMLParser
from threading import Lock
from typing import TYPE_CHECKING, Final, TypeAlias, TypeVar
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
    from httpx import Client, Response

# userinfo may hold quotes, so stop only at the characters that end it
_URL_CREDENTIALS: Final[re.Pattern[str]] = re.compile(r"(?<=://)[^/\s@]+@")
_NAME_AND_EXTRAS: Final = re.compile(r"^\s*[A-Za-z0-9][A-Za-z0-9._-]*(?:\s*\[[^\]]*\])?")
_SIMPLE_JSON: Final = "application/vnd.pypi.simple.v1+json"
_SIMPLE_ACCEPT: Final = f"{_SIMPLE_JSON}, application/vnd.pypi.simple.v1+html;q=0.2, text/html;q=0.01"
_NPM_ACCEPT: Final = "application/vnd.npm.install-v1+json; q=1.0, application/json; q=0.8"
_SEMVER: Final = re.compile(
    r"^v?(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<pre>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
# a full or partial version, such as `1`, `1.2` or `v1.2.3-beta.1`, which moves to the newest release
_NPM_PIN: Final[re.Pattern[str]] = re.compile(r"v?\d+(?:\.\d+){0,2}(?:-[0-9A-Za-z.-]+)?")
_JsonField = TypeVar("_JsonField", list, dict)
_SemverKey: TypeAlias = tuple[int, int, int, int, tuple[tuple[int, int, str], ...]]
_INDEX_CACHE: Final[WeakKeyDictionary[Client, dict[str, _IndexEntry]]] = WeakKeyDictionary()
_INDEX_CACHE_LOCK: Final[Lock] = Lock()


class PkgType(Enum):
    PYTHON = auto()
    JS = auto()


@dataclass(frozen=True)
class UpdateConfig:
    index_url: str
    authorization: str | None
    pre_release: bool
    python_version: Version | None


def update(client: Client, spec: str, pkg_type: PkgType, config: UpdateConfig) -> str:
    if pkg_type is PkgType.PYTHON:
        return _update_python(client, spec, config)
    return _update_js(client, spec, config)


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
        return _add_lower_bound(spec, _trim_version(version))
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
        # skip malformed entries the way the HTML parser skips malformed links
        return [
            (
                file["filename"],
                requires_python if isinstance(requires_python := file.get("requires-python"), str) else None,
            )
            for file in _json_field(response, "files", list)
            if isinstance(file, dict) and isinstance(file.get("filename"), str) and not file.get("yanked")
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
        return version < Version(pinned.removesuffix(".*"))
    except InvalidVersion:
        return False


def _trim_version(version: Version) -> str:
    result = str(version).partition("+")[0]
    while result.endswith(".0"):
        result = result[:-2]
    return result


def _add_lower_bound(spec: str, version: str) -> str:
    head = spec[: len(spec) - len(_NAME_AND_EXTRAS.sub("", spec, count=1))]
    specifier = spec[len(head) :].partition(";")[0].rstrip()
    rest = spec[len(head) + len(specifier) :]
    if not specifier:
        return f"{head}>={version}{rest}"
    if specifier.endswith(")"):
        return f"{head}{specifier[:-1]},>={version}){rest}"
    return f"{head}{specifier},>={version}{rest}"


def _format_version(version: Version, current: Specifier) -> str:
    if current.operator == "===":
        return str(version)  # keep the full string for `===`, a string comparison
    if current.version.endswith(".*"):
        return f"{_release_prefix(version, len(Version(current.version.removesuffix('.*')).release))}.*"
    if current.operator == "~=":
        if version.is_prerelease:
            return str(version).partition("+")[0]
        return _release_prefix(version, max(2, len(Version(current.version).release)))
    return _trim_version(version)


def _release_prefix(version: Version, depth: int) -> str:
    release = ".".join(str(part) for part in (*version.release, *(0,) * depth)[:depth])
    return f"{version.epoch}!{release}" if version.epoch else release


def _same_version(current: Specifier, new_version: str) -> bool:
    if current.operator == "===" or current.version.endswith(".*"):
        return current.version == new_version
    return Version(current.version) == Version(new_version)


def _replace_specifier(spec: str, current: Specifier, new_version: str) -> str:
    pattern = re.compile(
        rf"(?<![=!<>~]){re.escape(current.operator)}(?!=)(?P<space>\s*){re.escape(current.version)}(?![\w.*+!-])"
    )
    return pattern.sub(lambda match: f"{current.operator}{match['space']}{new_version}", spec, count=1)


def _update_js(client: Client, spec: str, config: UpdateConfig) -> str:
    at = spec.find("@", 1)  # skip the `@` that opens a scoped package name
    package, wanted = (spec, "") if at == -1 else (spec[:at], spec[at + 1 :])
    if not (versions := _get_js_pkgs(client, package, config)):
        return spec  # the registry has no release you accept, such as only pre-releases
    if not wanted or _NPM_PIN.fullmatch(wanted):
        pinned = _semver_key(_pad_version(wanted)) if wanted else None
        return spec if pinned is not None and versions[0][0] < pinned else f"{package}@{versions[0][1]}"
    operator = wanted[: len(wanted) - len(wanted.lstrip("^~>="))]
    # keep ranges this tool cannot compare, such as `<2` or a dist-tag
    if operator not in {"^", "~", ">="} or (current := _semver_key(wanted[len(operator) :])) is None:
        return spec
    # `^1.2.3` keeps the major inside its range, `^0.2.3` and `~1.2.3` keep the minor
    depth = {"~": 2, ">=": 0}.get(operator, next((at for at, part in enumerate(current[:2]) if part), 2) + 1)
    newest = next((version for key, version in versions if key >= current and key[:depth] == current[:depth]), None)
    return spec if newest is None else f"{package}@{operator}{newest}"


def _get_js_pkgs(client: Client, package: str, config: UpdateConfig) -> list[tuple[_SemverKey, str]]:
    authorization = {} if config.authorization is None else {"Authorization": config.authorization}
    response = client.get(
        f"{config.index_url.rstrip('/')}/{quote(package, safe='@')}",
        headers={"Accept": _NPM_ACCEPT, **authorization},
        follow_redirects=True,
    )
    response.raise_for_status()
    return sorted(
        (
            (key, version)
            for version, meta in _json_field(response, "versions", dict).items()
            if (key := _semver_key(version)) is not None
            and (config.pre_release or key[3] == 1)
            and not (isinstance(meta, dict) and meta.get("deprecated"))
        ),
        reverse=True,
    )


def _json_field(response: Response, name: str, kind: type[_JsonField]) -> _JsonField:
    if not isinstance(payload := response.json(), dict) or not isinstance(value := payload.get(name), kind):
        msg = f"{response.url} has no {name} {kind.__name__}"
        raise TypeError(msg)
    return value


def _pad_version(version: str) -> str:
    release, dash, pre = version.partition("-")
    parts = release.split(".")
    return f"{'.'.join([*parts, *['0'] * (3 - len(parts))])}{dash}{pre}"


def _semver_key(version: str) -> _SemverKey | None:
    if (match := _SEMVER.fullmatch(version)) is None:
        return None
    pre = match["pre"]
    # semver ranks numeric identifiers below alphanumeric ones
    identifiers = (
        tuple((0, int(part), "") if part.isdecimal() else (1, 0, part) for part in pre.split(".")) if pre else ()
    )
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

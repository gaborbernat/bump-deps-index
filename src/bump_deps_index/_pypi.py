from __future__ import annotations

from dataclasses import dataclass, field
from functools import cache
from html.parser import HTMLParser
from threading import Lock
from typing import TYPE_CHECKING, Final, NamedTuple

from httpx import HTTPStatusError, codes
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.utils import (
    InvalidSdistFilename,
    InvalidWheelFilename,
    canonicalize_name,
    parse_sdist_filename,
    parse_wheel_filename,
)
from packaging.version import Version

from bump_deps_index._parsed import json_field, mappings

if TYPE_CHECKING:
    from httpx import Client

_SIMPLE_JSON: Final[str] = "application/vnd.pypi.simple.v1+json"
_SIMPLE_ACCEPT: Final[str] = f"{_SIMPLE_JSON}, application/vnd.pypi.simple.v1+html;q=0.2, text/html;q=0.01"


class IndexLookup(NamedTuple):
    url: str
    first: tuple[str, ...] = ()
    """uv indexes checked before `url`; uv takes a package from the first one that has it."""
    extra: tuple[str, ...] = ()
    """pip extra indexes, whose releases pip merges with those of `url`."""


class SimpleIndex:
    """Reads PyPI simple index pages, fetching each page once across threads."""

    def __init__(self, client: Client) -> None:
        self.client = client
        self._pages: dict[str, _Page] = {}
        self._lock = Lock()

    def versions(
        self, lookup: IndexLookup, package: str, *, python_version: Version | None, pre_release: bool
    ) -> list[Version]:
        name = canonicalize_name(package)
        versions: set[Version] = set()
        for file in self._project_files(lookup, name):
            if (
                python_version is not None
                and file.requires_python is not None
                and (specifier := _requires_python(file.requires_python)) is not None
                and not specifier.contains(python_version)
            ):
                continue
            try:
                project, version = _parse_filename(file.filename)
            except (InvalidSdistFilename, InvalidWheelFilename, IndexError, ValueError):
                continue
            if project == name:  # an index page may list files of other projects, as pip and uv skip them
                versions.add(version)
        return sorted((version for version in versions if pre_release or not version.is_prerelease), reverse=True)

    def _project_files(self, lookup: IndexLookup, name: str) -> list[_IndexFile]:
        # uv takes a package from the first of its indexes that has it; pip merges its index with the extra indexes
        for urls in [*((url,) for url in lookup.first), (lookup.url, *lookup.extra)]:
            pages: list[list[_IndexFile]] = []
            missing: list[HTTPStatusError] = []
            for url in urls:
                try:
                    pages.append(self._files(f"{url.rstrip('/')}/{name}/"))
                except HTTPStatusError as exc:
                    if exc.response.status_code != codes.NOT_FOUND:
                        raise
                    missing.append(exc)
            if pages:
                return [file for page in pages for file in page]
        raise missing[0]  # no index has the package; report the not found answer of the main index

    def _files(self, url: str) -> list[_IndexFile]:
        with self._lock:
            page = self._pages.setdefault(url, _Page())
        with page.lock:
            if page.files is None:
                page.files = self._fetch(url)
            return page.files

    def _fetch(self, url: str) -> list[_IndexFile]:
        response = self.client.get(url, headers={"Accept": _SIMPLE_ACCEPT}, follow_redirects=True)
        response.raise_for_status()
        if response.headers.get("content-type", "").startswith(_SIMPLE_JSON):
            # skip malformed entries the way the HTML parser skips malformed links
            return [
                _IndexFile(filename, requires if isinstance(requires := file.get("requires-python"), str) else None)
                for file in mappings(json_field(response, "files", list))
                if isinstance(filename := file.get("filename"), str) and not file.get("yanked")
            ]
        parser = _IndexParser()
        parser.feed(response.text)
        return parser.files


@dataclass
class _Page:
    lock: Lock = field(default_factory=Lock)
    files: list[_IndexFile] | None = None


class _IndexFile(NamedTuple):
    filename: str
    requires_python: str | None


class _IndexParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.files: list[_IndexFile] = []
        self._tags: list[str] = []
        self._attrs: list[tuple[str, str | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._tags.append(tag)
        self._attrs = attrs

    def handle_endtag(self, tag: str) -> None:
        if self._tags and self._tags[-1] == tag:
            self._tags.pop()
        self._attrs = []

    def handle_data(self, data: str) -> None:
        if (
            self._tags
            and self._tags[-1] == "a"
            and data.strip()
            and all(key != "data-yanked" for key, _ in self._attrs)
        ):
            requires_python = next((value for key, value in self._attrs if key == "data-requires-python"), None)
            self.files.append(_IndexFile(data.strip(), requires_python))


@cache
def _requires_python(value: str) -> SpecifierSet | None:
    try:
        return SpecifierSet(value)
    except InvalidSpecifier:  # accept invalid legacy metadata to match pip
        return None


def _parse_filename(filename: str) -> tuple[str, Version]:
    if filename.endswith(".whl"):
        name, version, *_ = parse_wheel_filename(filename)
        return name, version
    if filename.endswith((".tar.gz", ".zip")):
        return parse_sdist_filename(filename)
    name, _, version = filename.removesuffix(".tar.bz2").rpartition("-")
    return canonicalize_name(name), Version(version)


__all__ = [
    "IndexLookup",
    "SimpleIndex",
]

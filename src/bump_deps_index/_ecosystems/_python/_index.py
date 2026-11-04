from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from html.parser import HTMLParser
from operator import itemgetter
from typing import TYPE_CHECKING

from httpx import HTTPStatusError, codes
from packaging.requirements import Requirement
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.utils import canonicalize_name, parse_sdist_filename, parse_wheel_filename
from packaging.version import Version

from bump_deps_index._ecosystems._common._candidates import (
    Candidate,
    Candidates,
    Lookup,
    Registry,
    accepted_versions,
    package_exclude_newer,
)
from bump_deps_index._parsed import json_field, mappings, parse_timestamp

if TYPE_CHECKING:
    from collections.abc import Iterator
    from datetime import datetime

    from bump_deps_index._config._project import IndexSettings
    from bump_deps_index._http._session import Session
    from bump_deps_index._lookup import IndexLookup


class SimpleIndex(Registry):
    def __init__(self, session: Session, settings: IndexSettings) -> None:
        self._session = session
        self._settings = settings

    def candidates(self, lookup: Lookup) -> Candidates:
        # lazy, so a URL requirement, which the bump keeps as is, reads no index
        return Candidates(versions=self._versions(lookup), preferred=None)

    def _versions(self, lookup: Lookup) -> Iterator[str]:
        name = canonicalize_name(lookup.name)
        candidates: list[tuple[Version, Candidate]] = []
        for file in self._project_files(lookup.indexes, name):
            if (
                lookup.python_floor is not None
                and file.requires_python is not None
                and (specifier := _requires_python(file.requires_python)) is not None
                and not specifier.contains(lookup.python_floor)
            ):
                continue
            try:
                project, version = _parse_filename(file.filename)
            except ValueError:
                continue
            if project == name:  # an index page may list files of other projects, as pip and uv skip them
                candidates.append((
                    version,
                    Candidate(version=str(version), uploaded=file.uploaded, withdrawn=file.yanked),
                ))
        # a stable sort keeps the spelling of the first file of a version ahead of later ones
        candidates.sort(key=itemgetter(0), reverse=True)
        yield from accepted_versions(
            (candidate for _, candidate in candidates),
            exclude_newer=package_exclude_newer(self._settings, name, canonical=canonicalize_name),
            pre_release=lookup.pre_release,
            is_prerelease=lambda text: Version(text).is_prerelease,
        )

    def _project_files(self, lookup: IndexLookup, name: str) -> list[_IndexFile]:
        # uv takes a package from the first of its indexes that has it; pip merges its index with the extra indexes
        for urls in [*((url,) for url in lookup.first), (lookup.url, *lookup.extra)]:
            pages: list[list[_IndexFile]] = []
            missing: list[HTTPStatusError] = []
            for url in urls:
                try:
                    pages.append(self._fetch(f"{url.rstrip('/')}/{name}/"))
                except HTTPStatusError as exc:
                    if exc.response.status_code != codes.NOT_FOUND:
                        raise
                    missing.append(exc)
            if pages:
                return [file for page in pages for file in page]
        raise missing[0]  # no index has the package; report the not found answer of the main index

    def _fetch(self, url: str) -> list[_IndexFile]:
        json_type = "application/vnd.pypi.simple.v1+json"
        accept = f"{json_type}, application/vnd.pypi.simple.v1+html;q=0.2, text/html;q=0.01"
        response = self._session.get(url, accept=accept)
        if response.headers.get("content-type", "").startswith(json_type):
            # skip malformed entries the way the HTML parser skips malformed links
            return [
                _IndexFile(
                    filename=filename,
                    requires_python=requires if isinstance(requires := file.get("requires-python"), str) else None,
                    uploaded=parse_timestamp(file.get("upload-time")),
                    yanked=bool(file.get("yanked")),
                )
                for file in mappings(json_field(response, "files", list))
                if isinstance(filename := file.get("filename"), str)
            ]
        parser = _IndexParser()
        parser.feed(response.text)
        return parser.files


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


@dataclass(frozen=True, slots=True, kw_only=True)
class _IndexFile:
    filename: str
    requires_python: str | None
    yanked: bool
    # PEP 700 upload time; the HTML simple API has none
    uploaded: datetime | None = None


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
        if self._tags and self._tags[-1] == "a" and data.strip():
            requires_python = next((value for key, value in self._attrs if key == "data-requires-python"), None)
            yanked = any(key == "data-yanked" for key, _ in self._attrs)
            self.files.append(_IndexFile(filename=data.strip(), requires_python=requires_python, yanked=yanked))


def python_name(spec: str) -> str:
    return Requirement(spec).name


__all__ = [
    "SimpleIndex",
    "python_name",
]

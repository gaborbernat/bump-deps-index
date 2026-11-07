from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from bump_deps_index._ecosystems._common._candidates import Candidates


def bump_js(spec: str, candidates: Candidates) -> str:
    package, wanted = _split_npm_spec(spec)
    # the registry passes valid versions only, ranked newest first; the filter narrows the type
    ranked = [(key, version) for version in candidates.versions if (key := _semver(version)) is not None]
    if (bounds := _in_range(wanted, ranked)) is None:
        return spec
    operator, in_range = bounds
    if not in_range:  # the registry has no release you accept, such as only pre-releases
        return spec
    # npm installs the `latest` dist-tag when it fits the range, and the highest version otherwise
    preferred = candidates.preferred
    return f"{package}@{operator}{preferred if preferred in in_range else in_range[0]}"


def _split_npm_spec(spec: str) -> tuple[str, str]:
    at = spec.find("@", 1)  # skip the `@` that opens a scoped package name
    return (spec, "") if at == -1 else (spec[:at], spec[at + 1 :])


def _semver(version: str) -> _Semver | None:
    pattern = (
        r"^v?(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
        r"(?:-(?P<pre>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
    )
    if (match := re.fullmatch(pattern, version)) is None:
        return None
    pre = match["pre"]
    # semver ranks numeric identifiers below alphanumeric ones
    identifiers = (
        tuple((0, int(part), "") if part.isdecimal() else (1, 0, part) for part in pre.split(".")) if pre else ()
    )
    return _Semver(
        major=int(match["major"]),
        minor=int(match["minor"]),
        patch=int(match["patch"]),
        release=pre is None,
        pre=identifiers,
    )


@dataclass(frozen=True, slots=True, kw_only=True, order=True)
class _Semver:
    major: int
    minor: int
    patch: int
    # a release sorts above its pre-releases
    release: bool
    pre: tuple[tuple[int, int, str], ...]

    def prefix(self, depth: int) -> tuple[int, ...]:
        return (self.major, self.minor, self.patch)[:depth]


def _in_range(wanted: str, ranked: list[tuple[_Semver, str]]) -> tuple[str, list[str]] | None:
    # a full or partial version, such as `1`, `1.2` or `v1.2.3-beta.1`, which moves to the newest release
    if not wanted or re.fullmatch(r"v?\d+(?:\.\d+){0,2}(?:-[0-9A-Za-z.-]+)?", wanted):
        pinned = _semver(_pad_version(wanted)) if wanted else None
        return "", [version for key, version in ranked if pinned is None or key >= pinned]
    operator = wanted[: len(wanted) - len(wanted.lstrip("^~>="))]
    # keep ranges this tool cannot compare, such as `<2` or a dist-tag
    if operator not in {"^", "~", ">="} or (current := _semver(wanted[len(operator) :])) is None:
        return None
    match operator:
        case ">=":
            depth = 0
        case "~":
            depth = 2
        case _:  # `^1.2.3` keeps the major inside its range, `^0.2.3` the minor and `^0.0.3` the patch
            depth = 1 if current.major else 2 if current.minor else 3
    in_range = [version for key, version in ranked if key >= current and key.prefix(depth) == current.prefix(depth)]
    return operator, in_range


def _pad_version(version: str) -> str:
    release, dash, pre = version.partition("-")
    parts = release.split(".")
    return f"{'.'.join([*parts, *['0'] * (3 - len(parts))])}{dash}{pre}"


def npm_name(spec: str) -> str:
    return _split_npm_spec(spec)[0]


def rank_versions(versions: Iterable[str]) -> list[str]:
    ranked = sorted(((key, version) for version in versions if (key := _semver(version)) is not None), reverse=True)
    return [version for _, version in ranked]


def is_prerelease(version: str) -> bool:
    return (key := _semver(version)) is not None and not key.release


__all__ = [
    "bump_js",
    "is_prerelease",
    "npm_name",
    "rank_versions",
]

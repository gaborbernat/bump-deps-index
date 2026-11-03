from __future__ import annotations

import re
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from collections.abc import Iterable


def bump_js(spec: str, versions: Iterable[str], latest: str | None, *, pre_release: bool) -> str:
    package, wanted = split_npm_spec(spec)
    ranked = sorted(
        (
            (key, version)
            for version in versions
            if (key := _semver(version)) is not None and (pre_release or key.release)
        ),
        reverse=True,
    )
    # a full or partial version, such as `1`, `1.2` or `v1.2.3-beta.1`, which moves to the newest release
    if not wanted or re.fullmatch(r"v?\d+(?:\.\d+){0,2}(?:-[0-9A-Za-z.-]+)?", wanted):
        operator, pinned = "", _semver(_pad_version(wanted)) if wanted else None
        candidates = [version for key, version in ranked if pinned is None or key >= pinned]
    else:
        operator = wanted[: len(wanted) - len(wanted.lstrip("^~>="))]
        # keep ranges this tool cannot compare, such as `<2` or a dist-tag
        if operator not in {"^", "~", ">="} or (current := _semver(wanted[len(operator) :])) is None:
            return spec
        match operator:
            case ">=":
                depth = 0
            case "~":
                depth = 2
            case _:  # `^1.2.3` keeps the major inside its range, `^0.2.3` the minor and `^0.0.3` the patch
                depth = 1 if current.major else 2 if current.minor else 3
        candidates = [version for key, version in ranked if key >= current and key[:depth] == current[:depth]]
    if not candidates:  # the registry has no release you accept, such as only pre-releases
        return spec
    # npm installs the `latest` dist-tag when it fits the range, and the highest version otherwise
    return f"{package}@{operator}{latest if latest in candidates else candidates[0]}"


def split_npm_spec(spec: str) -> tuple[str, str]:
    at = spec.find("@", 1)  # skip the `@` that opens a scoped package name
    return (spec, "") if at == -1 else (spec[:at], spec[at + 1 :])


class _Semver(NamedTuple):
    major: int
    minor: int
    patch: int
    release: bool
    """A release sorts above its pre-releases."""
    pre: tuple[tuple[int, int, str], ...]


def _pad_version(version: str) -> str:
    release, dash, pre = version.partition("-")
    parts = release.split(".")
    return f"{'.'.join([*parts, *['0'] * (3 - len(parts))])}{dash}{pre}"


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
    return _Semver(int(match["major"]), int(match["minor"]), int(match["patch"]), pre is None, identifiers)


__all__ = [
    "bump_js",
    "split_npm_spec",
]

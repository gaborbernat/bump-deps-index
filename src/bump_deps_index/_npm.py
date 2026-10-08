from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final, NamedTuple
from urllib.parse import quote

from bump_deps_index._parsed import json_field, table

if TYPE_CHECKING:
    from httpx import Client

    from bump_deps_index._parsed import Parsed

_ACCEPT: Final[str] = "application/vnd.npm.install-v1+json; q=1.0, application/json; q=0.8"
_SEMVER: Final[re.Pattern[str]] = re.compile(
    r"^v?(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<pre>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
# a full or partial version, such as `1`, `1.2` or `v1.2.3-beta.1`, which moves to the newest release
_PIN: Final[re.Pattern[str]] = re.compile(r"v?\d+(?:\.\d+){0,2}(?:-[0-9A-Za-z.-]+)?")


def update_js(client: Client, spec: str, registry: str, authorization: str | None, *, pre_release: bool) -> str:
    at = spec.find("@", 1)  # skip the `@` that opens a scoped package name
    package, wanted = (spec, "") if at == -1 else (spec[:at], spec[at + 1 :])
    versions, latest = _versions(client, package, registry, authorization, pre_release=pre_release)
    if not wanted or _PIN.fullmatch(wanted):
        operator, pinned = "", _semver(_pad_version(wanted)) if wanted else None
        candidates = [version for key, version in versions if pinned is None or key >= pinned]
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
        candidates = [version for key, version in versions if key >= current and key[:depth] == current[:depth]]
    if not candidates:  # the registry has no release you accept, such as only pre-releases
        return spec
    # npm installs the `latest` dist-tag when it fits the range, and the highest version otherwise
    return f"{package}@{operator}{latest if latest in candidates else candidates[0]}"


def _versions(
    client: Client, package: str, registry: str, authorization: str | None, *, pre_release: bool
) -> tuple[list[tuple[_Semver, str]], Parsed]:
    response = client.get(
        f"{registry.rstrip('/')}/{quote(package, safe='@')}",
        headers={"Accept": _ACCEPT, **({} if authorization is None else {"Authorization": authorization})},
        follow_redirects=True,
    )
    response.raise_for_status()
    return sorted(
        (
            (key, version)
            for version, meta in json_field(response, "versions", dict).items()
            if (key := _semver(version)) is not None
            and (pre_release or key.release)
            and not (isinstance(meta, dict) and meta.get("deprecated"))
        ),
        reverse=True,
    ), table(response.json(), "dist-tags").get("latest")


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
    if (match := _SEMVER.fullmatch(version)) is None:
        return None
    pre = match["pre"]
    # semver ranks numeric identifiers below alphanumeric ones
    identifiers = (
        tuple((0, int(part), "") if part.isdecimal() else (1, 0, part) for part in pre.split(".")) if pre else ()
    )
    return _Semver(int(match["major"]), int(match["minor"]), int(match["patch"]), pre is None, identifiers)


__all__ = [
    "update_js",
]

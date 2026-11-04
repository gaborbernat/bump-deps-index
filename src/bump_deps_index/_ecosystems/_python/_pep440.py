from __future__ import annotations

import re
from typing import TYPE_CHECKING

from packaging.requirements import Requirement
from packaging.version import InvalidVersion, Version

if TYPE_CHECKING:
    from packaging.specifiers import Specifier

    from bump_deps_index._ecosystems._base import Candidates


def bump_python(spec: str, candidates: Candidates) -> str:
    if (requirement := Requirement(spec)).url is not None:
        return spec
    specifiers = list(requirement.specifier)
    exact = next((specifier for specifier in specifiers if specifier.operator in {"==", "==="}), None)
    current = exact or next(
        (specifier for operator in (">=", "~=") for specifier in specifiers if specifier.operator == operator), None
    )
    local = _local_label(exact)
    for version in map(Version, candidates.versions):
        # the index already dropped the pre-releases you exclude
        if exact is None and not requirement.specifier.contains(version, prereleases=True):
            continue
        if exact is not None and _is_downgrade(exact.version, version):
            break
        if local is not None and version.local != local:  # a local label, such as `+cpu`, names a build you keep
            continue
        if current is None:
            return _add_lower_bound(spec, _trim_version(version))
        new_version = _format_version(version, current)
        if _same_version(current, new_version):
            break
        new = _replace_specifier(spec, current, new_version)
        # the other specifiers may exclude the new pin, such as `<2` next to `==1.0`
        if Requirement(new).specifier.contains(version, prereleases=True):
            return new
    return spec


def _local_label(exact: Specifier | None) -> str | None:
    if exact is None or exact.version.endswith(".*"):
        return None
    try:
        return Version(exact.version).local
    except InvalidVersion:
        return None


def _is_downgrade(pinned: str, version: Version) -> bool:
    try:
        return version < Version(pinned.removesuffix(".*"))
    except InvalidVersion:
        return False


def _add_lower_bound(spec: str, version: str) -> str:
    head = spec[: len(spec) - len(re.sub(r"^\s*[A-Za-z0-9][A-Za-z0-9._-]*(?:\s*\[[^\]]*\])?", "", spec, count=1))]
    specifier = spec[len(head) :].partition(";")[0].rstrip()
    rest = spec[len(head) + len(specifier) :]
    if not specifier:
        return f"{head}>={version}{rest}"
    if specifier.endswith(")"):
        return f"{head}{specifier[:-1]},>={version}){rest}"
    return f"{head}{specifier},>={version}{rest}"


def _trim_version(version: Version) -> str:
    result = str(version).partition("+")[0]
    while result.endswith(".0"):
        result = result[:-2]
    return result


def _format_version(version: Version, current: Specifier) -> str:
    if current.operator == "===":
        return str(version)  # keep the full string for `===`, a string comparison
    if current.version.endswith(".*"):
        return f"{_release_prefix(version, len(Version(current.version.removesuffix('.*')).release))}.*"
    if current.operator == "~=":
        if version.is_prerelease:
            return str(version).partition("+")[0]
        return _release_prefix(version, max(2, len(Version(current.version).release)))
    trimmed = _trim_version(version)
    # keep the local label of a pin such as `==1.0+cpu`
    return f"{trimmed}+{version.local}" if "+" in current.version else trimmed


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


__all__ = [
    "bump_python",
]

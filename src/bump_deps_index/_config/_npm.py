from __future__ import annotations

import os
import re
from base64 import b64decode, b64encode
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from collections.abc import Mapping

# npm reads `${NAME}` from the environment and keeps it as written when unset, and reads `${NAME?}` as empty then
_ENV_REFERENCE: Final[re.Pattern[str]] = re.compile(r"\$\{(?P<name>[^${}?]+)(?P<optional>\?)?\}")
# the token comes last to override a basic credential for the same registry
_CREDENTIALS: Final[dict[str, str]] = {":_auth": "Basic", ":_authToken": "Bearer"}


def npm_registry() -> str:
    return _npm_env("NPM_CONFIG_REGISTRY") or _npmrc().get("registry") or "https://registry.npmjs.org"


def npm_settings() -> NpmSettings:
    values = _npmrc()
    return NpmSettings(
        registry_by_scope={
            key.removesuffix(":registry"): value
            for key, value in values.items()
            if key.startswith("@") and key.endswith(":registry")
        },
        authorization_by_key=_npm_authorizations(values),
    )


def _npmrc() -> dict[str, str]:
    user = Path(_npm_env("NPM_CONFIG_USERCONFIG") or Path.home() / ".npmrc")
    return {**_read_npmrc(user), **_read_npmrc(Path.cwd() / ".npmrc")}


def _npm_env(name: str) -> str | None:
    # npm reads its settings from the environment in any letter case, such as `npm_config_registry`
    return next((value for key, value in os.environ.items() if key.upper() == name and value), None)


def _read_npmrc(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return {}
    # npm keeps the last assignment of a key
    return {
        key.strip(): _npmrc_value(value)
        for key, separator, value in (line.partition("=") for line in lines)
        if separator and not key.lstrip().startswith(("#", ";"))
    }


def _npmrc_value(raw: str) -> str:
    value = raw.strip()
    # npm drops a `;` or `#` comment after an unquoted value, and substitutes `${NAME}` from the environment
    if len(value) > 1 and value[0] in {"'", '"'} and value.endswith(value[0]):
        value = value[1:-1]
    else:
        value = re.split(r"[;#]", value, maxsplit=1)[0].rstrip()
    return _ENV_REFERENCE.sub(lambda match: os.environ.get(match["name"], "" if match["optional"] else match[0]), value)


def _npm_authorizations(values: dict[str, str]) -> dict[str, str]:
    # npm sends a token over a `_auth` value, and that over a `username` with a base64 `_password`
    found: dict[str, str] = {}
    for key, username in values.items():
        prefix = key.removesuffix(":username")
        if key.startswith("//") and key != prefix and (basic := _basic(username, values.get(f"{prefix}:_password"))):
            found[prefix] = f"Basic {basic}"
    for suffix, scheme in _CREDENTIALS.items():
        found |= {
            key.removesuffix(suffix): f"{scheme} {value}"
            for key, value in values.items()
            if key.startswith("//") and key.endswith(suffix)
        }
    return found


def _basic(username: str, encoded_password: str | None) -> str | None:
    try:
        password = b64decode(encoded_password or "").decode()
    except ValueError:  # skip a password that is not base64, as you could not log in with it
        return None
    return b64encode(f"{username}:{password}".encode()).decode() if password else None


@dataclass(frozen=True)
class NpmSettings:
    registry_by_scope: Mapping[str, str]
    authorization_by_key: Mapping[str, str]

    def registry(self, spec: str, default: str) -> str:
        return self.registry_by_scope.get(spec.partition("/")[0], default) if spec.startswith("@") else default

    def authorization(self, registry: str) -> str | None:
        parsed = urlsplit(registry)
        host, parts = parsed.netloc.rpartition("@")[2], [part for part in parsed.path.split("/") if part]
        # npm walks up the registry path one segment at a time and sends the first credential it finds
        for depth in range(len(parts), -1, -1):
            key = "".join((f"//{host}", *(f"/{part}" for part in parts[:depth])))
            if value := self.authorization_by_key.get(f"{key}/") or self.authorization_by_key.get(key):
                return value
        return None


__all__ = [
    "NpmSettings",
    "npm_registry",
    "npm_settings",
]

from __future__ import annotations

import ssl
from urllib.parse import quote, urlsplit

from httpx import Client, HTTPError
from truststore import SSLContext
from yaml import YAMLError
from yaml import safe_load as load_yaml

def hook_languages(repo: str, rev: str | None) -> dict[str, str]:
    if rev is None or (url := _manifest_url(repo, rev)) is None:
        return {}
    try:
        with Client(verify=SSLContext(ssl.PROTOCOL_TLS_CLIENT), timeout=10) as client:
            manifest = load_yaml(client.get(url, follow_redirects=True).raise_for_status().text)
    except (HTTPError, YAMLError):  # guess from the dependency shape when the manifest is out of reach
        return {}
    return {
        hook["id"]: hook["language"]
        for hook in (manifest if isinstance(manifest, list) else [])
        if isinstance(hook, dict) and isinstance(hook.get("id"), str) and isinstance(hook.get("language"), str)
    }


def _manifest_url(repo: str, rev: str) -> str | None:
    parsed = urlsplit(repo)
    path = parsed.path.strip("/").removesuffix(".git")
    if parsed.netloc == "github.com":
        return f"https://raw.githubusercontent.com/{path}/{quote(rev)}/.pre-commit-hooks.yaml"
    if parsed.netloc == "gitlab.com":
        return f"https://gitlab.com/{path}/-/raw/{quote(rev)}/.pre-commit-hooks.yaml"
    return None


__all__ = [
    "hook_languages",
]

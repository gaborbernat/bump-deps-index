from __future__ import annotations

from urllib.parse import quote, urlsplit

from httpx import HTTPError
from yaml import YAMLError
from yaml import safe_load as load_yaml

from ._session import new_client


def hook_languages(repo: str, rev: str | None) -> dict[str, str]:
    if rev is None or (url := _manifest_url(repo, rev)) is None:
        return {}
    try:
        with new_client(timeout=10) as client:
            manifest = load_yaml(client.get(url, follow_redirects=True).raise_for_status().text)
    except (HTTPError, YAMLError):  # Without a manifest, the loader infers package types from dependency strings.
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

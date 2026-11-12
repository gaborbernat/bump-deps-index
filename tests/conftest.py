from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Protocol

import httpx
import pytest

from bump_deps_index import main

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from pytest_httpx import HTTPXMock


@pytest.fixture
def isolated_index_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    home = tmp_path / "home"
    for name in ("HOME", "USERPROFILE"):  # Windows reads the home folder from `USERPROFILE`
        monkeypatch.setenv(name, str(home))
    for name in (
        "APPDATA",
        "NPM_CONFIG_REGISTRY",
        "NPM_CONFIG_USERCONFIG",
        "PIP_CONFIG_FILE",
        "PIP_EXTRA_INDEX_URL",
        "PIP_INDEX_URL",
        "PIP_UPLOADED_PRIOR_TO",
        "UV_DEFAULT_INDEX",
        "UV_EXCLUDE_NEWER",
        "UV_EXTRA_INDEX_URL",
        "UV_INDEX",
        "UV_INDEX_URL",
        "XDG_CONFIG_HOME",
    ):
        monkeypatch.delenv(name, raising=False)
    return home


@pytest.fixture
def work_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


def index_args(*args: str) -> list[str]:
    return ["-i", "https://pypi.example/simple", "-n", "https://npm.example", "-p", "no", "--no-exclude-newer", *args]


PYPI_FOO: Final[dict[str, str]] = {"https://pypi.example/simple/foo/": "<a>foo-2.tar.gz</a>"}


@pytest.fixture
def pages(request: pytest.FixtureRequest, httpx_mock: HTTPXMock) -> None:
    for url, page in request.param.items():
        httpx_mock.add_response(url=url, text=page)


@dataclass(frozen=True, slots=True, kw_only=True)
class Case:
    content: str
    pages: dict[str, str]
    updates: set[str]
    expected: str


class Bump(Protocol):
    def __call__(
        self,
        spec: str,
        pages: Mapping[str, httpx.Response],
        *,
        pre_release: bool,
        requires_python: str | None,
        exclude_newer: str | None,
    ) -> str: ...


@pytest.fixture
def bump(
    capsys: pytest.CaptureFixture[str], httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Bump:
    monkeypatch.chdir(tmp_path)

    def run_main(
        spec: str,
        pages: Mapping[str, httpx.Response],
        *,
        pre_release: bool,
        requires_python: str | None,
        exclude_newer: str | None,
    ) -> str:
        for url, response in pages.items():
            httpx_mock.add_callback(lambda _, served=response: served, url=url, is_optional=True)
        if requires_python is not None:
            (tmp_path / "pyproject.toml").write_text(f'[project]\nrequires-python = "{requires_python}"\n', "utf-8")
        args = ["-i", "https://I.com", "-n", "https://N.com", "-p", "yes" if pre_release else "no"]
        if exclude_newer is not None:
            args += ["--exclude-newer", exclude_newer]
        main([*args, spec])
        return capsys.readouterr().out.splitlines()[-1].rpartition(" -> ")[2]

    return run_main


@pytest.fixture
def workspace(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    httpx_mock: HTTPXMock,
    isolated_index_settings: Path,
) -> None:
    env, files = request.param
    for name, value in env.items():
        monkeypatch.setenv(name, value.format(tmp=tmp_path, devnull=os.devnull))
    for name, content in files.items():
        path = isolated_index_settings / name[2:] if name.startswith("~/") else tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content if isinstance(content, bytes) else content.encode())
    (cwd := tmp_path / "project" / "sub").mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(cwd)
    httpx_mock.add_callback(_serve, is_reusable=True)


def _serve(request: httpx.Request) -> httpx.Response:
    if request.url.path.endswith("/a/"):
        return httpx.Response(200, text="<a>a-1.tar.gz</a>")
    return httpx.Response(200, json={"versions": {"1.0.0": {}}})


__all__ = [
    "PYPI_FOO",
    "Bump",
    "Case",
    "index_args",
]

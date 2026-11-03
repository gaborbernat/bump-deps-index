from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

import pytest

from bump_deps_index import main

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    import httpx
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


__all__ = [
    "Bump",
    "index_args",
]

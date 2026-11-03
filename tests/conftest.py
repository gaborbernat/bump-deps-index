from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import TYPE_CHECKING
from urllib.parse import unquote

import httpx
import pytest
from packaging.utils import canonicalize_name

from bump_deps_index import Options, main, run

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
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
def index(httpx_mock: HTTPXMock) -> FakeIndex:
    fake = FakeIndex(
        pypi={},
        npm={},
        requires_python={},
        index_url="https://pypi.example/simple",
        npm_registry="https://npm.example",
        responses={},
        hooks=[],
    )
    httpx_mock.add_callback(fake.serve, is_optional=True, is_reusable=True)
    return fake


@dataclass
class FakeIndex:
    pypi: dict[str, list[str]]
    npm: dict[str, list[str]]
    requires_python: dict[str, str]
    index_url: str
    npm_registry: str
    responses: dict[str, httpx.Response]
    hooks: list[Callable[[httpx.Request], None]]

    def run(
        self,
        *filenames: Path,
        pkgs: Sequence[str] = (),
        pre_release: bool | None = False,
    ) -> bool:
        return run(
            Options(
                index_url=self.index_url,
                npm_registry=self.npm_registry,
                pkgs=list(pkgs),
                filenames=list(filenames),
                pre_release=pre_release,
                exclude_newer=None,
            )
        )

    def serve(self, request: httpx.Request) -> httpx.Response:
        for hook in self.hooks:
            hook(request)
        if (response := self.responses.get(str(request.url))) is not None:
            return response
        if request.url.host == "npm.example":
            if (versions := self.npm.get(unquote(request.url.path.removeprefix("/")))) is None:
                return httpx.Response(404)
            return httpx.Response(200, json={"versions": {key: {} for key in versions}})
        project = request.url.path.rstrip("/").rpartition("/")[2]
        if (versions := next((v for k, v in self.pypi.items() if canonicalize_name(k) == project), None)) is None:
            return httpx.Response(404)
        links = (
            f'<a data-requires-python="{escape(self.requires_python[file])}">{file}</a>'
            if (file := f"{project}-{version}.tar.gz") in self.requires_python
            else f"<a>{file}</a>"
            for version in versions
        )
        return httpx.Response(200, text="".join(links))


@pytest.fixture
def bump(
    capsys: pytest.CaptureFixture[str], httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Callable[..., str]:
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

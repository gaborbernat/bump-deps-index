from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from typing import TYPE_CHECKING, Literal
from urllib.parse import unquote

import httpx
import pytest
from packaging.utils import canonicalize_name

from bump_deps_index import Options, run

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from pytest_httpx import HTTPXMock


@pytest.fixture
def index(httpx_mock: HTTPXMock) -> FakeIndex:
    fake = FakeIndex()
    httpx_mock.add_callback(fake.serve, is_optional=True, is_reusable=True)
    return fake


@dataclass
class FakeIndex:
    pypi: dict[str, list[str]] = field(default_factory=dict)
    npm: dict[str, list[str]] = field(default_factory=dict)
    requires_python: dict[str, str] = field(default_factory=dict)
    index_url: str = "https://pypi.example/simple"
    npm_registry: str = "https://npm.example"

    def run(
        self,
        *filenames: Path,
        pkgs: Sequence[str] = (),
        pre_release: Literal["yes", "no", "file-default"] = "no",
    ) -> bool:
        return run(
            Options(
                index_url=self.index_url,
                npm_registry=self.npm_registry,
                pkgs=list(pkgs),
                filenames=list(filenames),
                pre_release=pre_release,
            )
        )

    def serve(self, request: httpx.Request) -> httpx.Response:
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

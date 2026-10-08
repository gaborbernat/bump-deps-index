from __future__ import annotations

from typing import TYPE_CHECKING, Final

import httpx
import pytest

from bump_deps_index import main

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_httpx import HTTPXMock

_PYPI: Final = "https://pypi.org/simple"
_NPM: Final = "https://registry.npmjs.org"


@pytest.mark.parametrize(
    ("workspace", "expected"),
    [
        pytest.param(({}, {}), (_PYPI, _NPM), id="defaults"),
        pytest.param(
            (
                {"PIP_INDEX_URL": "https://env.example/simple", "NPM_CONFIG_REGISTRY": "https://env.example/npm"},
                {"project/uv.toml": 'index-url = "https://uv.example/simple"', "project/.npmrc": "registry=https://x"},
            ),
            ("https://env.example/simple", "https://env.example/npm"),
            id="environment-wins",
        ),
        pytest.param(
            ({"UV_DEFAULT_INDEX": "https://uv-env.example/simple"}, {}),
            ("https://uv-env.example/simple", _NPM),
            id="uv-environment",
        ),
        pytest.param(
            (
                {},
                {
                    "uv.toml": '[[index]]\nurl = "https://other.example/simple"\n'
                    '[[index]]\nurl = "https://uv.example/simple"\ndefault = true',
                    "project/pyproject.toml": '[project]\nname = "demo"',
                    "~/.config/pip/pip.conf": "[global]\nindex-url = https://pip.example/simple",
                },
            ),
            ("https://uv.example/simple", _NPM),
            id="uv-default-index-in-parent-folder",
        ),
        pytest.param(
            ({}, {"project/pyproject.toml": '[tool.uv]\nindex-url = "https://uv.example/simple"'}),
            ("https://uv.example/simple", _NPM),
            id="uv-in-pyproject",
        ),
        pytest.param(
            (
                {},
                {
                    "project/uv.toml": "index-url = [",
                    "~/.config/pip/pip.conf": "[global]\nindex-url = https://pip.example/simple\n"
                    "[install]\nindex-url = https://install.example/simple",
                },
            ),
            ("https://install.example/simple", _NPM),
            id="pip-install-section-after-invalid-uv",
        ),
        pytest.param(
            (
                {"PIP_CONFIG_FILE": "{tmp}/custom.conf"},
                {
                    "custom.conf": "[global]\nindex-url = https://custom.example/simple",
                    "~/.config/pip/pip.conf": "[global]\nindex-url = https://pip.example/simple",
                },
            ),
            ("https://custom.example/simple", _NPM),
            id="pip-config-file",
        ),
        pytest.param(
            (
                {"XDG_CONFIG_HOME": "{tmp}/xdg"},
                {
                    "xdg/pip/pip.conf": "index-url = https://broken.example/simple",
                    "~/.pip/pip.conf": "[global]\nindex-url = https://legacy.example/simple",
                },
            ),
            ("https://legacy.example/simple", _NPM),
            id="pip-legacy-after-invalid-config",
        ),
        pytest.param(
            ({}, {"~/.config/uv/uv.toml": 'index-url = "https://uv-user.example/simple"'}),
            ("https://uv-user.example/simple", _NPM),
            id="uv-user-config",
        ),
        pytest.param(
            (
                {"APPDATA": "{tmp}/appdata"},
                {"appdata/uv/uv.toml": 'index-url = "https://uv-windows.example/simple"'},
            ),
            ("https://uv-windows.example/simple", _NPM),
            id="uv-windows-user-config",
        ),
        pytest.param(
            (
                {},
                {
                    "project/uv.toml": '[[index]]\nname = "no-url"\ndefault = true',
                    "pyproject.toml": "tool = 1",
                    "~/.config/pip/pip.conf": b"[global]\n# \xff\nindex-url = https://pip.example/simple",
                    "~/.config/uv/uv.toml": 'index = ["not-a-table"]',
                    "project/sub/.npmrc": b"registry=https://\xff.example",
                },
            ),
            (_PYPI, _NPM),
            id="malformed-files-ignored",
        ),
        pytest.param(
            (
                {"HOST": "npm.example"},
                {"project/sub/.npmrc": "# registry=https://comment.example\nregistry = https://${HOST}/npm/"},
            ),
            (_PYPI, "https://npm.example/npm/"),
            id="npmrc-in-project",
        ),
        pytest.param(
            (
                {},
                {"project/sub/.npmrc": "save-exact=true", "~/.npmrc": 'registry=https://a\nregistry="https://b"'},
            ),
            (_PYPI, "https://b"),
            id="npmrc-in-home-last-wins",
        ),
        pytest.param(
            (
                {"NPM_CONFIG_USERCONFIG": "{tmp}/npmrc"},
                {"npmrc": "registry=https://user.example", "~/.npmrc": "registry=https://home.example"},
            ),
            (_PYPI, "https://user.example"),
            id="npmrc-user-config-variable",
        ),
    ],
    indirect=["workspace"],
)
@pytest.mark.usefixtures("workspace")
def test_main_reads_index_settings(capsys: pytest.CaptureFixture[str], expected: tuple[str, str]) -> None:
    main(["a", "b@1"])

    assert capsys.readouterr().out.splitlines() == [
        f"Using Python index: {expected[0]}",
        f"Using JavaScript index: {expected[1]}",
        "a -> a>=1",
        "b@1 -> b@1.0.0",
    ]


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
        monkeypatch.setenv(name, value.format(tmp=tmp_path))
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

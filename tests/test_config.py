from __future__ import annotations

import os
from textwrap import dedent
from typing import TYPE_CHECKING, Final

import httpx
import pytest

from bump_deps_index import main

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from conftest import FakeIndex
    from pytest_httpx import HTTPXMock

_PYPI: Final[str] = "https://pypi.org/simple"
_NPM: Final[str] = "https://registry.npmjs.org"

pytestmark = pytest.mark.usefixtures("isolated_index_settings")


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
                {},
                {
                    "~/.pip/pip.conf": "[install]\nindex-url = https://install.example/simple",
                    "~/.config/pip/pip.conf": "[global]\nindex-url = https://pip.example/simple",
                },
            ),
            ("https://install.example/simple", _NPM),
            id="pip-install-section-across-files",
        ),
        pytest.param(
            (
                {"PIP_CONFIG_FILE": "{tmp}/custom.conf"},
                {
                    "custom.conf": "[global]\nindex-url = https://custom.example/simple",
                    "~/.config/pip/pip.conf": "[install]\nindex-url = https://pip.example/simple",
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
            (
                {},
                {
                    "~/.pip/pip.conf": "[global]\nindex-url = https://old.example/simple",
                    "~/.config/pip/pip.conf": "[global]\nindex-url = https://dash.example/simple\n"
                    "index_url = https://underscore.example/simple",
                },
            ),
            ("https://underscore.example/simple", _NPM),
            id="pip-underscore-key",
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
                {"PIP_CONFIG_FILE": "{devnull}", "npm_config_registry": "https://lower.example"},
                {"~/.config/pip/pip.conf": "[global]\nindex-url = https://pip.example/simple"},
            ),
            (_PYPI, "https://lower.example"),
            id="pip-config-disabled-and-lowercase-npm-variable",
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


def test_main_sends_npm_credentials_and_routes_scopes(
    httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TOKEN", "secret")
    (tmp_path / ".npmrc").write_text(
        "registry=https://npm.corp/api/\n"
        "@corp:registry=https://corp.example/npm/\n"
        "@other:registry=https://corp.example/npmx/  ; mirror for the other team\n"
        "//npm.corp/:_authToken=wrong\n"
        "//npm.corp/api/:_authToken=${TOKEN}\n"
        "//corp.example/npm/:_authToken=token\n"
        "//corp.example/npm/:_auth=dXNlcjpwYXNz\n"
        "//corp.example/np:_authToken=leak\n",
        encoding="utf-8",
    )
    versions = {"versions": {"1.0.0": {}}}
    httpx_mock.add_response(
        url="https://npm.corp/api/left-pad", match_headers={"Authorization": "Bearer secret"}, json=versions
    )
    httpx_mock.add_response(url="https://corp.example/npm/@corp%2Fx", json=versions)
    httpx_mock.add_response(url="https://corp.example/npmx/@other%2Fy", json=versions)

    main(["left-pad@0", "@corp/x@0", "@other/y@0"])

    assert {str(request.url): request.headers.get("Authorization") for request in httpx_mock.get_requests()} == {
        "https://npm.corp/api/left-pad": "Bearer secret",
        "https://corp.example/npm/@corp%2Fx": "Bearer token",
        "https://corp.example/npmx/@other%2Fy": None,
    }


def test_main_looks_up_uv_sources_on_their_index(
    capsys: pytest.CaptureFixture[str],
    httpx_mock: HTTPXMock,
    index: FakeIndex,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("UV_INDEX_CORP_MIRROR_USERNAME", "user")
    monkeypatch.setenv("UV_INDEX_CORP_MIRROR_PASSWORD", "p@ss")
    (tmp_path / "pyproject.toml").write_text(
        dedent(
            """
            [project]
            name = "demo"
            dependencies = ["internal", "pinned", "git-pkg", "workspace-pkg", "lost", "public"]
            [tool.uv]
            sources.internal = [{ index = "corp-mirror", marker = "sys_platform == 'linux'" }]
            sources.pinned = { index = "plain" }
            sources.git-pkg = { git = "https://github.com/a/git-pkg" }
            sources.workspace-pkg = [{ workspace = true }]
            sources.lost = { index = "missing" }
            [[tool.uv.index]]
            name = "corp-mirror"
            url = "https://corp.example/simple"
            default = true
            [[tool.uv.index]]
            name = "plain"
            url = "https://plain.example/simple"
            explicit = true
            """
        ).lstrip(),
        encoding="utf-8",
    )
    index.pypi.update(internal=["1"], pinned=["1"], public=["1"])

    main(["-f", "pyproject.toml"])

    assert (
        capsys.readouterr().out.splitlines(),
        {str(request.url): request.headers.get("Authorization") for request in httpx_mock.get_requests()},
    ) == (
        [
            "Using Python index: https://corp.example/simple",
            "internal -> internal>=1",
            "pinned -> pinned>=1",
            "public -> public>=1",
        ],
        {
            "https://user:p%40ss@corp.example/simple/internal/": "Basic dXNlcjpwQHNz",
            "https://plain.example/simple/pinned/": None,
            "https://user:p%40ss@corp.example/simple/public/": "Basic dXNlcjpwQHNz",
        },
    )


def test_main_reads_uv_sources_from_the_workspace_root(
    index: FakeIndex, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        dedent(
            """
            [tool.uv]
            workspace.members = ["member"]
            sources.internal = { index = "corp" }
            sources.pinned = { index = "corp" }
            [[tool.uv.index]]
            name = "corp"
            url = "https://corp.example/simple"
            """
        ).lstrip(),
        encoding="utf-8",
    )
    (member := tmp_path / "member").mkdir()
    (member / "pyproject.toml").write_text(
        dedent(
            """
            [project]
            name = "member"
            dependencies = ["internal", "pinned", "public"]
            [tool.uv]
            sources.pinned = { git = "https://github.com/a/pinned" }
            """
        ).lstrip(),
        encoding="utf-8",
    )
    monkeypatch.chdir(member)
    index.pypi.update(internal=["1"], public=["1"])

    main(["-i", "https://pypi.example/simple", "-f", "pyproject.toml"])

    assert (member / "pyproject.toml").read_text(encoding="utf-8") == dedent(
        """
        [project]
        name = "member"
        dependencies = ["internal>=1", "pinned", "public>=1"]
        [tool.uv]
        sources.pinned = { git = "https://github.com/a/pinned" }
        """
    ).lstrip()


def test_main_applies_uv_sources_where_uv_reads_them(
    httpx_mock: HTTPXMock, index: FakeIndex, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        dedent(
            """
            [project]
            name = "myproj"
            [tool.uv]
            sources.torch = { index = "corp" }
            [[tool.uv.index]]
            name = "corp"
            url = "https://corp.example/simple"
            """
        ).lstrip(),
        encoding="utf-8",
    )
    (tmp_path / "requirements.txt").write_text("torch>=1\n", encoding="utf-8")
    (tmp_path / "script.py").write_text(
        dedent(
            """
            # /// script
            # dependencies = ["torch>=1", "foo>=1", "myproj>=1"]
            # [tool.uv]
            # sources.foo = { git = "https://github.com/a/foo" }
            # index-url = "https://script.example/simple"
            # ///
            """
        ).lstrip(),
        encoding="utf-8",
    )
    index.pypi.update(torch=["2"], myproj=["2"])

    main(["-i", "https://pypi.example/simple", "-f", "requirements.txt", "script.py"])
    main(["-i", "https://pypi.example/simple", "torch"])

    assert sorted(str(request.url) for request in httpx_mock.get_requests()) == [
        "https://corp.example/simple/torch/",
        "https://pypi.example/simple/torch/",
        "https://script.example/simple/myproj/",
        "https://script.example/simple/torch/",
    ]


def _project_pages(pages: dict[str, str]) -> Callable[[httpx.Request], httpx.Response]:
    # serve one HTML page of file names per project URL, and not found for the rest
    def serve(request: httpx.Request) -> httpx.Response:
        url = request.url.copy_with(username=None, password=None)
        return httpx.Response(200, text=page) if (page := pages.get(str(url))) else httpx.Response(404)

    return serve


def test_main_merges_pip_extra_indexes(
    httpx_mock: HTTPXMock, isolated_index_settings: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PIP_EXTRA_INDEX_URL", "https://env.example/simple")
    pip_conf = isolated_index_settings / ".config" / "pip" / "pip.conf"
    pip_conf.parent.mkdir(parents=True)
    pip_conf.write_text("[global]\nextra-index-url =\n    https://conf.example/simple\n", encoding="utf-8")
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("--extra-index-url https://file.example/simple\nshared>=1\nconf>=1\nfile>=1\n", "utf-8")
    httpx_mock.add_callback(
        _project_pages({
            "https://pypi.example/simple/shared/": "<a>shared-2.tar.gz</a>",
            "https://env.example/simple/shared/": "<a>shared-5.tar.gz</a>",
            "https://conf.example/simple/conf/": "<a>conf-3.tar.gz</a>",
            "https://file.example/simple/file/": "<a>file-4.tar.gz</a>",
        }),
        is_reusable=True,
    )

    main(["-i", "https://pypi.example/simple", "-f", "requirements.txt"])

    assert requirements.read_text(encoding="utf-8").splitlines()[1:] == ["shared>=5", "conf>=3", "file>=4"]


def test_main_takes_a_package_from_the_first_uv_index_that_has_it(
    httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("UV_INDEX", "team=https://team.example/simple")
    monkeypatch.setenv("UV_INDEX_TEAM_PASSWORD", "tok")
    monkeypatch.setenv("UV_EXTRA_INDEX_URL", "https://extra.example/simple")
    (tmp_path / "pyproject.toml").write_text(
        dedent(
            """
            [project]
            name = "demo"
            dependencies = ["internal>=1", "public>=1", "pinned>=1", "team>=1"]
            [tool.uv]
            sources.pinned = { index = "pins" }
            [[tool.uv.index]]
            name = "corp"
            url = "https://corp.example/simple"
            [[tool.uv.index]]
            name = "pins"
            url = "https://pins.example/simple"
            explicit = true
            """
        ).lstrip(),
        encoding="utf-8",
    )
    (tmp_path / "requirements.txt").write_text("internal>=1\n", encoding="utf-8")
    (tmp_path / "script.py").write_text(
        "# /// script\n# dependencies = ['internal>=1']\n# [[tool.uv.index]]\n"
        "# url = 'https://script.example/simple'\n# ///\n",
        encoding="utf-8",
    )
    httpx_mock.add_callback(
        _project_pages({
            "https://team.example/simple/team/": "<a>team-6.tar.gz</a>",
            "https://extra.example/simple/public/": "<a>public-7.tar.gz</a>",
            "https://corp.example/simple/internal/": "<a>internal-3.tar.gz</a>",
            "https://script.example/simple/internal/": "<a>internal-5.tar.gz</a>",
            "https://pypi.example/simple/internal/": "<a>internal-99.tar.gz</a>",
            "https://pypi.example/simple/public/": "<a>public-2.tar.gz</a>",
            "https://pins.example/simple/pinned/": "<a>pinned-4.tar.gz</a>",
            "https://pypi.example/simple/pinned/": "<a>pinned-9.tar.gz</a>",
        }),
        is_reusable=True,
    )

    main(["-i", "https://pypi.example/simple", "-f", "pyproject.toml", "requirements.txt", "script.py"])

    assert (
        [(tmp_path / name).read_text(encoding="utf-8").splitlines()[line] for name, line in _UPDATED_LINES],
        {
            request.headers.get("Authorization")
            for request in httpx_mock.get_requests()
            if request.url.host == "team.example"
        },
    ) == (
        [
            'dependencies = ["internal>=3", "public>=7", "pinned>=4", "team>=6"]',
            "internal>=99",
            "# dependencies = ['internal>=5']",
        ],
        {"Basic OnRvaw=="},
    )


_UPDATED_LINES: Final[list[tuple[str, int]]] = [("pyproject.toml", 2), ("requirements.txt", 0), ("script.py", 1)]


def test_main_expands_npmrc_variables_and_sends_basic_credentials(
    httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MY_REG", "https://npm.example/")
    monkeypatch.delenv("UNSET", raising=False)
    (tmp_path / ".npmrc").write_text(
        "registry=${MY_REG?}\n"
        "@lit:registry=https://lit.example/${UNSET}\n"
        "@opt:registry=https://opt.example/${UNSET?}\n"
        "@tok:registry=https://token.example/\n"
        "@bad:registry=https://bad.example/\n"
        "//npm.example/:username=bob\n"
        "//npm.example/:_password=c2VjcmV0\n"
        "//token.example/:username=bob\n"
        "//token.example/:_password=c2VjcmV0\n"
        "//token.example/:_authToken=tok\n"
        "//bad.example/:username=bob\n"
        "//bad.example/:_password=/w==\n",
        encoding="utf-8",
    )
    httpx_mock.add_callback(lambda _: httpx.Response(200, json={"versions": {"1.0.0": {}}}), is_reusable=True)

    main(["a@1", "@lit/b@1", "@opt/c@1", "@tok/d@1", "@bad/e@1"])

    assert {str(request.url): request.headers.get("Authorization") for request in httpx_mock.get_requests()} == {
        "https://npm.example/a": "Basic Ym9iOnNlY3JldA==",
        "https://lit.example/$%7BUNSET%7D/@lit%2Fb": None,
        "https://opt.example/@opt%2Fc": None,
        "https://token.example/@tok%2Fd": "Bearer tok",
        "https://bad.example/@bad%2Fe": None,
    }

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import httpx
import pytest

from bump_deps_index import main

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from pathlib import Path

    from conftest import FakeIndex
    from pytest_httpx import HTTPXMock

pytestmark = pytest.mark.usefixtures("isolated_index_settings")


@pytest.fixture
def bump(
    capsys: pytest.CaptureFixture[str], httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Callable[..., str]:
    # look a spec up on the command line, from a folder whose project sets only `requires-python`
    monkeypatch.chdir(tmp_path)

    def run_main(
        spec: str,
        pages: Mapping[str, httpx.Response],
        *,
        pre_release: bool = False,
        requires_python: str | None = None,
    ) -> str:
        for url, response in pages.items():
            httpx_mock.add_callback(lambda _, served=response: served, url=url, is_optional=True)
        if requires_python is not None:
            (tmp_path / "pyproject.toml").write_text(f'[project]\nrequires-python = "{requires_python}"\n', "utf-8")
        main(["-i", "https://I.com", "-n", "https://N.com", "-p", "yes" if pre_release else "no", spec])
        return capsys.readouterr().out.splitlines()[-1].rpartition(" -> ")[2]

    return run_main


def test_update_python_parses_index_file_names(bump: Callable[..., str]) -> None:
    raw_html = """
    <html>
    <body>
    <a>A-B-1.0.4rc1.tar.bz2</a>
    <a>A-B-1.0.1.tar.bz2</a>
    <a>A-B-1.0.0.tar.gz</a>
    <a>A_B-1.0.3-py3-none-any.whl</a>
    <a>A-B-1.0.2.zip<span></a>
    <a>A-B.ok</a>
    <a>A-B-1.sdf.ok</a>
    <a/>
    </body></html>
    """

    assert bump("A-B", {"https://I.com/a-b/": httpx.Response(200, text=raw_html)}) == "A-B>=1.0.3"


def test_update_python_accepts_release_without_requires_python(bump: Callable[..., str]) -> None:

    assert (
        bump("A", {"https://I.com/a/": httpx.Response(200, text="<a>A-2.tar.gz</a>")}, requires_python=">=3.9")
        == "A>=2"
    )


@pytest.mark.parametrize(
    ("spec", "pre_release", "versions", "result"),
    [
        pytest.param("A", False, ["1.0.0"], "A>=1", id="no-ver"),
        pytest.param("A==1", False, ["1.1"], "A==1.1", id="eq-ver"),
        pytest.param("A===1", False, ["2"], "A===2", id="arbitrary-equality"),
        pytest.param("A<1", False, ["1.1"], "A<1", id="lt-ver"),
        pytest.param("A<2", False, ["1.5"], "A<2,>=1.5", id="preserve-upper-bound"),
        pytest.param("A (<2)", False, ["1.5"], "A (<2,>=1.5)", id="parenthesized-bound"),
        pytest.param("A <2 ; os_name=='nt'", False, ["1.5"], "A <2,>=1.5 ; os_name=='nt'", id="bound-marker"),
        pytest.param(
            "A[ b , a ] ;python_version<'3.99'",
            False,
            ["1"],
            "A[ b , a ]>=1 ;python_version<'3.99'",
            id="keeps-extras-and-marker-format",
        ),
        pytest.param(
            'A; python_version<"3.11"',
            False,
            ["1"],
            'A>=1; python_version<"3.11"',
            id="py-ver-marker",
        ),
        pytest.param(
            "A; python_version<'3.11'",
            False,
            ["1"],
            "A>=1; python_version<'3.11'",
            id="py-ver-marker-single-quote",
        ),
        pytest.param(
            'A[X]; python_version<"3.11"',
            False,
            ["1"],
            'A[X]>=1; python_version<"3.11"',
            id="py-ver-marker-extra",
        ),
        pytest.param(
            "A>=1",
            True,
            ["1.2.0b2", "1.2.0b1", "1.1.0", "0.1.0"],
            "A>=1.2.0b2",
            id="pre-release",
        ),
        pytest.param(
            "A",
            False,
            ["1.1.0+b2", "1.1.0+b1", "1.1.0", "0.1.0"],
            "A>=1.1",
            id="ignore-build-marker",
        ),
        pytest.param(
            "A @ https://example.com/a.whl",
            False,
            [],
            "A @ https://example.com/a.whl",
            id="direct-reference",
        ),
        pytest.param("A==2.0b1", False, ["1.9"], "A==2.0b1", id="eq-no-downgrade"),
        pytest.param("A==1.*", False, ["2.5"], "A==2.*", id="eq-wildcard"),
        pytest.param("A==1.4.*", False, ["2.5.1"], "A==2.5.*", id="eq-wildcard-depth"),
        pytest.param("A==1.4.*", False, ["3"], "A==3.0.*", id="eq-wildcard-pad"),
        pytest.param("A==1.4.*", False, ["1.4.9"], "A==1.4.*", id="eq-wildcard-same"),
        pytest.param("A==2.*", False, ["1.9"], "A==2.*", id="eq-wildcard-no-downgrade"),
        pytest.param("A==1!1.*", False, ["1!2.5"], "A==1!2.*", id="eq-wildcard-epoch"),
        pytest.param("A===2.0.0", False, ["3.0.0"], "A===3.0.0", id="arbitrary-equality-verbatim"),
        pytest.param("A===2.0.0", False, ["2.0.0"], "A===2.0.0", id="arbitrary-equality-same"),
        pytest.param("A===foo", False, ["1"], "A===1", id="arbitrary-equality-not-pep440"),
        pytest.param("A~=1.4", False, ["2.1", "1.9.3"], "A~=1.9", id="compatible-release"),
        pytest.param("A~=2.0", False, ["2.0.5"], "A~=2.0", id="compatible-release-same"),
        pytest.param("A~=1.4.2", False, ["1.4.7"], "A~=1.4.7", id="compatible-release-precision"),
        pytest.param("A~=1.4.2", False, ["1.5", "1.4.9"], "A~=1.4.9", id="compatible-release-cap"),
        pytest.param("A~=1.4", True, ["1.9b1"], "A~=1.9b1", id="compatible-release-pre"),
        pytest.param("A~=1!1.4", False, ["1!1.9.3"], "A~=1!1.9", id="compatible-release-epoch"),
        pytest.param("A >= 1.0", False, ["1.0"], "A >= 1.0", id="unchanged-keeps-format"),
        pytest.param("A >= 1.0 , <3", False, ["2.5"], "A >= 2.5 , <3", id="keeps-format"),
        pytest.param("A>=1.2,!=1.2.5,<3", False, ["1.9"], "A>=1.9,!=1.2.5,<3", id="keeps-order"),
        pytest.param("A>=1.2,<=1.2.5", False, ["1.2.4"], "A>=1.2.4,<=1.2.5", id="no-substring-match"),
        pytest.param("A==1.0,<3", False, ["3.0", "2.5"], "A==2.5,<3", id="eq-inside-upper-bound"),
        pytest.param("A==1.0,<2", False, ["2.1", "1.0"], "A==1.0,<2", id="eq-upper-bound-same"),
        pytest.param("A==1.*,!=2.*", False, ["2.1"], "A==1.*,!=2.*", id="eq-wildcard-excluded"),
        pytest.param("A==1.0+cpu", False, ["1.0+cu118", "1.0+cpu"], "A==1.0+cpu", id="eq-local"),
        pytest.param("A==1.0+cpu", False, ["2.0+cu118", "2.0+cpu"], "A==2+cpu", id="eq-local-newer"),
    ],
)
def test_update_python(
    spec: str, pre_release: bool, versions: list[str], result: str, bump: Callable[..., str]
) -> None:
    index = "".join(f"<a>A-{version}.tar.gz</a>" for version in versions)

    assert bump(spec, {"https://I.com/a/": httpx.Response(200, text=index)}, pre_release=pre_release) == result


@pytest.mark.parametrize(
    ("spec", "versions", "pre_release", "result"),
    [
        pytest.param("a@1", ["1.0.0", "2.0.0"], False, "a@2.0.0", id="versioned"),
        pytest.param("a@", ["2.0.0"], False, "a@2.0.0", id="bare"),
        pytest.param("a@", ["1.0.0", "1.1.0", "bad", "1.2.0-a.1"], False, "a@1.1.0", id="skip-invalid-and-pre"),
        pytest.param("a@", ["1.0.0-beta.2", "1.0.0-beta.11", "1.0.0-rc.1"], True, "a@1.0.0-rc.1", id="pre-rc"),
        pytest.param("a@", ["1.0.0-beta.2", "1.0.0-beta.11"], True, "a@1.0.0-beta.11", id="pre-numeric-order"),
        pytest.param("a@v1.0.0", ["1.0.0", "2.0.0"], False, "a@2.0.0", id="v-prefixed-pin"),
        pytest.param("a@^1.0.0", ["1.0.0", "1.2.0", "2.0.0"], False, "a@^1.2.0", id="caret-keeps-major"),
        pytest.param("a@^0.2.0", ["0.2.0", "0.2.5", "0.3.0"], False, "a@^0.2.5", id="caret-zero-major-keeps-minor"),
        pytest.param("a@^0.0.1", ["0.0.1", "0.0.2"], False, "a@^0.0.1", id="caret-zero-minor-keeps-patch"),
        pytest.param("a@~1.2.0", ["1.2.0", "1.2.3", "1.3.0"], False, "a@~1.2.3", id="tilde-keeps-minor"),
        pytest.param("a@>=1.0.0", ["1.0.0", "2.0.0"], False, "a@>=2.0.0", id="lower-bound"),
        pytest.param("a@^2.0.0", ["1.0.0"], False, "a@^2.0.0", id="no-release-in-range"),
        pytest.param("a@<2", ["1.0.0"], False, "a@<2", id="unsupported-operator"),
        pytest.param("a@^1.x", ["1.0.0"], False, "a@^1.x", id="unsupported-version"),
        pytest.param("a@latest", ["1.0.0"], False, "a@latest", id="dist-tag"),
        pytest.param("a@1.2", ["1.0.0", "2.0.0"], False, "a@2.0.0", id="partial-pin"),
        pytest.param("a@1 || 2", ["1.0.0", "3.0.0"], False, "a@1 || 2", id="union-range"),
        pytest.param("a@2.0.0-beta.1", ["1.9.0", "2.0.0-beta.1"], False, "a@2.0.0-beta.1", id="pin-no-downgrade"),
        pytest.param("a@3", ["2.0.0"], False, "a@3", id="partial-pin-no-downgrade"),
        pytest.param("a@1.0.0", ["1.1.0-beta"], False, "a@1.0.0", id="only-pre-releases"),
        pytest.param("a@1.x", ["1.0.0", "2.0.0"], False, "a@1.x", id="x-range"),
    ],
)
def test_update_js(spec: str, versions: list[str], pre_release: bool, result: str, bump: Callable[..., str]) -> None:

    assert (
        bump(
            spec,
            {"https://N.com/a": httpx.Response(200, json={"versions": {key: {} for key in versions}})},
            pre_release=pre_release,
        )
        == result
    )


@pytest.mark.parametrize(
    ("spec", "result"),
    [
        pytest.param("a@", "a@1.4.0", id="bare"),
        pytest.param("a@1.0.0", "a@1.4.0", id="pin"),
        pytest.param("a@^1.0.0", "a@^1.4.0", id="range"),
        pytest.param("a@^1.5.0", "a@^1.5.0", id="range-above-latest"),
        pytest.param("a@~1.0.0", "a@~1.0.0", id="range-below-latest"),
    ],
)
def test_update_js_prefers_latest_tag_inside_range(spec: str, result: str, bump: Callable[..., str]) -> None:
    versions = {key: {} for key in ("1.0.0", "1.4.0", "1.5.0", "2.0.0")}

    assert (
        bump(
            spec,
            {"https://N.com/a": httpx.Response(200, json={"dist-tags": {"latest": "1.4.0"}, "versions": versions})},
        )
        == result
    )


def test_update_python_skips_files_of_other_projects(bump: Callable[..., str]) -> None:
    files = "<a>foo-2.0.tar.gz</a><a>foo_bar-9.0.tar.gz</a><a>foo.bar-8.0-py3-none-any.whl</a><a>foo-bar-7.tar.bz2</a>"

    assert bump("foo>=1", {"https://I.com/foo/": httpx.Response(200, text=files)}) == "foo>=2"


def test_update_js_encodes_scoped_package(bump: Callable[..., str]) -> None:

    assert (
        bump(
            "@scope/package", {"https://N.com/@scope%2Fpackage": httpx.Response(200, json={"versions": {"1.0.0": {}}})}
        )
        == "@scope/package@1.0.0"
    )


def test_update_js_requests_abbreviated_metadata_and_skips_deprecated(
    httpx_mock: HTTPXMock, bump: Callable[..., str]
) -> None:
    httpx_mock.add_response(
        url="https://N.com/a",
        match_headers={"Accept": "application/vnd.npm.install-v1+json; q=1.0, application/json; q=0.8"},
        json={"versions": {"1.0.0": {}, "2.0.0": {"deprecated": "broken"}}},
    )

    assert bump("a@", {}) == "a@1.0.0"


def test_run_prints_index_once_without_credentials(
    capsys: pytest.CaptureFixture[str], index: FakeIndex, tmp_path: Path
) -> None:
    index.index_url = "https://user:secret@pypi.example:8443/simple"
    index.pypi.update(a=["1"], b=["2"])
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("a\nb\n")

    assert index.run(requirements)

    lines = capsys.readouterr().out.splitlines()
    assert (lines[0], sorted(lines[1:])) == (
        "Using Python index: https://pypi.example:8443/simple",
        ["a -> a>=1", "b -> b>=2"],
    )


@pytest.mark.parametrize(
    ("content_type", "body"),
    [
        pytest.param(
            "text/html",
            """
            <a>A-1.tar.gz</a>
            <a data-requires-python="&gt;=3.6.*">A-2.tar.gz</a>
            <a data-requires-python="&gt;=3.12">A-3.tar.gz</a>
            <a data-yanked="broken">A-4.tar.gz</a>
            """,
            id="html",
        ),
        pytest.param(
            "application/vnd.pypi.simple.v1+json",
            json.dumps({
                "meta": {"api-version": "1.1"},
                "name": "a",
                "files": [
                    {"filename": "a-1.tar.gz", "yanked": False},
                    {"filename": "a-2.tar.gz", "requires-python": ">=3.6.*"},
                    {"filename": "a-3.tar.gz", "requires-python": ">=3.12"},
                    {"filename": "a-4.tar.gz", "yanked": "broken"},
                ],
            }),
            id="json",
        ),
    ],
)
def test_update_python_filters_files(content_type: str, body: str, bump: Callable[..., str]) -> None:

    assert (
        bump(
            "A",
            {"https://I.com/a/": httpx.Response(200, headers={"Content-Type": content_type}, text=body)},
            requires_python=">=3.11",
        )
        == "A>=2"
    )


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({"versions": None}, id="null-versions"),
        pytest.param({"versions": ["1.0.0"]}, id="list-versions"),
        pytest.param(["1.0.0"], id="list-payload"),
    ],
)
def test_update_js_rejects_malformed_metadata(
    capsys: pytest.CaptureFixture[str], bump: Callable[..., str], payload: dict[str, list[str] | None] | list[str]
) -> None:

    with pytest.raises(SystemExit):
        bump("a@", {"https://N.com/a": httpx.Response(200, json=payload)})

    assert capsys.readouterr().err == "failed a@ with TypeError('https://n.com/a has no versions dict')\n"


def test_update_js_skips_malformed_version_metadata(bump: Callable[..., str]) -> None:

    assert (
        bump(
            "a@",
            {"https://N.com/a": httpx.Response(200, json={"versions": {"1.0.0": "x", "2.0.0": {"deprecated": "y"}}})},
        )
        == "a@1.0.0"
    )


def test_update_python_skips_malformed_json_files(bump: Callable[..., str]) -> None:

    assert (
        bump(
            "a",
            {
                "https://I.com/a/": httpx.Response(
                    200,
                    headers={"Content-Type": "application/vnd.pypi.simple.v1+json"},
                    json={"files": [{"filename": 5}, "a-3.tar.gz", {"filename": "a-2.tar.gz", "requires-python": 3}]},
                )
            },
        )
        == "a>=2"
    )


@pytest.mark.parametrize(
    ("extra_status", "raised"),
    [
        pytest.param(404, "Client error '404 Not Found' for url 'https://i.com/a/'", id="missing-everywhere"),
        pytest.param(500, "Server error '500 Internal Server Error' for url 'https://e.com/a/'", id="extra-fails"),
    ],
)
def test_update_python_reports_index_errors(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    bump: Callable[..., str],
    extra_status: int,
    raised: str,
) -> None:
    monkeypatch.setenv("PIP_EXTRA_INDEX_URL", "https://E.com")

    with pytest.raises(SystemExit):
        bump("A", {"https://I.com/a/": httpx.Response(404), "https://E.com/a/": httpx.Response(extra_status)})

    assert capsys.readouterr().err.startswith(f'failed A with HTTPStatusError("{raised}')

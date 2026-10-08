from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from httpx import Client
from packaging.version import Version

from bump_deps_index._spec import PkgType, UpdateConfig, redact_text, update

if TYPE_CHECKING:
    from pathlib import Path

    from conftest import FakeIndex
    from pytest_httpx import HTTPXMock


def _python(spec: str, *, pre_release: bool = False, python_version: Version | None = None) -> str:
    config = UpdateConfig(
        index_url="https://I.com", authorization=None, pre_release=pre_release, python_version=python_version
    )
    return update(Client(), spec, PkgType.PYTHON, config)


def _js(spec: str, *, pre_release: bool = False) -> str:
    config = UpdateConfig(index_url="https://N.com", authorization=None, pre_release=pre_release, python_version=None)
    return update(Client(), spec, PkgType.JS, config)


def test_update_python_parses_index_file_names(httpx_mock: HTTPXMock) -> None:
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
    httpx_mock.add_response(url="https://I.com/a-b/", text=raw_html)

    assert _python("A-B") == "A-B>=1.0.3"


def test_update_python_accepts_release_without_requires_python(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="https://I.com/a/", text="<a>A-2.tar.gz</a>")

    assert _python("A", python_version=Version("3.9")) == "A>=2"


@pytest.mark.parametrize(
    ("spec", "pre_release", "versions", "result"),
    [
        pytest.param("A", False, [Version("1.0.0")], "A>=1", id="no-ver"),
        pytest.param("A==1", False, [Version("1.1")], "A==1.1", id="eq-ver"),
        pytest.param("A===1", False, [Version("2")], "A===2", id="arbitrary-equality"),
        pytest.param("A<1", False, [Version("1.1")], "A<1", id="lt-ver"),
        pytest.param("A<2", False, [Version("1.5")], "A<2,>=1.5", id="preserve-upper-bound"),
        pytest.param("A (<2)", False, [Version("1.5")], "A (<2,>=1.5)", id="parenthesized-bound"),
        pytest.param("A <2 ; os_name=='nt'", False, [Version("1.5")], "A <2,>=1.5 ; os_name=='nt'", id="bound-marker"),
        pytest.param(
            "A[ b , a ] ;python_version<'3.99'",
            False,
            [Version("1")],
            "A[ b , a ]>=1 ;python_version<'3.99'",
            id="keeps-extras-and-marker-format",
        ),
        pytest.param(
            'A; python_version<"3.11"',
            False,
            [Version("1")],
            'A>=1; python_version<"3.11"',
            id="py-ver-marker",
        ),
        pytest.param(
            "A; python_version<'3.11'",
            False,
            [Version("1")],
            "A>=1; python_version<'3.11'",
            id="py-ver-marker-single-quote",
        ),
        pytest.param(
            'A[X]; python_version<"3.11"',
            False,
            [Version("1")],
            'A[X]>=1; python_version<"3.11"',
            id="py-ver-marker-extra",
        ),
        pytest.param(
            "A>=1",
            True,
            [Version("1.2.0b2"), Version("1.2.0b1"), Version("1.1.0"), Version("0.1.0")],
            "A>=1.2.0b2",
            id="pre-release",
        ),
        pytest.param(
            "A",
            False,
            [Version("1.1.0+b2"), Version("1.1.0+b1"), Version("1.1.0"), Version("0.1.0")],
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
        pytest.param("A==2.0b1", False, [Version("1.9")], "A==2.0b1", id="eq-no-downgrade"),
        pytest.param("A==1.*", False, [Version("2.5")], "A==2.*", id="eq-wildcard"),
        pytest.param("A==1.4.*", False, [Version("2.5.1")], "A==2.5.*", id="eq-wildcard-depth"),
        pytest.param("A==1.4.*", False, [Version("3")], "A==3.0.*", id="eq-wildcard-pad"),
        pytest.param("A==1.4.*", False, [Version("1.4.9")], "A==1.4.*", id="eq-wildcard-same"),
        pytest.param("A==2.*", False, [Version("1.9")], "A==2.*", id="eq-wildcard-no-downgrade"),
        pytest.param("A==1!1.*", False, [Version("1!2.5")], "A==1!2.*", id="eq-wildcard-epoch"),
        pytest.param("A===2.0.0", False, [Version("3.0.0")], "A===3.0.0", id="arbitrary-equality-verbatim"),
        pytest.param("A===2.0.0", False, [Version("2.0.0")], "A===2.0.0", id="arbitrary-equality-same"),
        pytest.param("A===foo", False, [Version("1")], "A===1", id="arbitrary-equality-not-pep440"),
        pytest.param("A~=1.4", False, [Version("2.1"), Version("1.9.3")], "A~=1.9", id="compatible-release"),
        pytest.param("A~=2.0", False, [Version("2.0.5")], "A~=2.0", id="compatible-release-same"),
        pytest.param("A~=1.4.2", False, [Version("1.4.7")], "A~=1.4.7", id="compatible-release-precision"),
        pytest.param("A~=1.4.2", False, [Version("1.5"), Version("1.4.9")], "A~=1.4.9", id="compatible-release-cap"),
        pytest.param("A~=1.4", True, [Version("1.9b1")], "A~=1.9b1", id="compatible-release-pre"),
        pytest.param("A~=1!1.4", False, [Version("1!1.9.3")], "A~=1!1.9", id="compatible-release-epoch"),
        pytest.param("A >= 1.0", False, [Version("1.0")], "A >= 1.0", id="unchanged-keeps-format"),
        pytest.param("A >= 1.0 , <3", False, [Version("2.5")], "A >= 2.5 , <3", id="keeps-format"),
        pytest.param("A>=1.2,!=1.2.5,<3", False, [Version("1.9")], "A>=1.9,!=1.2.5,<3", id="keeps-order"),
        pytest.param("A>=1.2,<=1.2.5", False, [Version("1.2.4")], "A>=1.2.4,<=1.2.5", id="no-substring-match"),
    ],
)
def test_update_python(
    httpx_mock: HTTPXMock,
    spec: str,
    pre_release: bool,
    versions: list[Version],
    result: str,
) -> None:
    index = "".join(f"<a>A-{version}.tar.gz</a>" for version in versions)
    httpx_mock.add_response(url="https://I.com/a/", text=index, is_optional=True)

    assert _python(spec, pre_release=pre_release) == result


@pytest.mark.parametrize(
    ("spec", "versions", "pre_release", "result"),
    [
        pytest.param("a@1", ["1.0.0", "2.0.0"], False, "a@2.0.0", id="versioned"),
        pytest.param("a", ["2.0.0"], False, "a@2.0.0", id="bare"),
        pytest.param("a", ["1.0.0", "1.1.0", "bad", "1.2.0-a.1"], False, "a@1.1.0", id="skip-invalid-and-pre"),
        pytest.param("a", ["1.0.0-beta.2", "1.0.0-beta.11", "1.0.0-rc.1"], True, "a@1.0.0-rc.1", id="pre-rc"),
        pytest.param("a", ["1.0.0-beta.2", "1.0.0-beta.11"], True, "a@1.0.0-beta.11", id="pre-numeric-order"),
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
        pytest.param("a@1.x", ["1.0.0", "2.0.0"], False, "a@1.x", id="x-range"),
    ],
)
def test_update_js(httpx_mock: HTTPXMock, spec: str, versions: list[str], pre_release: bool, result: str) -> None:
    httpx_mock.add_response(url="https://N.com/a", json={"versions": {key: {} for key in versions}})

    assert _js(spec, pre_release=pre_release) == result


def test_update_js_encodes_scoped_package(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="https://N.com/@scope%2Fpackage", json={"versions": {"1.0.0": {}}})

    assert _js("@scope/package") == "@scope/package@1.0.0"


def test_update_js_requests_abbreviated_metadata_and_skips_deprecated(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://N.com/a",
        match_headers={"Accept": "application/vnd.npm.install-v1+json; q=1.0, application/json; q=0.8"},
        json={"versions": {"1.0.0": {}, "2.0.0": {"deprecated": "broken"}}},
    )

    assert _js("a") == "a@1.0.0"


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
def test_update_python_filters_files(httpx_mock: HTTPXMock, content_type: str, body: str) -> None:
    httpx_mock.add_response(url="https://I.com/a/", headers={"Content-Type": content_type}, text=body)

    assert _python("A", python_version=Version("3.11")) == "A>=2"


def test_update_python_fetches_each_project_once_per_client(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="https://I.com/a/", text="<a>A-2.tar.gz</a>")
    client = Client()
    config = UpdateConfig(index_url="https://I.com", authorization=None, pre_release=False, python_version=None)

    results = [update(client, spec, PkgType.PYTHON, config) for spec in ("a", "A>=1")]

    assert (results, len(httpx_mock.get_requests())) == (["a>=2", "A>=2"], 1)


def test_redact_text() -> None:
    message = "for url 'https://user:s3cret@index.example/simple/a/' and http://token@npm.example/a"

    assert redact_text(message) == "for url 'https://index.example/simple/a/' and http://npm.example/a"

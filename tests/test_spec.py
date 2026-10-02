from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from httpx import Client
from packaging.version import Version

from bump_deps_index._spec import PkgType, UpdateConfig, get_js_pkgs, get_pkgs, redact_text, update

if TYPE_CHECKING:
    from pytest_httpx import HTTPXMock
    from pytest_mock import MockerFixture


def test_get_pkgs(capsys: pytest.CaptureFixture[str], httpx_mock: HTTPXMock) -> None:
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

    result = get_pkgs(Client(), "https://I.com", package="A-B", pre_release=False)

    assert result == [Version("1.0.3"), Version("1.0.2"), Version("1.0.1"), Version("1.0.0")]
    out, err = capsys.readouterr()
    assert not out
    assert not err


def test_update_python_accepts_release_without_requires_python(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="https://I.com/a/", text="<a>A-2.tar.gz</a>")

    updated = update(
        Client(),
        "A",
        PkgType.PYTHON,
        UpdateConfig(index_url="https://I.com", npm_registry="N", pre_release=False, python_version=Version("3.9")),
    )

    assert updated == "A>=2"


@pytest.mark.parametrize(
    ("spec", "pre_release", "versions", "result"),
    [
        pytest.param("A", False, [Version("1.0.0")], "A>=1", id="no-ver"),
        pytest.param("A==1", False, [Version("1.1")], "A==1.1", id="eq-ver"),
        pytest.param("A===1", False, [Version("2")], "A===2", id="arbitrary-equality"),
        pytest.param("A<1", False, [Version("1.1")], "A<1", id="lt-ver"),
        pytest.param("A<2", False, [Version("1.5")], "A<2,>=1.5", id="preserve-upper-bound"),
        pytest.param(
            'A; python_version<"3.11"',
            False,
            [Version("1")],
            'A>=1; python_version < "3.11"',
            id="py-ver-marker",
        ),
        pytest.param(
            "A; python_version<'3.11'",
            False,
            [Version("1")],
            "A>=1; python_version < '3.11'",
            id="py-ver-marker-single-quote",
        ),
        pytest.param(
            'A[X]; python_version<"3.11"',
            False,
            [Version("1")],
            'A[X]>=1; python_version < "3.11"',
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
        pytest.param("A==1.*", False, [Version("2")], "A==2", id="eq-wildcard"),
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

    updated = update(
        Client(),
        spec,
        PkgType.PYTHON,
        UpdateConfig(index_url="https://I.com", npm_registry="N", pre_release=pre_release, python_version=None),
    )

    assert updated == result


@pytest.mark.parametrize(
    ("spec", "result"),
    [
        pytest.param("A@1", "A@2.0.0", id="versioned"),
        pytest.param("A", "A@2.0.0", id="bare"),
    ],
)
def test_update_js(mocker: MockerFixture, spec: str, result: str) -> None:
    mocker.patch("bump_deps_index._spec.get_js_pkgs", return_value=["2.0.0"])

    updated = update(
        Client(),
        spec,
        PkgType.JS,
        UpdateConfig(index_url="I", npm_registry="N", pre_release=False, python_version=None),
    )

    assert updated == result


def test_get_js_pkgs(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(text='{"versions":{"1.0.0": {}, "1.1.0": {}, "bad": {}, "1.2.0-a.1": {}}}')
    result = get_js_pkgs(Client(), "https://N.com", "a", pre_release=False)
    assert result == ["1.1.0", "1.0.0"]


def test_get_js_pkgs_orders_semver_prereleases(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        text='{"versions":{"1.0.0-beta.2": {}, "1.0.0-beta.11": {}, "1.0.0-rc.1": {}, "1.0.0": {}}}'
    )

    result = get_js_pkgs(Client(), "https://N.com/", "a", pre_release=True)

    assert result == ["1.0.0", "1.0.0-rc.1", "1.0.0-beta.11", "1.0.0-beta.2"]


def test_get_js_pkgs_encodes_scoped_package(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="https://N.com/@scope%2Fpackage", text='{"versions":{"1.0.0": {}}}')

    result = get_js_pkgs(Client(), "https://N.com", "@scope/package", pre_release=False)

    assert result == ["1.0.0"]


def test_update_redacts_index_credentials_and_preserves_port(
    capsys: pytest.CaptureFixture[str], mocker: MockerFixture
) -> None:
    mocker.patch("bump_deps_index._spec.get_pkgs", return_value=[])

    update(
        Client(),
        "credential-test",
        PkgType.PYTHON,
        UpdateConfig(
            index_url="https://user:secret@index.example:8443/simple",
            npm_registry="N",
            pre_release=False,
            python_version=None,
        ),
    )

    assert capsys.readouterr().out == "Using Python index: https://index.example:8443/simple\n"


def test_get_js_pkgs_requests_abbreviated_metadata_and_skips_deprecated(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        match_headers={"Accept": "application/vnd.npm.install-v1+json; q=1.0, application/json; q=0.8"},
        text='{"versions":{"1.0.0": {}, "2.0.0": {"deprecated": "broken"}}}',
    )

    assert get_js_pkgs(Client(), "https://N.com", "a", pre_release=False) == ["1.0.0"]


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
def test_get_pkgs_filters_files(httpx_mock: HTTPXMock, content_type: str, body: str) -> None:
    httpx_mock.add_response(url="https://I.com/a/", headers={"Content-Type": content_type}, text=body)

    result = get_pkgs(Client(), "https://I.com", "a", pre_release=False, python_version=Version("3.11"))

    assert result == [Version("2"), Version("1")]


def test_get_pkgs_fetches_each_project_once_per_client(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="https://I.com/a/", text="<a>A-2.tar.gz</a>")
    client = Client()

    first = get_pkgs(client, "https://I.com", "a", pre_release=False)
    second = get_pkgs(client, "https://I.com", "A", pre_release=True)

    assert first == second == [Version("2")]
    assert len(httpx_mock.get_requests()) == 1


def test_redact_text() -> None:
    message = "for url 'https://user:s3cret@index.example/simple/a/' and http://token@npm.example/a"

    assert redact_text(message) == "for url 'https://index.example/simple/a/' and http://npm.example/a"

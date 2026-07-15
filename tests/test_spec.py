from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from httpx import Client
from packaging.version import Version

from bump_deps_index._spec import PkgType, UpdateConfig, get_js_pkgs, get_pkgs, update

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
    ],
)
def test_update_python(
    mocker: MockerFixture,
    spec: str,
    pre_release: bool,
    versions: list[Version],
    result: str,
) -> None:
    mocker.patch("bump_deps_index._spec.get_pkgs", return_value=versions)

    updated = update(
        Client(),
        spec,
        PkgType.PYTHON,
        UpdateConfig(index_url="I", npm_registry="N", pre_release=pre_release, python_version=None),
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

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from httpx import Client
from packaging.version import Version

from bump_deps_index._spec import PkgType, get_js_pkgs, get_pkgs, update

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
    <a>A-B-1.0.3.whl</a>
    <a>A-B-1.0.2.zip</a>
    <a>A-B.ok</a>
    <a>A-B-1.sdf.ok</a>
    <a/>
    </body></html>
    """
    httpx_mock.add_response(url="https://I.com/A-B/", text=raw_html)

    result = get_pkgs(Client(), "https://I.com", package="A-B", pre_release=False)

    assert result == [Version("1.0.3"), Version("1.0.2"), Version("1.0.1"), Version("1.0.0")]
    out, err = capsys.readouterr()
    assert not out
    assert not err


@pytest.mark.parametrize(
    ("spec", "pkg_type", "pre_release", "versions", "result"),
    [
        pytest.param("A", PkgType.PYTHON, False, [Version("1.0.0")], "A>=1", id="no-ver"),
        pytest.param("A==1", PkgType.PYTHON, False, [Version("1.1")], "A==1.1", id="eq-ver"),
        pytest.param("A<1", PkgType.PYTHON, False, [Version("1.1")], "A<1", id="lt-ver"),
        pytest.param(
            'A; python_version<"3.11"',
            PkgType.PYTHON,
            False,
            [Version("1")],
            'A>=1; python_version < "3.11"',
            id="py-ver-marker",
        ),
        pytest.param(
            "A; python_version<'3.11'",
            PkgType.PYTHON,
            False,
            [Version("1")],
            "A>=1; python_version < '3.11'",
            id="py-ver-marker-single-quote",
        ),
        pytest.param(
            'A[X]; python_version<"3.11"',
            PkgType.PYTHON,
            False,
            [Version("1")],
            'A[X]>=1; python_version < "3.11"',
            id="py-ver-marker-extra",
        ),
        pytest.param(
            "A",
            PkgType.PYTHON,
            True,
            [Version("1.2.0b2"), Version("1.2.0b1"), Version("1.1.0"), Version("0.1.0")],
            "A>=1.2.0b2",
            id="pre-release",
        ),
        pytest.param(
            "A",
            PkgType.PYTHON,
            False,
            [Version("1.1.0+b2"), Version("1.1.0+b1"), Version("1.1.0"), Version("0.1.0")],
            "A>=1.1",
            id="ignore-build-marker",
        ),
        pytest.param("A@1", PkgType.JS, False, [Version("2.0")], "A@2", id="js-ver"),
        pytest.param("A", PkgType.JS, False, [Version("2.0")], "A@2", id="js-bare"),
    ],
)
def test_update(  # noqa: PLR0913
    mocker: MockerFixture,
    spec: str,
    pkg_type: PkgType,
    pre_release: bool,
    versions: list[Version],
    result: str,
) -> None:
    if pkg_type is PkgType.PYTHON:
        mocker.patch("bump_deps_index._spec.get_pkgs", return_value=versions)
    else:
        mocker.patch("bump_deps_index._spec.get_js_pkgs", return_value=versions)
    res = update(Client(), "I", "N", spec, pkg_type, pre_release)
    assert res == result


def test_get_js_pkgs(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(text='{"versions":{"1.0": {}, "1.1": {}, "bad": {}, "1.2a1": {}}}')
    result = get_js_pkgs(Client(), "https://N.com", "a", pre_release=False)
    assert result == ["1.1", "1.0"]

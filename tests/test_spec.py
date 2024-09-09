from __future__ import annotations

from contextlib import contextmanager
from io import BytesIO
from typing import TYPE_CHECKING

import pytest
from packaging.version import Version

from bump_deps_index._spec import PkgType, get_js_pkgs, get_pkgs, update

if TYPE_CHECKING:
    from collections.abc import Iterator

    from pytest_mock import MockerFixture


def test_get_pkgs(mocker: MockerFixture, capsys: pytest.CaptureFixture[str]) -> None:
    @contextmanager
    def _read_url(url: str) -> Iterator[BytesIO]:
        assert url == "I/A-B"
        yield BytesIO(raw_html.encode())

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
    mocker.patch("bump_deps_index._spec.urlopen", side_effect=_read_url)

    result = get_pkgs("I", package="A-B", pre_release=False)

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
    res = update("I", "N", spec, pkg_type, pre_release)
    assert res == result


def test_get_js_pkgs(mocker: MockerFixture) -> None:
    url_open = mocker.patch("bump_deps_index._spec.urlopen")
    content = b'{"versions":{"1.0": {}, "1.1": {}, "bad": {}, "1.2a1": {}}}'
    url_open.return_value.__enter__.return_value = BytesIO(content)
    result = get_js_pkgs("N", "a", pre_release=False)
    assert result == ["1.1", "1.0"]

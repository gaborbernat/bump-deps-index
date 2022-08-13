from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from io import BytesIO

import pytest
from packaging.version import Version
from pytest_mock import MockerFixture

from bump_deps_index._spec import PkgType, get_js_pkgs, get_pkgs, update


def test_get_pkgs(mocker: MockerFixture, capsys: pytest.CaptureFixture[str]) -> None:
    @contextmanager
    def _read_url(url: str) -> Iterator[BytesIO]:
        assert url == "I/A-B"
        yield BytesIO(raw_html.encode("utf-8"))

    raw_html = """
    <html>
    <body>
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

    result = get_pkgs("I", package="A-B")

    assert result == [Version("1.0.3"), Version("1.0.2"), Version("1.0.1"), Version("1.0.0")]
    out, err = capsys.readouterr()
    assert not out
    assert not err


@pytest.mark.parametrize(
    ("spec", "pkg_type", "versions", "result"),
    [
        ("A", PkgType.PYTHON, [Version("1.0.0")], "A>=1"),
        ("A==1", PkgType.PYTHON, [Version("1.1")], "A==1.1"),
        ("A<1", PkgType.PYTHON, [Version("1.1")], "A<1"),
        ('A; python_version<"3.11"', PkgType.PYTHON, [Version("1")], 'A>=1; python_version < "3.11"'),
        ('A[X]; python_version<"3.11"', PkgType.PYTHON, [Version("1")], 'A[X]>=1; python_version < "3.11"'),
        ("A", PkgType.PYTHON, [Version("1.1.0+b2"), Version("1.1.0+b1"), Version("1.1.0"), Version("0.1.0")], "A>=1.1"),
        ("A@1", PkgType.JS, [Version("2.0")], "A@2"),
        ("A", PkgType.JS, [Version("2.0")], "A@2"),
    ],
)
def test_update(mocker: MockerFixture, spec: str, pkg_type: PkgType, versions: list[Version], result: str) -> None:
    if pkg_type is PkgType.PYTHON:
        mocker.patch("bump_deps_index._spec.get_pkgs", return_value=versions)
    else:
        mocker.patch("bump_deps_index._spec.get_js_pkgs", return_value=versions)
    res = update("I", "N", spec, pkg_type)
    assert res == result


def test_get_js_pkgs(mocker: MockerFixture) -> None:
    url_open = mocker.patch("bump_deps_index._spec.urlopen")
    url_open.return_value.__enter__.return_value = BytesIO(b'{"versions":{"1.0": {}, "1.1": {}}}')
    result = get_js_pkgs("N", "a")
    assert result == [Version("1.1"), Version("1.0")]

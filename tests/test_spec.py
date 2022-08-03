from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from io import BytesIO

import pytest
from packaging.version import Version
from pytest_mock import MockerFixture

from bump_deps_index._spec import get_pkgs, update


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
    ("spec", "versions", "result"),
    [
        ("A", [Version("1.0.0")], "A>=1"),
        ("A==1", [Version("1.1")], "A==1.1"),
        ("A<1", [Version("1.1")], "A<1"),
        ('A; python_version<"3.11"', [Version("1")], 'A>=1; python_version < "3.11"'),
        ('A[X]; python_version<"3.11"', [Version("1")], 'A[X]>=1; python_version < "3.11"'),
        ("A", [Version("1.1.0+b2"), Version("1.1.0+b1"), Version("1.1.0"), Version("0.1.0")], "A>=1.1"),
    ],
)
def test_update(mocker: MockerFixture, spec: str, versions: list[Version], result: str) -> None:
    mocker.patch("bump_deps_index._spec.get_pkgs", return_value=versions)
    res = update("I", spec)
    assert res == result

from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING

from conftest import index_args

from bump_deps_index import main

if TYPE_CHECKING:
    from pathlib import Path

    import pytest
    from pytest_httpx import HTTPXMock


def test_run_tox_ini(capsys: pytest.CaptureFixture[str], httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    httpx_mock.add_response(url="https://pypi.example/simple/a/", text="<a>a-1.tar.gz</a>")
    httpx_mock.add_response(url="https://pypi.example/simple/b/", text="<a>b-2.tar.gz</a><a>b-3.tar.gz</a>")
    httpx_mock.add_response(url="https://pypi.example/simple/c/", text="<a>c-3.tar.gz</a>")
    dest = tmp_path / "tox.ini"
    content = """
    [tox]
    requires =
        C
    [testenv]
    deps =
        -e .
        -r requirements.txt
        A
    [testenv:ok]
    deps =
        B==2
    [magic]
    deps = NO
    """
    dest.write_text(dedent(content).lstrip())
    main(index_args("-f", str(dest)))

    out, err = capsys.readouterr()
    assert (err, set(out.splitlines())) == (
        "",
        {
            "Using Python index: https://pypi.example/simple",
            "A -> A>=1",
            "B==2 -> B==3",
            "C -> C>=3",
        },
    )

    expected = """
    [tox]
    requires =
        C>=3
    [testenv]
    deps =
        -e .
        -r requirements.txt
        A>=1
    [testenv:ok]
    deps =
        B==3
    [magic]
    deps = NO
    """
    assert dest.read_text() == dedent(expected).lstrip()

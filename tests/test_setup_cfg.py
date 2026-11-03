from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING

from conftest import index_args

from bump_deps_index import main

if TYPE_CHECKING:
    from pathlib import Path

    import pytest
    from pytest_httpx import HTTPXMock


def test_run_setup_cfg(capsys: pytest.CaptureFixture[str], httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    httpx_mock.add_response(url="https://pypi.example/simple/a/", text="<a>a-1.tar.gz</a>")
    httpx_mock.add_response(url="https://pypi.example/simple/b/", text="<a>b-1.tar.gz</a>")
    httpx_mock.add_response(url="https://pypi.example/simple/c/", text="<a>c-3.tar.gz</a>")
    dest = tmp_path / "setup.cfg"
    content = """
    [options]
    install_requires =
        A
    [options.extras_require]
    testing =
        B
    type =
        C
    """
    dest.write_text(dedent(content).lstrip())
    main(index_args("-f", str(dest)))

    out, err = capsys.readouterr()
    assert (err, set(out.splitlines())) == (
        "",
        {
            "Using Python index: https://pypi.example/simple",
            "B -> B>=1",
            "A -> A>=1",
            "C -> C>=3",
        },
    )

    expected = """
    [options]
    install_requires =
        A>=1
    [options.extras_require]
    testing =
        B>=1
    type =
        C>=3
    """
    assert dest.read_text() == dedent(expected).lstrip()

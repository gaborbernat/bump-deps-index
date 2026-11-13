from __future__ import annotations

import time
from textwrap import dedent
from typing import TYPE_CHECKING

import pytest
from conftest import PYPI_FOO, index_args

from bump_deps_index import main

if TYPE_CHECKING:
    from pathlib import Path

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


@pytest.mark.parametrize(
    ("name", "content", "expected", "pages"),
    [
        pytest.param(
            "tox.ini",
            """
            [tox]
            requires = foo
            [testenv]
            deps = foo>=1  # why
            [testenv:url]
            deps =
                bar @ git+https://github.com/a/bar
                py311, !pypy: foo>=1
            """,
            """
            [tox]
            requires = foo>=2
            [testenv]
            deps = foo>=2  # why
            [testenv:url]
            deps =
                bar @ git+https://github.com/a/bar
                py311, !pypy: foo>=2
            """,
            PYPI_FOO,
            id="tox-ini-single-line-and-url",
        ),
        pytest.param(
            "tox.ini",
            """
            [testenv]
            deps: foo>=1
            [testenv:b]
            deps =
                # pinned: see issue
                foo>=1
            commands: foo>=1
            """,
            """
            [testenv]
            deps: foo>=2
            [testenv:b]
            deps =
                # pinned: see issue
                foo>=2
            commands: foo>=1
            """,
            PYPI_FOO,
            id="tox-ini-colon-delimiter",
        ),
        pytest.param(
            "tox.ini",
            """
            [tox] # main
            requires = foo>=1
            [testenv]
              deps = foo>=1
            [testenv:b]
            deps =
                foo>=1  # pinned
            """,
            """
            [tox] # main
            requires = foo>=2
            [testenv]
              deps = foo>=2
            [testenv:b]
            deps =
                foo>=2  # pinned
            """,
            PYPI_FOO,
            id="tox-ini-header-comment-indented-key-inline-comment",
        ),
        pytest.param(
            "tox.ini",
            "[DEFAULT]\ndeps = foo>=1\nrequires = foo>=1\n[tox]\n[testenv]\ncommands = x\n",
            "[DEFAULT]\ndeps = foo>=2\nrequires = foo>=2\n[tox]\n[testenv]\ncommands = x\n",
            PYPI_FOO,
            id="tox-ini-default-section",
        ),
        pytest.param(
            "tox.ini",
            """
            [testenv]
            deps =
                {py312,py311}: foo>=1
                {[base]deps}
            """,
            """
            [testenv]
            deps =
                {py312,py311}: foo>=2
                {[base]deps}
            """,
            PYPI_FOO,
            id="tox-ini-brace-factor",
        ),
        pytest.param(
            "tox.ini",
            """
            [testenv]
            deps =
                py311: foo
            commands = foo
            """,
            """
            [testenv]
            deps =
                py311: foo>=2
            commands = foo
            """,
            PYPI_FOO,
            id="tox-ini-preserves-commands-and-factors",
        ),
    ],
    indirect=["pages"],
)
@pytest.mark.usefixtures("pages")
def test_file_updates(tmp_path: Path, name: str, content: str, expected: str) -> None:
    dest = tmp_path / name
    dest.write_text(dedent(content).lstrip(), encoding="utf-8")

    main(index_args("-f", str(dest)))

    assert dest.read_text(encoding="utf-8") == dedent(expected).lstrip()


@pytest.mark.parametrize(
    ("name", "content", "expected", "pages"),
    [
        pytest.param(
            "tox.ini",
            f"[testenv]\ndeps =\n    {'!,' * 26}x\n    foo>=1\n",
            f"[testenv]\ndeps =\n    {'!,' * 26}x\n    foo>=2\n",
            PYPI_FOO,
            id="tox-ini-factor-like-commas",
        ),
    ],
    indirect=["pages"],
)
@pytest.mark.usefixtures("pages")
def test_pathological_line_parses_in_linear_time(tmp_path: Path, name: str, content: str, expected: str) -> None:
    dest = tmp_path / name
    dest.write_text(content, encoding="utf-8")
    start = time.perf_counter()

    main(index_args("-f", str(dest)))

    assert (dest.read_text(encoding="utf-8"), time.perf_counter() - start < 1) == (expected, True)

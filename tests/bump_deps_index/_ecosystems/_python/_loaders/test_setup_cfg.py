from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING

import pytest
from conftest import PYPI_FOO, index_args

from bump_deps_index import main

if TYPE_CHECKING:
    from pathlib import Path

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


@pytest.mark.parametrize(
    ("name", "content", "expected", "pages"),
    [
        pytest.param(
            "setup.cfg",
            """
            [options]
            install_requires = foo>=1
            [options.extras_require]
            test = foo
            """,
            """
            [options]
            install_requires = foo>=2
            [options.extras_require]
            test = foo>=2
            """,
            PYPI_FOO,
            id="setup-cfg-single-line",
        ),
        pytest.param(
            "setup.cfg",
            """
            [options]
            install_requires: foo>=1
            """,
            """
            [options]
            install_requires: foo>=2
            """,
            PYPI_FOO,
            id="setup-cfg-colon-delimiter",
        ),
        pytest.param(
            "setup.cfg",
            """
            [options] ; install settings
            install_requires =
                foo>=1
            """,
            """
            [options] ; install settings
            install_requires =
                foo>=2
            """,
            PYPI_FOO,
            id="setup-cfg-header-comment",
        ),
        pytest.param(
            "setup.cfg",
            "[DEFAULT]\ninstall_requires = foo>=1\ntest = foo>=1\n[options]\n[options.extras_require]\n",
            "[DEFAULT]\ninstall_requires = foo>=2\ntest = foo>=2\n[options]\n[options.extras_require]\n",
            PYPI_FOO,
            id="setup-cfg-default-section",
        ),
        pytest.param(
            "setup.cfg",
            """
            [options]
            install_requires =
                foo>=1  # http
            [options.extras_require]
            test = foo>=1 # tests
            """,
            """
            [options]
            install_requires =
                foo>=2  # http
            [options.extras_require]
            test = foo>=2 # tests
            """,
            PYPI_FOO,
            id="setup-cfg-inline-comment",
        ),
        pytest.param(
            "setup.cfg",
            """
            [options]
            packages = foo
            python_requires = >=3.11
            install_requires =
                foo
            """,
            """
            [options]
            packages = foo
            python_requires = >=3.11
            install_requires =
                foo>=2
            """,
            PYPI_FOO,
            id="setup-cfg-updates-only-requirement-values",
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

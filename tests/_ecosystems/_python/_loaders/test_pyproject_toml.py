from __future__ import annotations

import time
from textwrap import dedent
from typing import TYPE_CHECKING, Final

import pytest
from conftest import PYPI_FOO, index_args

from bump_deps_index import main

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_httpx import HTTPXMock


def test_run_pyproject_toml(capsys: pytest.CaptureFixture[str], httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    httpx_mock.add_response(url="https://pypi.example/simple/a/", text="<a>a-1.tar.gz</a>")
    httpx_mock.add_response(url="https://pypi.example/simple/b/", text="<a>b-2.tar.gz</a><a>b-3.tar.gz</a>")
    httpx_mock.add_response(url="https://pypi.example/simple/c/", text="<a>c-1.tar.gz</a>")
    httpx_mock.add_response(url="https://pypi.example/simple/d/", status_code=404)
    httpx_mock.add_response(url="https://pypi.example/simple/e/", text="<a>e-3.tar.gz</a>")
    httpx_mock.add_response(url="https://pypi.example/simple/f/", text="<a>f-4.tar.gz</a>")
    dest = tmp_path / "pyproject.toml"
    content = """
    [build-system]
    requires = ["A"]
    [project]
    dependencies = [ "B==2"]
    optional-dependencies.test = [ "C" ]
    optional-dependencies.docs = [ "D"]
    [dependency-groups]
    first = ["E"]
    second = ["F", {include-group = "first"}]
    """
    dest.write_text(dedent(content).lstrip())

    with pytest.raises(SystemExit, match=r"^1$"):
        main(index_args("-f", str(dest)))

    out, err = capsys.readouterr()
    assert err.startswith("failed to look up D, so it was not updated: HTTPStatusError(")
    assert set(out.splitlines()) == {
        "Using Python index: https://pypi.example/simple",
        "C -> C>=1",
        "F -> F>=4",
        "A -> A>=1",
        "E -> E>=3",
        "B==2 -> B==3",
    }

    expected = """
    [build-system]
    requires = ["A>=1"]
    [project]
    dependencies = [ "B==3"]
    optional-dependencies.test = [ "C>=1" ]
    optional-dependencies.docs = [ "D"]
    [dependency-groups]
    first = ["E>=3"]
    second = ["F>=4", {include-group = "first"}]
    """
    assert dest.read_text() == dedent(expected).lstrip()


@pytest.mark.parametrize(
    ("requires_python_line", "expected"),
    [
        pytest.param("", "A>=2", id="missing"),
        pytest.param('requires-python = ">=3.9"', "A>=0.9", id="inclusive-floor"),
        pytest.param('requires-python = ">3.9"', "A>=1", id="exclusive-floor"),
        pytest.param('requires-python = ">=3.9,!=3.9.*"', "A>=2", id="excluded-minor"),
        pytest.param('requires-python = ">=3.9,!=3.9"', "A>=1", id="excluded-release"),
        pytest.param('requires-python = ">3.9.1rc1"', "A>=1", id="exclusive-prerelease"),
        pytest.param('requires-python = ">=3.9,<3"', "A>=2", id="empty-range"),
    ],
)
def test_run_pyproject_toml_respects_requires_python(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    requires_python_line: str,
    expected: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    dest = tmp_path / "pyproject.toml"
    toml = f"""
    [project]
    name = "demo"
    {requires_python_line}
    dependencies = ["A"]
    """
    dest.write_text(dedent(toml).lstrip())
    httpx_mock.add_response(
        url="https://pypi.example/simple/a/",
        text="""
        <a data-requires-python="&gt;=3.10">A-2.tar.gz</a>
        <a data-requires-python="&gt;=3.10">A-1-py3-none-any.whl</a>
        <a data-requires-python="&gt;=3.9.1">A-1.tar.gz</a>
        <a data-requires-python="&gt;=3.9">A-0.9.tar.gz</a>
        """,
    )

    main(index_args("-f", str(dest)))

    assert dest.read_text() == dedent(toml).lstrip().replace('dependencies = ["A"]', f'dependencies = ["{expected}"]')


def test_run_pyproject_toml_multiline(
    capsys: pytest.CaptureFixture[str], httpx_mock: HTTPXMock, tmp_path: Path
) -> None:
    httpx_mock.add_response(url="https://pypi.example/simple/requests/", text="<a>requests-2.30.tar.gz</a>")
    httpx_mock.add_response(url="https://pypi.example/simple/httpx/", text="<a>httpx-0.28.tar.gz</a>")
    dest = tmp_path / "pyproject.toml"
    toml = """
    [project]
    dependencies = [
        "requests>=2.28",
        "httpx>=0.27",
    ]
    [tool.something]
    unrelated = ["should-not-change>=1.0"]
    """
    dest.write_text(dedent(toml).lstrip())

    main(index_args("-f", str(dest)))

    out, err = capsys.readouterr()
    assert (err, set(out.splitlines())) == (
        "",
        {
            "Using Python index: https://pypi.example/simple",
            "requests>=2.28 -> requests>=2.30",
            "httpx>=0.27 -> httpx>=0.28",
        },
    )
    assert dest.read_text() == dedent(toml).lstrip().replace("2.28", "2.30").replace("0.27", "0.28")


def test_run_pyproject_toml_accepts_prereleases_everywhere(tmp_path: Path, httpx_mock: HTTPXMock) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        dedent(
            """
            [build-system]
            requires = ["build-dep"]

            [project]
            name = "example"
            dependencies = ["runtime-dep"]

            [project.optional-dependencies]
            test = ["optional-dep"]

            [dependency-groups]
            dev = ["group-dep"]
            """
        ).lstrip(),
        encoding="utf-8",
    )
    for name in ("build-dep", "runtime-dep", "optional-dep", "group-dep"):
        httpx_mock.add_response(url=f"https://pypi.example/simple/{name}/", text=f"<a>{name}-2.0.0rc1.tar.gz</a>")

    main(["-i", "https://pypi.example/simple", "-p", "yes", "--no-exclude-newer", "-f", str(pyproject)])

    assert (
        pyproject.read_text(encoding="utf-8")
        == dedent(
            """
        [build-system]
        requires = ["build-dep>=2.0.0rc1"]

        [project]
        name = "example"
        dependencies = ["runtime-dep>=2.0.0rc1"]

        [project.optional-dependencies]
        test = ["optional-dep>=2.0.0rc1"]

        [dependency-groups]
        dev = ["group-dep>=2.0.0rc1"]
        """
        ).lstrip()
    )


@pytest.mark.parametrize(
    ("name", "content", "expected", "pages"),
    [
        pytest.param(
            "pyproject.toml",
            """
            [project]
            name = "demo"
            optional-dependencies = { test = ["foo>=1"] }
            """,
            """
            [project]
            name = "demo"
            optional-dependencies = { test = ["foo>=2"] }
            """,
            PYPI_FOO,
            id="pyproject-inline-table",
        ),
        pytest.param(
            "pyproject.toml",
            """
            [project]
            name = "my-pkg"
            dependencies = ["My_Pkg[x]>=1", "foo>=1"]
            """,
            """
            [project]
            name = "my-pkg"
            dependencies = ["My_Pkg[x]>=1", "foo>=2"]
            """,
            PYPI_FOO,
            id="pyproject-skips-own-non-canonical-name",
        ),
        pytest.param(
            "pyproject.toml",
            """
            [project]
            name = "demo"
            dependencies = [
              "foo>=1",  # see [docs
            ]
            [tool.other]
            pins = ["foo>=1"]
            """,
            """
            [project]
            name = "demo"
            dependencies = [
              "foo>=2",  # see [docs
            ]
            [tool.other]
            pins = ["foo>=1"]
            """,
            PYPI_FOO,
            id="pyproject-bracket-in-comment",
        ),
        pytest.param(
            "pyproject.toml",
            """
            [project]
            name = "demo"
            dependencies = ["  foo>=1 "]
            """,
            """
            [project]
            name = "demo"
            dependencies = ["  foo>=2 "]
            """,
            PYPI_FOO,
            id="pyproject-padded-spec",
        ),
        pytest.param(
            "pyproject.toml",
            """
            [project]
            name = "demo"
            dependencies = [
              "not \\"]\\" valid",
              "foo>=1",
            ]
            [tool.other]
            pins = ["foo>=1"]
            """,
            """
            [project]
            name = "demo"
            dependencies = [
              "not \\"]\\" valid",
              "foo>=2",
            ]
            [tool.other]
            pins = ["foo>=1"]
            """,
            PYPI_FOO,
            id="pyproject-bracket-in-string",
        ),
        pytest.param(
            "pyproject.toml",
            """
            [ project ]
            name = "demo"
            dependencies = ["foo>=1"]
            [ "project" . optional-dependencies ]
            test = ["foo>=1"]
            """,
            """
            [ project ]
            name = "demo"
            dependencies = ["foo>=2"]
            [ "project" . optional-dependencies ]
            test = ["foo>=2"]
            """,
            PYPI_FOO,
            id="pyproject-spaced-table-header",
        ),
        pytest.param(
            "pyproject.toml",
            """
            project.name = "demo"
            project.dependencies = ["foo>=1"]
            tool.other.pins = ["foo>=1"]
            """,
            """
            project.name = "demo"
            project.dependencies = ["foo>=2"]
            tool.other.pins = ["foo>=1"]
            """,
            PYPI_FOO,
            id="pyproject-top-level-dotted-key",
        ),
        pytest.param(
            "pyproject.toml",
            """
            [project]
            name = "demo"
            [tool.uv]
            dev-dependencies = ["foo>=1"]
            """,
            """
            [project]
            name = "demo"
            [tool.uv]
            dev-dependencies = ["foo>=2"]
            """,
            PYPI_FOO,
            id="pyproject-uv-dev-dependencies",
        ),
        pytest.param(
            "pyproject.toml",
            '''
            [project]
            name = "demo"
            readme.text = """
            dependencies = ["foo>=1"]
            """
            version = """1"""
            dependencies = ["foo>=1"]
            ''',
            '''
            [project]
            name = "demo"
            readme.text = """
            dependencies = ["foo>=1"]
            """
            version = """1"""
            dependencies = ["foo>=2"]
            ''',
            PYPI_FOO,
            id="pyproject-multi-line-string",
        ),
        pytest.param(
            "pyproject.toml",
            """
            # use \"\"\" for docstrings
            [tool.x]
            a = '''he said \"\"\"hi'''
            [project]
            name = "demo"
            dependencies = ["foo>=1"]  # was "foo>=1"
            """,
            """
            # use \"\"\" for docstrings
            [tool.x]
            a = '''he said \"\"\"hi'''
            [project]
            name = "demo"
            dependencies = ["foo>=2"]  # was "foo>=1"
            """,
            PYPI_FOO,
            id="pyproject-triple-quotes-in-comment-and-literal",
        ),
        pytest.param(
            "pyproject.toml",
            """
            [project]
            name = "demo"
            [tool.uv]
            conflicts = [
              [{ extra = "a" }, { extra = "b" }],
            ]
            dev-dependencies = ["foo>=1"]
            """,
            """
            [project]
            name = "demo"
            [tool.uv]
            conflicts = [
              [{ extra = "a" }, { extra = "b" }],
            ]
            dev-dependencies = ["foo>=2"]
            """,
            PYPI_FOO,
            id="pyproject-nested-array-before-dependencies",
        ),
        pytest.param(
            "pyproject.toml",
            """
            [project]
            name = "demo"
            dependencies = ['foo>=1', "foo>=1; os_name == \\"nt\\""]
            """,
            """
            [project]
            name = "demo"
            dependencies = ['foo>=2', "foo>=2; os_name == \\"nt\\""]
            """,
            PYPI_FOO,
            id="pyproject-literal-and-escaped-strings",
        ),
        pytest.param(
            "pyproject.toml",
            """
            [project]
            name = "demo"
            dependencies = "foo>=1"
            optional-dependencies = ["foo>=1"]
            """,
            """
            [project]
            name = "demo"
            dependencies = "foo>=1"
            optional-dependencies = ["foo>=1"]
            """,
            {},
            id="pyproject-wrong-types",
        ),
        pytest.param(
            "pyproject.toml",
            """
            [project]
            name = "demo"
            dependencies = [\"\"\"foo>=1\"\"\", '''
            foo>=1''', "\\u0066oo>=2"]
            optional-dependencies.x = "foo>=1"
            """,
            """
            [project]
            name = "demo"
            dependencies = [\"\"\"foo>=2\"\"\", '''
            foo>=2''', "\\u0066oo>=2"]
            optional-dependencies.x = "foo>=1"
            """,
            PYPI_FOO,
            id="pyproject-multi-line-strings-and-unchanged-escapes",
        ),
        pytest.param(
            "pyproject.toml",
            '[project]\nname = "demo"\ndependencies = ["\\nfoo>=1", """\\\n  foo>=1\\\n  """, """\\ffoo>=1"""]\n',
            '[project]\nname = "demo"\ndependencies = ["\\nfoo>=2", """foo>=2""", """\\u000cfoo>=2"""]\n',
            PYPI_FOO,
            id="pyproject-escapes-and-line-ending-backslash",
        ),
        pytest.param(
            "pyproject.toml",
            """
            [project]
            name = "example"

            [project.optional-dependencies]
            test = ["foo"]

            [tool.example]
            dependencies = ["foo"]
            """,
            """
            [project]
            name = "example"

            [project.optional-dependencies]
            test = ["foo>=2"]

            [tool.example]
            dependencies = ["foo"]
            """,
            PYPI_FOO,
            id="pyproject-updates-only-dependency-tables",
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


_COMMENT_LINES: Final[str] = "#\n" * 20_000


@pytest.mark.parametrize(
    ("name", "content", "expected", "pages"),
    [
        pytest.param(
            "pyproject.toml",
            f'[project]\nname = "demo"\ndependencies = [\n  "foo"{" " * 100_000},\n]\n',
            f'[project]\nname = "demo"\ndependencies = [\n  "foo>=2"{" " * 100_000},\n]\n',
            PYPI_FOO,
            id="pyproject-long-whitespace",
        ),
        pytest.param(
            "pyproject.toml",
            f'[project]\nname = "demo"\ndependencies = ["""foo\\\n>=1"""]\n{_COMMENT_LINES}',
            f'[project]\nname = "demo"\ndependencies = ["""foo>=2"""]\n{_COMMENT_LINES}',
            PYPI_FOO,
            id="joined-line-before-many-equal-lines",
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

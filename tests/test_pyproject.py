from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING

import pytest
from conftest import index_args

from bump_deps_index import main

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_httpx import HTTPXMock


def test_run_args(capsys: pytest.CaptureFixture[str], httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="https://pypi.example/simple/a/", text="<a>a-1.tar.gz</a>")
    httpx_mock.add_response(url="https://pypi.example/simple/b/", text="")
    httpx_mock.add_response(url="https://pypi.example/simple/c/", status_code=404)
    httpx_mock.add_response(url="https://npm.example/@scope%2Fpkg", json={"versions": {"1.0.0": {}, "2.0.0": {}}})
    httpx_mock.add_response(url="https://npm.example/pkg", json={"versions": {"2.0.0": {}}})

    with pytest.raises(SystemExit, match=r"^1$"):
        main(index_args(" A ", "B", "C", "@scope/pkg@1", "direct @ https://example.com/direct.whl", "pkg@1"))

    out, err = capsys.readouterr()
    assert err.startswith(
        "failed to look up C, so it was not updated: HTTPStatusError(\"Client error '404 Not Found' for url "
    )
    assert set(out.splitlines()) == {
        "Using Python index: https://pypi.example/simple",
        "Using JavaScript index: https://npm.example",
        "A -> A>=1",
        "B",
        "@scope/pkg@1 -> @scope/pkg@2.0.0",
        "direct @ https://example.com/direct.whl",
        "pkg@1 -> pkg@2.0.0",
    }


def test_run_args_without_pyproject_keeps_index_selection(
    capsys: pytest.CaptureFixture[str], httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    httpx_mock.add_response(
        url="https://pypi.example/simple/a/", text='<a data-requires-python="&gt;=4">a-2.tar.gz</a>'
    )

    main(index_args("A"))

    assert capsys.readouterr().out.splitlines() == ["Using Python index: https://pypi.example/simple", "A -> A>=2"]


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
    ("requires_python", "expected"),
    [
        pytest.param(None, "A>=2", id="missing"),
        pytest.param(">=3.9", "A>=0.9", id="inclusive-floor"),
        pytest.param(">3.9", "A>=1", id="exclusive-floor"),
        pytest.param(">=3.9,!=3.9.*", "A>=2", id="excluded-minor"),
        pytest.param(">=3.9,!=3.9", "A>=1", id="excluded-release"),
        pytest.param(">3.9.1rc1", "A>=1", id="exclusive-prerelease"),
        pytest.param(">=3.9,<3", "A>=2", id="empty-range"),
    ],
)
def test_run_pyproject_toml_respects_requires_python(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    requires_python: str | None,
    expected: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    dest = tmp_path / "pyproject.toml"
    requires_python_line = f'requires-python = "{requires_python}"' if requires_python is not None else ""
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


def test_run_reports_unparsable_pyproject_and_continues(
    capsys: pytest.CaptureFixture[str], httpx_mock: HTTPXMock, tmp_path: Path
) -> None:
    httpx_mock.add_response(url="https://pypi.example/simple/a/", text="<a>a-1.tar.gz</a>")
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[project\n")
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("A\n")
    with pytest.raises(SystemExit, match=r"^1$"):
        main(index_args("-f", str(pyproject), str(requirements)))

    error = "TOMLDecodeError(\"Expected ']' at the end of a table declaration (at line 1, column 9)\")"
    assert capsys.readouterr().err.splitlines() == [
        f"failed to read {pyproject}, so it was skipped: {error}",
        f"ignoring project metadata from {pyproject}, so its uv settings are not read: {error}",
    ]
    assert (pyproject.read_text(), requirements.read_text()) == ("[project\n", "A>=1\n")

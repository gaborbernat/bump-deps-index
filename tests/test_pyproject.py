from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING

import httpx
import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from conftest import FakeIndex


def test_run_args(capsys: pytest.CaptureFixture[str], index: FakeIndex) -> None:
    index.pypi.update(A=["1"], B=[])
    index.npm.update({"@scope/pkg": ["1.0.0", "2.0.0"], "pkg": ["2.0.0"]})

    assert not index.run(pkgs=[" A ", "B", "C", "@scope/pkg@1", "direct @ https://example.com/direct.whl", "pkg@1"])

    out, err = capsys.readouterr()
    assert err.startswith("failed C with HTTPStatusError(\"Client error '404 Not Found' for url ")
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
    capsys: pytest.CaptureFixture[str], index: FakeIndex, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    index.pypi["A"] = ["2"]
    index.requires_python["a-2.tar.gz"] = ">=4"

    assert index.run(pkgs=["A"])

    assert capsys.readouterr().out.splitlines() == ["Using Python index: https://pypi.example/simple", "A -> A>=2"]


def test_run_pyproject_toml(capsys: pytest.CaptureFixture[str], index: FakeIndex, tmp_path: Path) -> None:
    index.pypi.update(A=["1"], B=["2", "3"], C=["1"], E=["3"], F=["4"])
    dest = tmp_path / "pyproject.toml"
    toml = """
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
    dest.write_text(dedent(toml).lstrip())

    assert not index.run(dest)

    out, err = capsys.readouterr()
    assert err.startswith("failed D with HTTPStatusError(")
    assert set(out.splitlines()) == {
        "Using Python index: https://pypi.example/simple",
        "C -> C>=1",
        "F -> F>=4",
        "A -> A>=1",
        "E -> E>=3",
        "B==2 -> B==3",
    }

    toml = """
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
    assert dest.read_text() == dedent(toml).lstrip()


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
    index: FakeIndex,
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
    index.responses["https://pypi.example/simple/a/"] = httpx.Response(
        200,
        text="""
        <a data-requires-python="&gt;=3.10">A-2.tar.gz</a>
        <a data-requires-python="&gt;=3.10">A-1-py3-none-any.whl</a>
        <a data-requires-python="&gt;=3.9.1">A-1.tar.gz</a>
        <a data-requires-python="&gt;=3.9">A-0.9.tar.gz</a>
        """,
    )

    assert index.run(dest)

    assert dest.read_text() == dedent(toml).lstrip().replace('dependencies = ["A"]', f'dependencies = ["{expected}"]')


def test_run_pyproject_toml_multiline(capsys: pytest.CaptureFixture[str], index: FakeIndex, tmp_path: Path) -> None:
    index.pypi.update(requests=["2.30"], httpx=["0.28"])
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

    assert index.run(dest)

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


def test_run_pyproject_toml_accepts_prereleases_everywhere(tmp_path: Path, index: FakeIndex) -> None:
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
    index.pypi.update({key: ["2.0.0rc1"] for key in ("build-dep", "runtime-dep", "optional-dep", "group-dep")})

    assert index.run(pyproject, pre_release="yes")

    assert pyproject.read_text(encoding="utf-8").count(">=2.0.0rc1") == 4


def test_run_reports_unparsable_pyproject_and_continues(
    capsys: pytest.CaptureFixture[str], index: FakeIndex, tmp_path: Path
) -> None:
    index.pypi["A"] = ["1"]
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[project\n")
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("A\n")
    assert not index.run(pyproject, requirements)

    error = "TOMLDecodeError(\"Expected ']' at the end of a table declaration (at line 1, column 9)\")"
    assert capsys.readouterr().err.splitlines() == [
        f"failed to read {pyproject} with {error}",
        f"ignoring project metadata from {pyproject} due to {error}",
    ]
    assert (pyproject.read_text(), requirements.read_text()) == ("[project\n", "A>=1\n")

from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING

import pytest
from httpx import Client
from packaging.version import Version

from bump_deps_index import Options, run
from bump_deps_index._spec import PkgType, UpdateConfig

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_httpx import HTTPXMock
    from pytest_mock import MockerFixture


def test_run_args(capsys: pytest.CaptureFixture[str], mocker: MockerFixture) -> None:
    mapping = {
        "A": "A>=1",
        "B": "B",
        "@scope/pkg@1": "@scope/pkg@2.0.0",
        "direct @ https://example.com/direct.whl": "direct @ https://example.com/direct.whl",
        "pkg@1": "pkg@2.0.0",
    }
    update_spec = mocker.patch(
        "bump_deps_index._run.update_spec",
        side_effect=lambda _, spec, __, ___: mapping[spec],
    )

    successful = run(
        Options(
            index_url="https://pypi.org/simple",
            npm_registry="N",
            pkgs=[" A ", "B", "C", "@scope/pkg@1", "direct @ https://example.com/direct.whl", "pkg@1"],
            filenames=None,
            pre_release="no",
        ),
    )

    assert not successful
    out, err = capsys.readouterr()
    assert err == "failed C with KeyError('C')\n"
    assert set(out.splitlines()) == {
        "A -> A>=1",
        "B",
        "@scope/pkg@1 -> @scope/pkg@2.0.0",
        "direct @ https://example.com/direct.whl",
        "pkg@1 -> pkg@2.0.0",
    }

    found: set[tuple[str, PkgType]] = set()
    for called in update_spec.call_args_list:
        assert len(called.args) == 4
        assert isinstance(called.args[0], Client)
        found.add((called.args[1], called.args[2]))
        assert called.args[3] == UpdateConfig(
            index_url="https://pypi.org/simple",
            npm_registry="N",
            pre_release=False,
            python_version=Version("3.11"),
        )
        assert not called.kwargs
    assert found == {
        ("C", PkgType.PYTHON),
        ("B", PkgType.PYTHON),
        ("A", PkgType.PYTHON),
        ("@scope/pkg@1", PkgType.JS),
        ("direct @ https://example.com/direct.whl", PkgType.PYTHON),
        ("pkg@1", PkgType.JS),
    }


def test_run_args_without_pyproject_keeps_index_selection(
    capsys: pytest.CaptureFixture[str],
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    httpx_mock.add_response(
        url="https://I.com/a/",
        text='<a data-requires-python="&gt;=4">A-2.tar.gz</a>',
    )

    run(Options(index_url="https://I.com", npm_registry="", pkgs=["A"], filenames=None, pre_release="no"))

    assert "A -> A>=2" in capsys.readouterr().out.splitlines()


def test_run_pyproject_toml(capsys: pytest.CaptureFixture[str], mocker: MockerFixture, tmp_path: Path) -> None:
    mapping = {"A": "A>=1", "B==2": "B==1", "C": "C>=1", "E": "E>=3", "F": "F>=4"}
    mocker.patch(
        "bump_deps_index._run.update_spec",
        side_effect=lambda _, spec, __, ___: mapping[spec],
    )
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
    successful = run(
        Options(index_url="https://pypi.org/simple", npm_registry="", pkgs=[], filenames=[dest], pre_release="no")
    )

    assert not successful
    out, err = capsys.readouterr()
    assert err == "failed D with KeyError('D')\n"
    assert set(out.splitlines()) == {"C -> C>=1", "F -> F>=4", "A -> A>=1", "E -> E>=3", "B==2 -> B==1"}

    toml = """
    [build-system]
    requires = ["A>=1"]
    [project]
    dependencies = [ "B==1"]
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
        url="https://I.com/a/",
        text="""
        <a data-requires-python="&gt;=3.10">A-2.tar.gz</a>
        <a data-requires-python="&gt;=3.10">A-1-py3-none-any.whl</a>
        <a data-requires-python="&gt;=3.9.1">A-1.tar.gz</a>
        <a data-requires-python="&gt;=3.9">A-0.9.tar.gz</a>
        """,
    )

    run(Options(index_url="https://I.com", npm_registry="", pkgs=[], filenames=[dest], pre_release="no"))

    assert dest.read_text() == dedent(toml).lstrip().replace('dependencies = ["A"]', f'dependencies = ["{expected}"]')


def test_run_pyproject_toml_multiline(
    capsys: pytest.CaptureFixture[str], mocker: MockerFixture, tmp_path: Path
) -> None:
    mapping = {"requests>=2.28": "requests>=2.30", "httpx>=0.27": "httpx>=0.28"}
    mocker.patch(
        "bump_deps_index._run.update_spec",
        side_effect=lambda _, spec, __, ___: mapping[spec],
    )
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
    run(Options(index_url="https://pypi.org/simple", npm_registry="", pkgs=[], filenames=[dest], pre_release="no"))

    out, err = capsys.readouterr()
    assert not err
    assert set(out.splitlines()) == {"requests>=2.28 -> requests>=2.30", "httpx>=0.27 -> httpx>=0.28"}

    result = dest.read_text()
    assert "requests>=2.30" in result
    assert "httpx>=0.28" in result
    assert "should-not-change>=1.0" in result


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
    for package in ("build-dep", "runtime-dep", "optional-dep", "group-dep"):
        httpx_mock.add_response(
            url=f"https://index.example/simple/{package}/",
            text=f"<a>{package}-2.0.0rc1.tar.gz</a>",
        )

    successful = run(
        Options(
            index_url="https://index.example/simple",
            npm_registry="N",
            pkgs=[],
            filenames=[pyproject],
            pre_release="yes",
        )
    )

    assert successful
    assert pyproject.read_text(encoding="utf-8").count(">=2.0.0rc1") == 4

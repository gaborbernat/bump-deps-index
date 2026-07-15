from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING

import pytest

from bump_deps_index import Options, run

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


def test_tox_toml(capsys: pytest.CaptureFixture[str], mocker: MockerFixture, tmp_path: Path) -> None:
    mapping = {"A": "A>=1"}
    mocker.patch(
        "bump_deps_index._run.update_spec",
        side_effect=lambda _, spec, __, ___: mapping[spec],
    )
    dest = tmp_path / "tox.toml"
    toml = """
    requires = ["A"]
    """
    dest.write_text(dedent(toml).lstrip())
    run(Options(index_url="https://pypi.org/simple", npm_registry="", pkgs=[], filenames=[dest], pre_release="no"))

    out, err = capsys.readouterr()
    assert not err
    assert set(out.splitlines()) == {"A -> A>=1"}

    toml = """
    requires = ["A>=1"]
    """
    assert dest.read_text() == dedent(toml).lstrip()


def test_run_rejects_unsupported_file(tmp_path: Path) -> None:
    filename = tmp_path / "dependencies.json"
    filename.touch()

    with pytest.raises(NotImplementedError) as exception_info:
        run(Options(index_url="I", npm_registry="N", pkgs=[], filenames=[filename], pre_release="no"))

    assert str(exception_info.value) == f"we do not support {filename}"


def test_tox_toml_deps(capsys: pytest.CaptureFixture[str], mocker: MockerFixture, tmp_path: Path) -> None:
    mapping = {"A": "A>=1", "B": "B>=2", "C": "C>=3", "D": "D>=4"}
    mocker.patch(
        "bump_deps_index._run.update_spec",
        side_effect=lambda _, spec, __, ___: mapping[spec],
    )
    dest = tmp_path / "tox.toml"
    toml = """
    requires = ["A"]

    [env_run_base]
    deps = ["B"]

    [env.test]
    deps = ["-r requirements.txt", "C"]

    [env.no_deps]
    description = "no deps here"

    [ui]
    deps = ["D"]
    """
    dest.write_text(dedent(toml).lstrip())
    run(Options(index_url="https://pypi.org/simple", npm_registry="", pkgs=[], filenames=[dest], pre_release="no"))

    out, err = capsys.readouterr()
    assert not err
    assert set(out.splitlines()) == {"A -> A>=1", "B -> B>=2", "C -> C>=3", "D -> D>=4"}

    toml = """
    requires = ["A>=1"]

    [env_run_base]
    deps = ["B>=2"]

    [env.test]
    deps = ["-r requirements.txt", "C>=3"]

    [env.no_deps]
    description = "no deps here"

    [ui]
    deps = ["D>=4"]
    """
    assert dest.read_text() == dedent(toml).lstrip()


def test_tox_toml_substitutions(capsys: pytest.CaptureFixture[str], mocker: MockerFixture, tmp_path: Path) -> None:
    mapping = {n: f"{n}>=1" for n in ("alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel")}
    mocker.patch(
        "bump_deps_index._run.update_spec",
        side_effect=lambda _, spec, __, ___: mapping[spec],
    )
    dest = tmp_path / "tox.toml"
    toml = """
    requires = ["alpha"]

    [env_run_base]
    deps = [
      { replace = "if", condition = "true", then = ["bravo"], else = ["charlie"], extend = true },
      { replace = "posargs", default = ["delta"], extend = true },
      { replace = "env", name = "X", default = "echo" },
      { replace = "glob", pattern = "*.txt", default = ["foxtrot"], extend = true },
      { replace = "ref", of = ["env_run_base", "deps"] },
    ]

    [env_base.matrix]
    factors = [["py312", "py313"]]
    deps = [
      { replace = "if", condition = "true", then = [
        { replace = "posargs", default = ["golf"], extend = true },
      ], extend = true },
    ]

    [env.type]
    deps = ["hotel"]
    """
    dest.write_text(dedent(toml).lstrip())
    run(Options(index_url="https://pypi.org/simple", npm_registry="", pkgs=[], filenames=[dest], pre_release="no"))

    out, err = capsys.readouterr()
    assert not err
    assert set(out.splitlines()) == {f"{n} -> {n}>=1" for n in mapping}

    toml = """
    requires = ["alpha>=1"]

    [env_run_base]
    deps = [
      { replace = "if", condition = "true", then = ["bravo>=1"], else = ["charlie>=1"], extend = true },
      { replace = "posargs", default = ["delta>=1"], extend = true },
      { replace = "env", name = "X", default = "echo>=1" },
      { replace = "glob", pattern = "*.txt", default = ["foxtrot>=1"], extend = true },
      { replace = "ref", of = ["env_run_base", "deps"] },
    ]

    [env_base.matrix]
    factors = [["py312", "py313"]]
    deps = [
      { replace = "if", condition = "true", then = [
        { replace = "posargs", default = ["golf>=1"], extend = true },
      ], extend = true },
    ]

    [env.type]
    deps = ["hotel>=1"]
    """
    assert dest.read_text() == dedent(toml).lstrip()


def test_tox_toml_malformed_env_entry(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    dest = tmp_path / "tox.toml"
    toml = """
    [env]
    broken = "not-a-table"
    """
    dest.write_text(dedent(toml).lstrip())
    run(Options(index_url="https://pypi.org/simple", npm_registry="", pkgs=[], filenames=[dest], pre_release="no"))

    out, err = capsys.readouterr()
    assert not err
    assert not set(out.splitlines())
    assert dest.read_text() == dedent(toml).lstrip()


def test_tox_toml_multiline(capsys: pytest.CaptureFixture[str], mocker: MockerFixture, tmp_path: Path) -> None:
    mapping = {"pytest>=7.0": "pytest>=8.0", "coverage>=6.0": "coverage>=7.0"}
    mocker.patch(
        "bump_deps_index._run.update_spec",
        side_effect=lambda _, spec, __, ___: mapping[spec],
    )
    dest = tmp_path / "tox.toml"
    toml = """
    [env_run_base]
    deps = [
        "pytest>=7.0",
        "coverage>=6.0",
    ]
    """
    dest.write_text(dedent(toml).lstrip())
    run(Options(index_url="https://pypi.org/simple", npm_registry="", pkgs=[], filenames=[dest], pre_release="no"))

    out, err = capsys.readouterr()
    assert not err
    assert set(out.splitlines()) == {"pytest>=7.0 -> pytest>=8.0", "coverage>=6.0 -> coverage>=7.0"}

    result = dest.read_text()
    assert "pytest>=8.0" in result
    assert "coverage>=7.0" in result


def test_run_pyproject_toml_empty(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    dest = tmp_path / "tox.ini"
    dest.write_text("")
    run(Options(index_url="https://pypi.org/simple", npm_registry="", pkgs=[], filenames=[dest], pre_release="no"))

    out, err = capsys.readouterr()
    assert not err
    assert not set(out.splitlines())
    assert not dest.read_text()

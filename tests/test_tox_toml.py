from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from conftest import FakeIndex


def test_tox_toml(capsys: pytest.CaptureFixture[str], index: FakeIndex, tmp_path: Path) -> None:
    index.pypi.update({"A": ["1"]})
    dest = tmp_path / "tox.toml"
    toml = """
    requires = ["A"]
    """
    dest.write_text(dedent(toml).lstrip())
    assert index.run(dest)

    out, err = capsys.readouterr()
    assert not err
    assert set(out.splitlines()) == {"Using Python index: https://pypi.example/simple", "A -> A>=1"}

    toml = """
    requires = ["A>=1"]
    """
    assert dest.read_text() == dedent(toml).lstrip()


@pytest.mark.parametrize(
    ("name", "message"),
    [
        pytest.param("dependencies.json", "we do not support {}", id="unsupported"),
        pytest.param("tox.toml", "{} does not exist", id="missing"),
    ],
)
def test_run_rejects_file(
    capsys: pytest.CaptureFixture[str], index: FakeIndex, tmp_path: Path, name: str, message: str
) -> None:
    (tmp_path / "dependencies.json").touch()
    filename = tmp_path / name

    assert not index.run(filename)

    assert capsys.readouterr().err == f"{message.format(filename)}\n"


def test_tox_toml_deps(capsys: pytest.CaptureFixture[str], index: FakeIndex, tmp_path: Path) -> None:
    index.pypi.update({"A": ["1"], "B": ["2"], "C": ["3"], "D": ["4"]})
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
    assert index.run(dest)

    out, err = capsys.readouterr()
    assert not err
    assert set(out.splitlines()) == {
        "Using Python index: https://pypi.example/simple",
        "A -> A>=1",
        "B -> B>=2",
        "C -> C>=3",
        "D -> D>=4",
    }

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


def test_tox_toml_substitutions(capsys: pytest.CaptureFixture[str], index: FakeIndex, tmp_path: Path) -> None:
    names = ("alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel")
    index.pypi.update({key: ["1"] for key in names})
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
    assert index.run(dest)

    out, err = capsys.readouterr()
    assert not err
    assert set(out.splitlines()) == {
        "Using Python index: https://pypi.example/simple",
    } | {f"{n} -> {n}>=1" for n in names}

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


def test_tox_toml_malformed_env_entry(capsys: pytest.CaptureFixture[str], tmp_path: Path, index: FakeIndex) -> None:
    dest = tmp_path / "tox.toml"
    toml = """
    [env]
    broken = "not-a-table"
    """
    dest.write_text(dedent(toml).lstrip())
    assert index.run(dest)

    out, err = capsys.readouterr()
    assert not err
    assert not set(out.splitlines())
    assert dest.read_text() == dedent(toml).lstrip()


def test_tox_toml_multiline(capsys: pytest.CaptureFixture[str], index: FakeIndex, tmp_path: Path) -> None:
    index.pypi.update({"pytest": ["8.1"], "coverage": ["7.1"]})
    dest = tmp_path / "tox.toml"
    toml = """
    [env_run_base]
    deps = [
        "pytest>=7.0",
        "coverage>=6.0",
    ]
    """
    dest.write_text(dedent(toml).lstrip())
    assert index.run(dest)

    out, err = capsys.readouterr()
    assert not err
    assert set(out.splitlines()) == {
        "Using Python index: https://pypi.example/simple",
        "pytest>=7.0 -> pytest>=8.1",
        "coverage>=6.0 -> coverage>=7.1",
    }

    assert dest.read_text() == dedent(toml).lstrip().replace("7.0", "8.1").replace("6.0", "7.1")

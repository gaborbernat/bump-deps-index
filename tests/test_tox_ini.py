from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING

from bump_deps_index import Options, run

if TYPE_CHECKING:
    from pathlib import Path

    import pytest
    from pytest_mock import MockerFixture


def test_run_tox_ini(capsys: pytest.CaptureFixture[str], mocker: MockerFixture, tmp_path: Path) -> None:
    mapping = {"A": "A>=1", "B==2": "B==1", "C": "C>=3"}
    mocker.patch(
        "bump_deps_index._run.update_spec",
        side_effect=lambda _, spec, __, ___: mapping[spec],
    )
    dest = tmp_path / "tox.ini"
    tox_ini = """
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
    dest.write_text(dedent(tox_ini).lstrip())
    run(Options(index_url="https://pypi.org/simple", npm_registry="", pkgs=[], filenames=[dest], pre_release="no"))

    out, err = capsys.readouterr()
    assert not err
    assert set(out.splitlines()) == {"A -> A>=1", "B==2 -> B==1", "C -> C>=3"}

    tox_ini = """
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
        B==1
    [magic]
    deps = NO
    """
    assert dest.read_text() == dedent(tox_ini).lstrip()


def test_tox_ini_empty(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    dest = tmp_path / "tox.ini"
    dest.write_text("")
    run(Options(index_url="https://pypi.org/simple", npm_registry="", pkgs=[], filenames=[dest], pre_release="no"))

    out, err = capsys.readouterr()
    assert not err
    assert not set(out.splitlines())
    assert not dest.read_text()

from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    import pytest
    from conftest import FakeIndex


def test_run_tox_ini(capsys: pytest.CaptureFixture[str], index: FakeIndex, tmp_path: Path) -> None:
    index.pypi.update({"A": ["1"], "B": ["2", "3"], "C": ["3"]})
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
    assert index.run(dest)

    out, err = capsys.readouterr()
    assert not err
    assert set(out.splitlines()) == {
        "Using Python index: https://pypi.example/simple",
        "A -> A>=1",
        "B==2 -> B==3",
        "C -> C>=3",
    }

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
        B==3
    [magic]
    deps = NO
    """
    assert dest.read_text() == dedent(tox_ini).lstrip()


def test_tox_ini_empty(capsys: pytest.CaptureFixture[str], tmp_path: Path, index: FakeIndex) -> None:
    dest = tmp_path / "tox.ini"
    dest.write_text("")
    assert index.run(dest)

    out, err = capsys.readouterr()
    assert not err
    assert not set(out.splitlines())
    assert not dest.read_text()

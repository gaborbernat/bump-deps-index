from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING

from bump_deps_index import Options, run

if TYPE_CHECKING:
    from pathlib import Path

    import pytest
    from pytest_mock import MockerFixture


def test_run_setup_cfg(capsys: pytest.CaptureFixture[str], mocker: MockerFixture, tmp_path: Path) -> None:
    mapping = {"A": "A>=1", "B": "B==1", "C": "C>=3"}
    mocker.patch(
        "bump_deps_index._run.update_spec",
        side_effect=lambda _, spec, __, ___: mapping[spec],
    )
    dest = tmp_path / "setup.cfg"
    setup_cfg = """
    [options]
    install_requires =
        A
    [options.extras_require]
    testing =
        B
    type =
        C
    """
    dest.write_text(dedent(setup_cfg).lstrip())
    run(Options(index_url="https://pypi.org/simple", npm_registry="", pkgs=[], filenames=[dest], pre_release="no"))

    out, err = capsys.readouterr()
    assert not err
    assert set(out.splitlines()) == {"B -> B==1", "A -> A>=1", "C -> C>=3"}

    setup_cfg = """
    [options]
    install_requires =
        A>=1
    [options.extras_require]
    testing =
        B==1
    type =
        C>=3
    """
    assert dest.read_text() == dedent(setup_cfg).lstrip()


def test_run_setup_cfg_empty(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    dest = tmp_path / "setup.cfg"
    dest.write_text("")
    run(Options(index_url="https://pypi.org/simple", npm_registry="", pkgs=[], filenames=[dest], pre_release="no"))

    out, err = capsys.readouterr()
    assert not err
    assert not set(out.splitlines())
    assert not dest.read_text()

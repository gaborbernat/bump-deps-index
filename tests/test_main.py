from __future__ import annotations

import sys
from pathlib import Path
from subprocess import check_call
from typing import TYPE_CHECKING

import pytest

from bump_deps_index import main

if TYPE_CHECKING:
    from conftest import FakeIndex


def test_main(capfd: pytest.CaptureFixture[str]) -> None:
    check_call([sys.executable, "-m", "bump_deps_index", "-h"])
    out, _err = capfd.readouterr()
    assert out


def test_script(capfd: pytest.CaptureFixture[str]) -> None:
    check_call([Path(sys.executable).parent / "bump-deps-index", "-h"])
    out, _err = capfd.readouterr()
    assert out


def test_main_updates_packages(
    capsys: pytest.CaptureFixture[str], index: FakeIndex, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    index.pypi["A"] = ["1"]

    main(["-i", index.index_url, "A"])

    assert capsys.readouterr().out.splitlines() == ["Using Python index: https://pypi.example/simple", "A -> A>=1"]


def test_main_exits_on_failed_update(index: FakeIndex, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as error:
        main(["-i", index.index_url, "missing"])

    assert error.value.code == 1

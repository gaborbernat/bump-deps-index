from __future__ import annotations

import sys
from pathlib import Path
from subprocess import check_call
from typing import TYPE_CHECKING

import pytest

from bump_deps_index import main

if TYPE_CHECKING:
    from conftest import FakeIndex
    from pytest_httpx import HTTPXMock


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


def test_main_discovers_constraints_and_package_json(
    index: FakeIndex, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    index.pypi["a"] = ["1"]
    index.npm["b"] = ["1.0.0", "1.1.0"]
    for name in ("constraints.txt", "constraints-dev.txt", "dev-requirements.txt"):
        (tmp_path / name).write_text("a\n", encoding="utf-8")
    (tmp_path / "package.json").write_text('{"dependencies": {"b": "^1.0.0"}}', encoding="utf-8")

    main(["-i", index.index_url, "-n", index.npm_registry])

    assert [
        (tmp_path / name).read_text(encoding="utf-8")
        for name in ("constraints.txt", "constraints-dev.txt", "dev-requirements.txt", "package.json")
    ] == ["a>=1\n", "a>=1\n", "a\n", '{"dependencies": {"b": "^1.1.0"}}']


def test_main_reports_malformed_registry_response(
    capsys: pytest.CaptureFixture[str], httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    httpx_mock.add_response(url="https://npm.example/a", json={"versions": None})

    with pytest.raises(SystemExit) as error:
        main(["-n", "https://npm.example", "a@1"])

    assert (error.value.code, capsys.readouterr().err) == (
        1,
        "failed a@1 with TypeError('https://npm.example/a has no versions dict')\n",
    )

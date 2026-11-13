from __future__ import annotations

import sys
from pathlib import Path
from subprocess import check_call  # ruff: ignore[suspicious-subprocess-import] The test invokes only local entry points.
from typing import TYPE_CHECKING

import pytest

from bump_deps_index import main

if TYPE_CHECKING:
    from pytest_httpx import HTTPXMock


def test_main(capfd: pytest.CaptureFixture[str]) -> None:
    check_call([sys.executable, "-m", "bump_deps_index", "-h"])
    out, _err = capfd.readouterr()
    assert out.startswith("usage: bump-deps-index ")


def test_script(capfd: pytest.CaptureFixture[str]) -> None:
    check_call([Path(sys.executable).parent / "bump-deps-index", "-h"])  # ruff: ignore[subprocess-without-shell-equals-true] The command path is fixed.
    out, _err = capfd.readouterr()
    assert out.startswith("usage: bump-deps-index ")


@pytest.mark.usefixtures("work_dir")
def test_main_updates_packages(capsys: pytest.CaptureFixture[str], httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="https://pypi.example/simple/a/", text="<a>a-1.tar.gz</a>")

    main(["-i", "https://pypi.example/simple", "A"])

    assert capsys.readouterr().out.splitlines() == ["Using Python index: https://pypi.example/simple", "A -> A>=1"]


@pytest.mark.usefixtures("work_dir")
def test_main_exits_on_failed_update(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="https://pypi.example/simple/missing/", status_code=404)

    with pytest.raises(SystemExit) as error:
        main(["-i", "https://pypi.example/simple", "missing"])

    assert error.value.code == 1


def test_main_discovers_constraints_and_package_json(httpx_mock: HTTPXMock, work_dir: Path) -> None:
    httpx_mock.add_response(url="https://pypi.example/simple/a/", text="<a>a-1.tar.gz</a>")
    httpx_mock.add_response(url="https://npm.example/b", json={"versions": {"1.0.0": {}, "1.1.0": {}}})
    for name in ("constraints.txt", "constraints-dev.txt", "requirements_dev.txt", "dev-requirements.txt"):
        (work_dir / name).write_text("a\n", encoding="utf-8")
    (work_dir / "package.json").write_text('{"dependencies": {"b": "^1.0.0"}}', encoding="utf-8")

    main(["-i", "https://pypi.example/simple", "-n", "https://npm.example"])

    assert [
        (work_dir / name).read_text(encoding="utf-8")
        for name in (
            "constraints.txt",
            "constraints-dev.txt",
            "requirements_dev.txt",
            "dev-requirements.txt",
            "package.json",
        )
    ] == ["a>=1\n", "a>=1\n", "a>=1\n", "a\n", '{"dependencies": {"b": "^1.1.0"}}']


@pytest.mark.usefixtures("work_dir")
def test_main_reports_malformed_registry_response(capsys: pytest.CaptureFixture[str], httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="https://npm.example/a", json={"versions": None})

    with pytest.raises(SystemExit) as error:
        main(["-n", "https://npm.example", "a@1"])

    assert (error.value.code, capsys.readouterr().err) == (
        1,
        "failed to look up a@1, so it was not updated: TypeError('https://npm.example/a has no versions dict')\n",
    )

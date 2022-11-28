from __future__ import annotations

from itertools import product
from pathlib import Path

import pytest

from bump_deps_index._cli import Options, parse_cli


def test_cli_ok_default(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PIP_INDEX_URL", raising=False)
    monkeypatch.delenv("NPM_CONFIG_REGISTRY", raising=False)
    options = parse_cli([])

    assert isinstance(options, Options)
    assert options.__dict__ == {
        "index_url": "https://pypi.org/simple",
        "npm_registry": "https://registry.npmjs.org",
        "pkgs": [],
        "filenames": [],
        "pre_release": "file-default",
    }


def test_cli_override_existing_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "setup.cfg").write_text("")
    options = parse_cli(["-f", "pyproject.toml"])
    assert options.filenames == [Path("pyproject.toml")]


@pytest.mark.parametrize("files", product(["pyproject.toml", "tox.ini", ".pre-commit-config.yaml", "setup.cfg"]))
def test_cli_pickup_existing_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, files: list[str]) -> None:
    for file in files:
        (tmp_path / file).write_text("")
    (tmp_path / "decoy").write_text("")
    monkeypatch.chdir(tmp_path)
    options = parse_cli([])
    assert set(options.filenames) == {tmp_path / f for f in files}

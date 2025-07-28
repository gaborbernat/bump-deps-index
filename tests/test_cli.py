from __future__ import annotations

from itertools import chain, combinations
from pathlib import Path

import pytest

from bump_deps_index._cli import Options, parse_cli
from bump_deps_index._loaders import get_loaders


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


_filenames = [Path(i) for i in ("pyproject.toml", "tox.ini", ".pre-commit-config.yaml", "setup.cfg")]


@pytest.mark.parametrize(
    "files",
    [set(c) for c in chain.from_iterable(combinations(_filenames, r) for r in range(1, len(_filenames) + 1))],
    ids=[
        "+".join(f.name for f in sorted(c, key=lambda p: p.name))
        for c in chain.from_iterable(combinations(_filenames, r) for r in range(1, len(_filenames) + 1))
    ],
)
def test_cli_pickup_existing_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, files: set[Path]) -> None:
    get_loaders.cache_clear()
    for file in files:
        (tmp_path / file).write_text("")
    (tmp_path / "decoy").write_text("")
    monkeypatch.chdir(tmp_path)

    options = parse_cli([])

    assert set(options.filenames) == files

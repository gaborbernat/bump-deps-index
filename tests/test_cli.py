from __future__ import annotations

import pytest

from bump_deps_index._cli import Options, parse_cli


def test_cli_ok_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PIP_INDEX_URL", raising=False)
    options = parse_cli(["A", "B"])

    assert isinstance(options, Options)
    assert options.__dict__ == {
        "index_url": "https://pypi.org/simple",
        "pkgs": ["A", "B"],
        "filename": None,
    }

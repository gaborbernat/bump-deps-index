from __future__ import annotations


def test_version() -> None:
    from bump_deps_index import __version__

    assert __version__

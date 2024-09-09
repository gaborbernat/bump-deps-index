from __future__ import annotations


def test_version() -> None:
    from bump_deps_index import __version__  # noqa: PLC0415

    assert __version__

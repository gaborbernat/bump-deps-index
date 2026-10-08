from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    import pytest
    from conftest import FakeIndex


def test_run_setup_cfg(capsys: pytest.CaptureFixture[str], index: FakeIndex, tmp_path: Path) -> None:
    index.pypi.update({"A": ["1"], "B": ["1"], "C": ["3"]})
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
    assert index.run(dest)

    out, err = capsys.readouterr()
    assert (err, set(out.splitlines())) == (
        "",
        {
            "Using Python index: https://pypi.example/simple",
            "B -> B>=1",
            "A -> A>=1",
            "C -> C>=3",
        },
    )

    setup_cfg = """
    [options]
    install_requires =
        A>=1
    [options.extras_require]
    testing =
        B>=1
    type =
        C>=3
    """
    assert dest.read_text() == dedent(setup_cfg).lstrip()

"""Bump dependencies from an index server."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from ._cli import Options, parse_cli
from ._run import run
from .version import version

if TYPE_CHECKING:
    from collections.abc import Sequence

__version__: Final = version


def main(args: Sequence[str] | None = None) -> None:
    """Run the command-line interface."""
    opt = parse_cli(args)
    if not run(opt):
        raise SystemExit(1)


__all__ = [
    "Options",
    "__version__",
    "main",
    "run",
]

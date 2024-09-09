"""Bump dependencies from an index server."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._cli import Options, parse_cli
from ._run import run
from .version import version

if TYPE_CHECKING:
    from collections.abc import Sequence

#: semantic version of the package
__version__ = version


def main(args: Sequence[str] | None = None) -> None:
    """
    Run via CLI arguments.

    :param args: the CLI arguments
    """
    opt = parse_cli(args)
    run(opt)


__all__ = [
    "Options",
    "__version__",
    "main",
    "run",
]

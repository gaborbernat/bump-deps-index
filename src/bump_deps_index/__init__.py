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
    """
    Run the command-line interface.

    :param args: command-line arguments, or ``sys.argv[1:]`` when None.
    :raises SystemExit: with status 1 when a lookup fails or a file cannot be updated.
    """
    options = parse_cli(args)
    if not run(options):
        raise SystemExit(1)


__all__ = [
    "Options",
    "__version__",
    "main",
    "run",
]

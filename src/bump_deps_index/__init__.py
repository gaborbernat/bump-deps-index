from __future__ import annotations

from collections.abc import Sequence

from ._cli import Options, parse_cli
from ._run import run
from .version import version

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
    "__version__",
    "Options",
    "main",
    "run",
]

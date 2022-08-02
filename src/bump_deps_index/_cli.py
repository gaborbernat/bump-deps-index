from __future__ import annotations

import os
from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser, Namespace
from collections.abc import Sequence
from pathlib import Path

from bump_deps_index.version import version


class Options(Namespace):
    """Run options."""

    index_url: str
    """The PyPI Index URL to query for versions."""
    pkgs: list[str]
    """Package names to get latest version for."""
    filename: Path
    """
    The file to upload python package version from, can be one of:

    - ``pyproject.toml``
    - ``tox.ini``
    - ``.pre-commit-config.yaml``
    - ``setup.cfg``
    """


def parse_cli(args: Sequence[str] | None) -> Options:
    parser = _build_parser()
    res = Options()
    parser.parse_args(args, namespace=res)
    return res


def _build_parser() -> ArgumentParser:
    epilog = f"running {version} at {Path(__file__).parent}"
    parser = ArgumentParser(prog="bump-deps-index", formatter_class=_HelpFormatter, epilog=epilog)
    index_url, msg = os.environ.get("PIP_INDEX_URL", "https://pypi.org/simple"), "PyPI index URL to target"
    parser.add_argument("--index-url", "-i", dest="index_url", metavar="url", default=index_url, help=msg)
    source = parser.add_mutually_exclusive_group()
    source.required = True
    source.add_argument("pkgs", nargs="*", help="packages to inspect", default=[], metavar="pkg")
    valid = ["pyproject.toml", "tox.ini", ".pre-commit-config.yaml", "setup.cfg"]
    msg = f"update Python version within a file - can be one of {', '.join(valid)}"
    source.add_argument("--file", "-f", dest="filename", help=msg, type=Path)
    return parser


class _HelpFormatter(ArgumentDefaultsHelpFormatter):
    def __init__(self, prog: str) -> None:
        super().__init__(prog, max_help_position=35, width=190)


__all__ = [
    "parse_cli",
    "Options",
]

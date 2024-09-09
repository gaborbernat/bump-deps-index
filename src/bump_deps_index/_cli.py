from __future__ import annotations

import os
from argparse import ArgumentParser, Namespace, RawDescriptionHelpFormatter
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from bump_deps_index.version import version

if TYPE_CHECKING:
    from collections.abc import Sequence


class Options(Namespace):
    """Run options."""

    index_url: str
    """The PyPI Index URL to query for Python versions."""
    npm_registry: str
    """The NPM registry to query for JS versions."""
    pkgs: list[str]
    """Package names to get latest version for."""
    filenames: list[Path]
    """
    The file to upload python package version from, can be one of:

    - ``pyproject.toml``
    - ``tox.ini``
    - ``.pre-commit-config.yaml``
    - ``setup.cfg``
    """
    pre_release: Literal["yes", "no", "file-default"]
    """Accept pre-releases: yes, no or decide per file type"""


def parse_cli(args: Sequence[str] | None) -> Options:
    parser = _build_parser()
    res = Options()
    parser.parse_args(args, namespace=res)
    return res


def _build_parser() -> ArgumentParser:
    epilog = f"running {version} at {Path(__file__).parent}"
    parser = ArgumentParser(prog="bump-deps-index", formatter_class=_HelpFormatter, epilog=epilog)
    index_url = os.environ.get("PIP_INDEX_URL", "https://pypi.org/simple")
    msg = f"PyPI index URL to target (default: {index_url})"
    parser.add_argument("--index-url", "-i", dest="index_url", metavar="url", default=index_url, help=msg)
    npm_registry = os.environ.get("NPM_CONFIG_REGISTRY", "https://registry.npmjs.org")
    msg = f"NPM registry (default: {npm_registry})"
    parser.add_argument("--npm-registry", "-n", dest="npm_registry", metavar="url", default=npm_registry, help=msg)
    msg = "accept pre-release versions"
    parser.add_argument("-p", "--pre-release", choices=["yes", "no", "file-default"], default="file-default", help=msg)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("pkgs", nargs="*", help="packages to inspect", default=[], metavar="pkg")
    valid = ["pyproject.toml", "tox.ini", ".pre-commit-config.yaml", "setup.cfg"]
    cwd = Path().cwd()
    exist = [cwd / i for i in valid if (cwd / i).exists()]
    msg = f"update Python version within a file (default: [{', '.join(i.name for i in exist)}])"
    source.add_argument(
        "--file",
        "-f",
        dest="filenames",
        help=msg,
        default=exist,
        action="store",
        nargs="*",
        metavar="f",
        type=Path,
    )
    return parser


class _HelpFormatter(RawDescriptionHelpFormatter):
    def __init__(self, prog: str) -> None:
        super().__init__(prog, max_help_position=35, width=190)


__all__ = [
    "Options",
    "parse_cli",
]

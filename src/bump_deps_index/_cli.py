from __future__ import annotations

import os
from argparse import ArgumentParser, Namespace, RawDescriptionHelpFormatter
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from bump_deps_index._loaders import get_loaders
from bump_deps_index._spec import redact_url
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
    Files to update, each one of:

    - ``pyproject.toml``
    - ``tox.toml``
    - ``tox.ini``
    - ``setup.cfg``
    - ``.pre-commit-config.yaml``
    - ``requirements*.txt`` and ``requirements*.in``
    - Python scripts with PEP 723 inline metadata
    """
    pre_release: Literal["yes", "no", "file-default"]
    """Accept pre-releases: yes, no or decide per file type"""


def parse_cli(args: Sequence[str] | None) -> Options:
    res = Options()
    _build_parser().parse_args(args, namespace=res)
    if res.filenames is None:  # discover after parsing to avoid reading local scripts when you pass packages
        found = () if res.pkgs else set(chain.from_iterable(loader.files for loader in get_loaders()))
        res.filenames = sorted(file.relative_to(Path.cwd()) for file in found)
    return res


def _build_parser() -> ArgumentParser:
    epilog = f"running {version} at {Path(__file__).parent}"
    parser = ArgumentParser(prog="bump-deps-index", formatter_class=_HelpFormatter, epilog=epilog)
    index_url = os.environ.get("PIP_INDEX_URL", "https://pypi.org/simple")
    msg = f"PyPI index URL to target (default: {redact_url(index_url)})"
    parser.add_argument("--index-url", "-i", dest="index_url", metavar="url", default=index_url, help=msg)
    npm_registry = os.environ.get("NPM_CONFIG_REGISTRY", "https://registry.npmjs.org")
    msg = f"NPM registry (default: {redact_url(npm_registry)})"
    parser.add_argument("--npm-registry", "-n", dest="npm_registry", metavar="url", default=npm_registry, help=msg)
    msg = "accept pre-release versions"
    parser.add_argument("-p", "--pre-release", choices=["yes", "no", "file-default"], default="file-default", help=msg)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("pkgs", nargs="*", help="packages to inspect", default=[], metavar="pkg")
    msg = "files to update (default: supported files in the working directory)"
    source.add_argument(
        "--file",
        "-f",
        dest="filenames",
        help=msg,
        default=None,
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

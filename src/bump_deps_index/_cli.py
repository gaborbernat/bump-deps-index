from __future__ import annotations

from argparse import SUPPRESS, ArgumentParser, ArgumentTypeError, Namespace, RawDescriptionHelpFormatter
from datetime import UTC, datetime
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING

from bump_deps_index._config import npm_registry, python_exclude_newer, python_index_url
from bump_deps_index._cutoff import parse_exclude_newer
from bump_deps_index._loaders import get_loaders
from bump_deps_index._redact import redact_url
from bump_deps_index.version import version

if TYPE_CHECKING:
    from collections.abc import Sequence


class Options(Namespace):
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
    - ``package.json``
    - ``.pre-commit-config.yaml``
    - requirements and constraints files, ending in ``.txt`` or ``.in``
    - Python scripts with PEP 723 inline metadata
    """
    pre_release: bool | None
    """Accept pre-releases: yes, no or decide per file type"""
    exclude_newer: datetime | None
    """Only candidates uploaded before this instant; None accepts every release"""


def parse_cli(args: Sequence[str] | None) -> Options:
    options = Options()
    _build_parser().parse_args(args, namespace=options)
    if options.filenames is None:  # discover after parsing to avoid reading local scripts when you pass packages
        found = () if options.pkgs else set(chain.from_iterable(loader.files for loader in get_loaders()))
        options.filenames = sorted(file.relative_to(Path.cwd()) for file in found)
    return options


def _build_parser() -> ArgumentParser:
    epilog = f"running {version} at {Path(__file__).parent}"
    parser = ArgumentParser(prog="bump-deps-index", formatter_class=_HelpFormatter, epilog=epilog)
    index_url = python_index_url()
    index_help = f"PyPI index URL to target (default: {redact_url(index_url)})"
    parser.add_argument("--index-url", "-i", dest="index_url", metavar="url", default=index_url, help=index_help)
    registry_help = f"NPM registry (default: {redact_url(registry := npm_registry())})"
    parser.add_argument(
        "--npm-registry", "-n", dest="npm_registry", metavar="url", default=registry, help=registry_help
    )
    pre_release_help = (
        "accept pre-release versions; file-default accepts them in .pre-commit-config.yaml and refuses them elsewhere"
    )
    parser.add_argument(
        "-p",
        "--pre-release",
        type=_pre_release_argument,
        metavar="{yes,no,file-default}",
        default="file-default",
        help=pre_release_help,
    )
    cutoff_help = (
        "only use releases uploaded before this cutoff, a timestamp or a duration such as P7D "
        "(default: from pip and uv settings)"
    )
    cutoff_flags = parser.add_mutually_exclusive_group()
    cutoff_flags.add_argument(
        "--exclude-newer",
        dest="exclude_newer",
        metavar="cutoff",
        default=python_exclude_newer(),
        type=_cutoff_argument,
        help=cutoff_help,
    )
    # SUPPRESS keeps the flag out of the defaults, so the mutual exclusion check sees it when it is given
    cutoff_flags.add_argument(
        "--no-exclude-newer",
        dest="exclude_newer",
        action="store_const",
        const=None,
        default=SUPPRESS,
        help="ignore every cutoff, including the one from the environment and config files; overrides --exclude-newer",
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument("pkgs", nargs="*", help="packages to inspect", default=[], metavar="pkg")
    source.add_argument(
        "--file",
        "-f",
        dest="filenames",
        help="files to update (default: supported files in the working directory)",
        default=None,
        action="store",
        nargs="*",
        metavar="f",
        type=Path,
    )
    return parser


def _cutoff_argument(value: str) -> datetime:
    try:
        return parse_exclude_newer(value, datetime.now(UTC))
    except (OverflowError, ValueError) as exc:  # a duration too long for a datetime is as invalid as a malformed one
        raise ArgumentTypeError(str(exc)) from exc


def _pre_release_argument(value: str) -> bool | None:
    choices = {"yes": True, "no": False, "file-default": None}
    if value not in choices:  # the message matches the one argparse gives for a `choices` mismatch
        msg = f"{value!r} is not a valid choice: use yes, no or file-default"
        raise ArgumentTypeError(msg)
    return choices[value]


class _HelpFormatter(RawDescriptionHelpFormatter):
    def __init__(self, prog: str) -> None:
        super().__init__(prog, max_help_position=35, width=190)


__all__ = [
    "Options",
    "parse_cli",
]

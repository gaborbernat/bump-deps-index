from __future__ import annotations

from argparse import SUPPRESS, ArgumentParser, ArgumentTypeError, Namespace, RawDescriptionHelpFormatter
from datetime import UTC, datetime
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from bump_deps_index._config import npm_registry, python_exclude_newer, python_index_url
from bump_deps_index._cutoff import parse_exclude_newer
from bump_deps_index._loaders import get_loaders
from bump_deps_index._redact import redact_url
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
    - ``package.json``
    - ``.pre-commit-config.yaml``
    - requirements and constraints files, ending in ``.txt`` or ``.in``
    - Python scripts with PEP 723 inline metadata
    """
    pre_release: Literal["yes", "no", "file-default"]
    """Accept pre-releases: yes, no or decide per file type"""
    exclude_newer: datetime | None
    """Only candidates uploaded before this instant; None accepts every release"""


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
    index_url = python_index_url()
    msg = f"PyPI index URL to target (default: {redact_url(index_url)})"
    parser.add_argument("--index-url", "-i", dest="index_url", metavar="url", default=index_url, help=msg)
    msg = f"NPM registry (default: {redact_url(registry := npm_registry())})"
    parser.add_argument("--npm-registry", "-n", dest="npm_registry", metavar="url", default=registry, help=msg)
    msg = "accept pre-release versions; file-default accepts them in .pre-commit-config.yaml and refuses them elsewhere"
    parser.add_argument("-p", "--pre-release", choices=["yes", "no", "file-default"], default="file-default", help=msg)
    msg = (
        "only use releases uploaded before this cutoff: an RFC 3339 timestamp such as 2026-10-27T15:46:26Z, a local "
        "date, a datetime without an offset (read as local time), or a duration before now such as P7D, PT24H, "
        "7 days or 1 week; the default is the first set of PIP_UPLOADED_PRIOR_TO, UV_EXCLUDE_NEWER, exclude-newer in "
        "the nearest uv.toml or [tool.uv] table, uploaded-prior-to in your pip configuration, and exclude-newer in "
        "your user uv.toml, and exclude-newer = false in a uv file disables the cutoff without consulting the later "
        "sources; like uv, a file without an upload time is excluded, so an index without upload times, such as one "
        "that serves only the HTML simple API, offers no candidates; a requirement already above the newest candidate "
        "is kept; pre-commit hooks take their versions from PyPI or npm, so the cutoff applies to them too"
    )
    cutoff = parser.add_mutually_exclusive_group()
    cutoff.add_argument(
        "--exclude-newer",
        dest="exclude_newer",
        metavar="cutoff",
        default=python_exclude_newer(),
        type=_cutoff,
        help=msg,
    )
    # SUPPRESS keeps the flag out of the defaults, so the mutual exclusion check sees it when it is given
    msg = "ignore every cutoff, including the one from the environment and config files; overrides --exclude-newer"
    cutoff.add_argument(
        "--no-exclude-newer",
        dest="exclude_newer",
        action="store_const",
        const=None,
        default=SUPPRESS,
        help=msg,
    )
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


def _cutoff(value: str) -> datetime:
    try:
        return parse_exclude_newer(value, datetime.now(UTC))
    except (OverflowError, ValueError) as exc:  # a duration too long for a datetime is as invalid as a malformed one
        raise ArgumentTypeError(str(exc)) from exc


class _HelpFormatter(RawDescriptionHelpFormatter):
    def __init__(self, prog: str) -> None:
        super().__init__(prog, max_help_position=35, width=190)


__all__ = [
    "Options",
    "parse_cli",
]

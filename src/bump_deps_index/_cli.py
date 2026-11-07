from __future__ import annotations

from argparse import ArgumentParser, ArgumentTypeError, Namespace, RawDescriptionHelpFormatter
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from ._config._npm import npm_registry
from ._config._python import python_exclude_newer, python_exclude_newer_package, python_index_url
from ._cutoff import parse_exclude_newer
from ._redact import redact_url
from ._run import run
from .version import version

if TYPE_CHECKING:
    from collections.abc import Sequence


def main(args: Sequence[str] | None = None) -> None:
    """
    Run the command-line interface.

    :param args: command-line arguments, or ``sys.argv[1:]`` when None.
    :raises SystemExit: with status 1 when a lookup fails or a file cannot be updated.
    """
    if not run(parse_cli(args)):
        raise SystemExit(1)


def parse_cli(args: Sequence[str] | None) -> Options:
    options = Options()
    parser = _build_parser()
    parser.parse_args(args, namespace=options)
    if options.no_exclude_newer:
        for option, flags in (
            ("--exclude-newer-package", options.exclude_newer_package_flags),
            ("--exclude-newer-group", options.exclude_newer_group_flags),
        ):
            if flags:
                parser.error(f"argument {option}: not allowed with argument --no-exclude-newer")
        options.exclude_newer = None
        options.exclude_newer_package = {}
        options.exclude_newer_group = {}
    else:
        try:
            configured = {
                name: None if value is False else _cutoff_argument(value)
                for name, value in python_exclude_newer_package().items()
            }
        except ArgumentTypeError as exc:
            parser.error(f"invalid exclude-newer-package in uv settings: {exc}")
        options.exclude_newer_package = {**configured, **dict(options.exclude_newer_package_flags)}
        options.exclude_newer_group = dict(options.exclude_newer_group_flags)
    return options


class Options(Namespace):
    """Options of one run, as the command line sets them; ``run`` reads them."""

    index_url: str

    """The PyPI Index URL to query for Python versions."""
    npm_registry: str
    """The NPM registry to query for JS versions."""
    pkgs: list[str]
    """Package names to get latest version for."""
    filenames: list[Path] | None
    """
    Files to update, None to discover them in the working directory during the run; each one of:

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
    no_exclude_newer: bool
    """Whether ``--no-exclude-newer`` was given, which drops every cutoff, the per-package ones included"""
    exclude_newer_package_flags: list[tuple[str, datetime | None]]
    """Per-package cutoffs from the command line, in order; a repeated name takes its last value"""
    exclude_newer_package: dict[str, datetime | None]
    """Per-package cutoffs by the name as written, the command line over the config; None exempts the package"""
    exclude_newer_group_flags: list[tuple[str, datetime | None]]
    """Per-group cutoffs from the command line, in order; a repeated group takes its last value"""
    exclude_newer_group: dict[str, datetime | None]
    """Per-group cutoffs by the group name as written; None exempts the group from the global cutoff"""


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
    cutoff_flags = parser.add_mutually_exclusive_group()
    cutoff_help = (
        "only use releases uploaded before this cutoff, a timestamp or a duration such as P7D "
        "(default: from pip and uv settings)"
    )
    cutoff_flags.add_argument(
        "--exclude-newer",
        dest="exclude_newer",
        metavar="cutoff",
        default=python_exclude_newer(),
        type=_cutoff_argument,
        help=cutoff_help,
    )
    cutoff_flags.add_argument(
        "--no-exclude-newer",
        dest="no_exclude_newer",
        action="store_true",
        help="ignore every cutoff, including the one from the environment and config files; overrides --exclude-newer",
    )
    package_cutoff_help = (
        "cutoff for one package, NAME=CUTOFF in any form --exclude-newer takes or NAME=false for none; repeatable"
    )
    parser.add_argument(
        "--exclude-newer-package",
        dest="exclude_newer_package_flags",
        metavar="name=cutoff",
        action="append",
        default=[],
        type=_named_cutoff_argument,
        help=package_cutoff_help,
    )
    group_cutoff_help = (
        "cutoff for one PEP 735 dependency group, GROUP=CUTOFF in any form --exclude-newer takes or GROUP=false for "
        "none; project means the project's dependencies and extras; repeatable"
    )
    parser.add_argument(
        "--exclude-newer-group",
        dest="exclude_newer_group_flags",
        metavar="group=cutoff",
        action="append",
        default=[],
        type=_named_cutoff_argument,
        help=group_cutoff_help,
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


class _HelpFormatter(RawDescriptionHelpFormatter):
    def __init__(self, prog: str) -> None:
        super().__init__(prog, max_help_position=35, width=190)


def _pre_release_argument(value: str) -> bool | None:
    choices = {"yes": True, "no": False, "file-default": None}
    if value not in choices:  # the message matches the one argparse gives for a `choices` mismatch
        msg = f"{value!r} is not a valid choice: use yes, no or file-default"
        raise ArgumentTypeError(msg)
    return choices[value]


def _cutoff_argument(value: str) -> datetime:
    try:
        return parse_exclude_newer(value, datetime.now(UTC))
    except (OverflowError, ValueError) as exc:  # a duration too long for a datetime is as invalid as a malformed one
        raise ArgumentTypeError(str(exc)) from exc


def _named_cutoff_argument(value: str) -> tuple[str, datetime | None]:
    name, separator, cutoff = value.partition("=")
    if not (separator and name):
        msg = f"{value!r} is not NAME=CUTOFF: use a name, then a cutoff such as P7D or false"
        raise ArgumentTypeError(msg)
    return name, None if cutoff == "false" else _cutoff_argument(cutoff)


__all__ = [
    "Options",
    "main",
    "parse_cli",
]

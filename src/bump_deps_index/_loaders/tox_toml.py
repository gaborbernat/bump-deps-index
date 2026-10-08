from __future__ import annotations

from tomllib import load as load_toml
from typing import TYPE_CHECKING, ClassVar, Final

from typing_extensions import override

from bump_deps_index._spec import PkgType

from ._base import Entry, SingleFileLoader
from ._toml_text import replace_strings

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping
    from pathlib import Path

    from bump_deps_index._parsed import Parsed


_NESTED: Final[frozenset[str]] = frozenset({"env", "env_base"})


class ToxToml(SingleFileLoader):
    filename: ClassVar[str] = "tox.toml"

    @override
    def load(self, filename: Path) -> Iterator[Entry]:
        with filename.open("rb") as file_handler:
            cfg: dict[str, Parsed] = load_toml(file_handler)
        for value in (cfg.get("requires"), *(section.get("deps") for section in _sections(cfg))):
            yield from (Entry(spec, PkgType.PYTHON) for spec in _requirements(value))

    @override
    def _update_text(self, filename: Path, text: str, changes: Mapping[str, str]) -> str:
        return replace_strings(text, changes, _is_dependency)


def _sections(cfg: dict[str, Parsed]) -> Iterator[dict[str, Parsed]]:
    for key, section in cfg.items():
        if isinstance(section, dict):
            yield section
            if key in _NESTED:
                yield from (env for env in section.values() if isinstance(env, dict))


def _requirements(value: Parsed) -> Iterator[str]:
    # follow lists and the branches of a tox substitution that can hold requirements
    match value:
        case str() if value and value[0] not in {"-", "{"}:
            yield value
        case list():
            for item in value:
                yield from _requirements(item)
        case dict() if value.get("replace") == "if":
            yield from _requirements(value.get("then"))
            yield from _requirements(value.get("else"))
        case dict() if value.get("replace") in {"posargs", "env", "glob"}:
            yield from _requirements(value.get("default"))


def _is_dependency(path: tuple[str, ...]) -> bool:
    # an environment named `deps` has the path `env.deps.deps`, so fall through to the next shape
    match path:
        case ("requires", *rest) | (_, "deps", *rest) if _collected(rest):
            return True
        case (nested, _, "deps", *rest) if nested in _NESTED and _collected(rest):
            return True
    return False


def _collected(path: list[str]) -> bool:
    # follow the value the way `_requirements` does
    while path:
        match path:
            case (
                ["[]", *rest] | ["{if}", "then" | "else", *rest] | ["{posargs}" | "{env}" | "{glob}", "default", *rest]
            ):
                path = rest
            case _:
                return False
    return True


__all__ = [
    "ToxToml",
]

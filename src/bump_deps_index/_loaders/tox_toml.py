from __future__ import annotations

from pathlib import Path
from tomllib import load as load_toml
from typing import TYPE_CHECKING, ClassVar, Final

from bump_deps_index._spec import PkgType

from ._base import Loader
from ._toml_text import replace_strings

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

    from bump_deps_index._parsed import Parsed

    from ._base import Entry


_NESTED: Final[frozenset[str]] = frozenset({"env", "env_base"})


class ToxToml(Loader):
    _filename: ClassVar[str] = "tox.toml"

    @property
    def files(self) -> Iterator[Path]:
        if (path := Path.cwd() / self._filename).exists():
            yield path

    def supports(self, filename: Path) -> bool:
        return filename.name == self._filename

    @staticmethod
    def _update_text(text: str, changes: Mapping[str, str]) -> str:
        return replace_strings(text, changes, _is_dependency)

    def load(self, filename: Path, *, pre_release: bool | None) -> Iterator[Entry]:
        pre = False if pre_release is None else pre_release
        with filename.open("rb") as file_handler:
            cfg: dict[str, Parsed] = load_toml(file_handler)
        yield from self._generate(self._specs(cfg.get("requires")), pkg_type=PkgType.PYTHON, pre_release=pre)
        yield from self._extract_deps(cfg, pre_release=pre)

    def _extract_deps(self, cfg: dict[str, Parsed], *, pre_release: bool) -> Iterator[Entry]:
        for key, section in cfg.items():
            if not isinstance(section, dict):
                continue
            yield from self._deps_from_section(section, pre_release=pre_release)
            if key in _NESTED:
                for env_section in section.values():
                    if isinstance(env_section, dict):
                        yield from self._deps_from_section(env_section, pre_release=pre_release)

    def _deps_from_section(self, section: dict[str, Parsed], *, pre_release: bool) -> Iterator[Entry]:
        yield from self._generate(self._specs(section.get("deps")), pkg_type=PkgType.PYTHON, pre_release=pre_release)

    @classmethod
    def _specs(cls, value: Parsed) -> list[str]:
        """Collect dependencies from nested tox substitution fallbacks."""
        found: list[str] = []
        cls._collect(value, found)
        return found

    @classmethod
    def _collect(cls, value: Parsed, found: list[str]) -> None:
        if isinstance(value, str):
            if value and value[0] not in {"-", "{"}:
                found.append(value)
        elif isinstance(value, list):
            for item in value:
                cls._collect(item, found)
        elif isinstance(value, dict):
            replace = value.get("replace")
            if replace == "if":
                cls._collect(value.get("then"), found)
                cls._collect(value.get("else"), found)
            elif replace in {"posargs", "env", "glob"}:
                cls._collect(value.get("default"), found)


def _is_dependency(path: tuple[str, ...]) -> bool:
    # try each shape in turn: an environment named `deps` has the path `env.deps.deps`
    match path:
        case ("requires", *rest) | (_, "deps", *rest) if _collected(rest):
            return True
        case (nested, _, "deps", *rest) if nested in _NESTED and _collected(rest):
            return True
    return False


def _collected(path: list[str]) -> bool:
    # follow the value the way `_collect` does: into lists, and into the branches of a substitution
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

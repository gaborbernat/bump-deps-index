from __future__ import annotations

from tomllib import load as load_toml
from typing import TYPE_CHECKING, ClassVar, Final

from typing_extensions import override

from bump_deps_index._ecosystems._common._loader import Entry, Loaded, SingleFileLoader
from bump_deps_index._lookup import PkgType

from ._toml_text import replace_strings

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping
    from pathlib import Path

    from bump_deps_index._parsed import Parsed


_NESTED: Final[frozenset[str]] = frozenset({"env", "env_base"})
# tox substitutions can hold requirements in their branches, so the walk and the path check follow these keys
_SUBSTITUTIONS: Final[dict[Parsed, tuple[str, ...]]] = {
    "if": ("then", "else"),
    "posargs": ("default",),
    "env": ("default",),
    "glob": ("default",),
}


class ToxToml(SingleFileLoader):
    filename: ClassVar[str] = "tox.toml"

    @override
    def load(self, filename: Path) -> Loaded:
        with filename.open("rb") as file_handler:
            cfg: dict[str, Parsed] = load_toml(file_handler)
        values = (cfg.get("requires"), *(section.get("deps") for section in self._sections(cfg)))
        return Loaded(
            entries=[
                Entry(spec=spec, pkg_type=PkgType.PYTHON) for value in values for spec in self._requirements(value)
            ],
            rewrite=self._update_text,
        )

    @staticmethod
    def _sections(cfg: dict[str, Parsed]) -> Iterator[dict[str, Parsed]]:
        for key, section in cfg.items():
            if isinstance(section, dict):
                yield section
                if key in _NESTED:
                    yield from (env for env in section.values() if isinstance(env, dict))

    @staticmethod
    def _requirements(value: Parsed) -> Iterator[str]:
        match value:
            case str() if value and value[0] not in {"-", "{"}:
                yield value
            case list():
                for item in value:
                    yield from ToxToml._requirements(item)
            case dict() if isinstance(kind := value.get("replace"), str) and kind in _SUBSTITUTIONS:
                for key in _SUBSTITUTIONS[kind]:
                    yield from ToxToml._requirements(value.get(key))

    def _update_text(self, text: str, changes: Mapping[str, str]) -> str:
        return replace_strings(text, changes, self._is_dependency)

    @staticmethod
    def _is_dependency(path: tuple[str, ...]) -> bool:
        # an environment named `deps` has the path `env.deps.deps`, so fall through to the next shape
        match path:
            case ("requires", *rest) | (_, "deps", *rest) if ToxToml._collected(rest):
                return True
            case (nested, _, "deps", *rest) if nested in _NESTED and ToxToml._collected(rest):
                return True
        return False

    @staticmethod
    def _collected(path: list[str]) -> bool:
        # follow the value the way `_requirements` does
        while path:
            match path:
                case ["[]", *rest]:
                    path = rest
                case [kind, key, *rest] if (
                    kind.startswith("{") and kind.endswith("}") and key in _SUBSTITUTIONS.get(kind[1:-1], ())
                ):
                    path = rest
                case _:
                    return False
        return True


__all__ = [
    "ToxToml",
]

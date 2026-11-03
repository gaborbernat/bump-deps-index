from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from typing import TYPE_CHECKING, Generic, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

_Value = TypeVar("_Value")


@dataclass
class _Page(Generic[_Value]):
    lock: Lock = field(default_factory=Lock)
    value: _Value | None = None


class FetchCache(Generic[_Value]):
    def __init__(self) -> None:
        self._pages: dict[str, _Page[_Value]] = {}
        self._lock = Lock()

    def get(self, url: str, fetch: Callable[[str], _Value]) -> _Value:
        with self._lock:
            page = self._pages.setdefault(url, _Page())
        with page.lock:
            if page.value is None:
                page.value = fetch(url)
            return page.value


__all__ = [
    "FetchCache",
]

from __future__ import annotations

from threading import Lock
from typing import TYPE_CHECKING, Generic, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

_Value = TypeVar("_Value")


class FetchCache(Generic[_Value]):
    def __init__(self) -> None:
        self._values: dict[str, _Value] = {}
        self._locks: dict[str, Lock] = {}
        self._lock = Lock()

    def get(self, url: str, fetch: Callable[[str], _Value]) -> _Value:
        with self._lock:
            page_lock = self._locks.setdefault(url, Lock())
        with page_lock:
            if url not in self._values:
                self._values[url] = fetch(url)
            return self._values[url]


__all__ = [
    "FetchCache",
]

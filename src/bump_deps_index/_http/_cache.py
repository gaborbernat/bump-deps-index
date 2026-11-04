from __future__ import annotations

from collections.abc import Hashable
from threading import Lock
from typing import TYPE_CHECKING, Generic, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

_Key = TypeVar("_Key", bound=Hashable)
_Value = TypeVar("_Value")


class FetchCache(Generic[_Key, _Value]):
    def __init__(self) -> None:
        self._values: dict[_Key, _Value] = {}
        self._locks: dict[_Key, Lock] = {}
        self._lock = Lock()

    def get(self, key: _Key, fetch: Callable[[], _Value]) -> _Value:
        with self._lock:
            key_lock = self._locks.setdefault(key, Lock())
        with key_lock:
            if key not in self._values:
                self._values[key] = fetch()
            return self._values[key]


__all__ = [
    "FetchCache",
]

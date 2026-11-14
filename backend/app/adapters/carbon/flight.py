"""One Carbon call per cache file at a time, in this process.

The Carbon reader (CARBON_READER) and the printed-scale reader (RASTER_PRINTED_SCALE) ask the same
page call of the same image and share its cache file. Since they read a sheet at the same time
(app/adapters/beside.py), both could miss the cache and pay for the call twice. Each of them looks
up, calls and writes a cache file inside `flight(path)`: the second one waits for the first and
then finds its reply in the cache. A call that failed is not cached, so the one that waited asks
again, as it did when the two ran one after the other.

`waiting(path)` is how many threads wait for that file's flight (tests)."""

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

_guard = threading.Lock()
_locks: dict[Path, threading.Lock] = {}
_users: dict[Path, int] = {}  # threads holding or waiting for each file's lock
_waiting: dict[Path, int] = {}


@contextmanager
def flight(path: Path | None) -> Iterator[None]:
    """Held while this thread looks up, asks and caches `path`; None (no cache): not held."""
    if path is None:
        yield
        return
    with _guard:
        lock = _locks.setdefault(path, threading.Lock())
        _users[path] = _users.get(path, 0) + 1
        _waiting[path] = _waiting.get(path, 0) + 1
    try:
        with lock:
            with _guard:
                _waiting[path] -= 1
            yield
    finally:
        with _guard:
            _users[path] -= 1
            if not _users[path]:  # the last one: forget the file
                del _users[path], _locks[path], _waiting[path]


def waiting(path: Path) -> int:
    with _guard:
        return _waiting.get(path, 0)

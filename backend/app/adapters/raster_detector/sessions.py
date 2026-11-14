"""One ONNX Runtime session per model file per process, which remembers its recent outputs.

The shipping raster config reads one page with the same network several times: the Decisions
swap and the count arbiter both run `detector-v8:C-yolo26l` (eight identical views), and the
arbiter's one-view read and the `l1` double-check reader feed C-yolo26l the same canvas as view 0
(only their thresholds differ, after the network). A pipeline is also built per project, which
loaded every model again. So `shared_session` keeps one session per model file (path, size and
modification time), and that session keeps the outputs of its last `MEMO` distinct inputs: a run
with an input it has seen returns the outputs it computed, so every reader still gets exactly
the numbers the network gives for its input. Inputs are told apart by a hash of their bytes,
shape and dtype; the arrays handed out are read-only, so no reader can change another's.
A run whose input is being computed on another thread waits for it instead of computing it again.
"""

import hashlib
import threading
from collections import OrderedDict
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import Future
from pathlib import Path
from typing import Any

import numpy as np

MEMO = 32  # inputs remembered per model: one page's eight views plus its one-view reads


class SharedSession:
    """An `onnxruntime.InferenceSession` (or a test's fake) whose `run` is memoised by input."""

    def __init__(self, session: Any, memo: int = MEMO) -> None:
        self._session = session
        self._memo = memo
        self._done: OrderedDict[tuple[Any, ...], Future[tuple[np.ndarray, ...]]] = OrderedDict()
        self._lock = threading.Lock()
        self.runs = 0  # network runs actually made (the rest came from the memo)

    def get_inputs(self) -> Sequence[Any]:
        return self._session.get_inputs()

    def get_outputs(self) -> Sequence[Any]:
        return self._session.get_outputs()

    def run(self, output_names: Any, input_feed: Mapping[str, Any]) -> Sequence[Any]:
        key = _key(output_names, input_feed)
        with self._lock:
            future = self._done.get(key)
            mine = future is None
            if future is None:
                future = Future()
                self._done[key] = future
                while len(self._done) > self._memo:
                    self._done.popitem(last=False)
            else:
                self._done.move_to_end(key)
        if not mine:
            return list(future.result())
        try:
            outputs = tuple(_frozen(v) for v in self._session.run(output_names, input_feed))
        except BaseException as error:
            with self._lock:
                if self._done.get(key) is future:
                    del self._done[key]  # a failed run is not remembered
            future.set_exception(error)
            raise
        with self._lock:
            self.runs += 1
        future.set_result(outputs)
        return list(outputs)


def _frozen(value: Any) -> np.ndarray:
    array = np.asarray(value)
    array.setflags(write=False)
    return array


def _key(output_names: Any, feed: Mapping[str, Any]) -> tuple[Any, ...]:
    parts: list[Any] = [None if output_names is None else tuple(output_names)]
    for name in sorted(feed):
        array = np.ascontiguousarray(feed[name])
        digest = hashlib.blake2b(memoryview(array).cast("B"), digest_size=16).hexdigest()
        parts.append((name, array.dtype.str, array.shape, digest))
    return tuple(parts)


_sessions: dict[tuple[str, int, int], SharedSession] = {}
_sessions_lock = threading.Lock()


def shared_session(model: Path, load: Callable[[Path], Any]) -> SharedSession:
    """The process's session for `model`, made with `load(model)` the first time (or when the
    file changed since)."""
    stat = model.stat()
    key = (str(model.resolve()), stat.st_size, stat.st_mtime_ns)
    with _sessions_lock:
        if key not in _sessions:
            _sessions[key] = SharedSession(load(model))
        return _sessions[key]

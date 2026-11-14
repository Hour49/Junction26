"""Ingest latency without changing what is read: one ONNX session per model file per process that
remembers its outputs by input (raster_detector/sessions.py), and the composite's sources read
a sheet at the same time (answer-latency, 2026-11-14: the shipping config ran C-yolo26l's eight
views twice per page and loaded every model again per project)."""

import threading
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from test_raster_composite import FILE, LEFT, SHEET, Fake, composite, element

from app.adapters.raster_detector.sessions import SharedSession, shared_session
from app.core import cost
from app.core.drawing.model import Plan
from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from app.core.pipeline.ports import Extractor


class Network:
    """A fake ONNX session: output = input * 2, counting its runs; `fail` raises once."""

    def __init__(self, fail: bool = False) -> None:
        self.runs = 0
        self.fail = fail
        self.started = threading.Event()
        self.release = threading.Event()
        self.release.set()

    def get_inputs(self) -> list[Any]:
        return []

    def get_outputs(self) -> list[Any]:
        return []

    def run(self, output_names: Any, feed: dict[str, np.ndarray]) -> list[np.ndarray]:
        self.runs += 1
        self.started.set()
        assert self.release.wait(10)
        if self.fail:
            self.fail = False
            raise RuntimeError("out of memory")
        return [feed["x"] * 2]


def x(value: float) -> dict[str, np.ndarray]:
    return {"x": np.full((1, 3, 4, 4), value, np.float32)}


def test_a_session_runs_the_network_once_per_distinct_input() -> None:
    network = Network()
    session = SharedSession(network)
    first = session.run(None, x(1.0))
    again = session.run(None, x(1.0))
    assert network.runs == 1 and np.array_equal(first[0], again[0])
    assert np.array_equal(first[0], x(2.0)["x"])
    with pytest.raises(ValueError, match="read-only"):
        first[0][0, 0, 0, 0] = 5  # one reader can't change what another reads
    session.run(None, x(1.5))  # another input
    session.run(["y"], x(1.0))  # other outputs asked for
    session.run(None, {"x": x(1.0)["x"].astype(np.float64)})  # same numbers, another dtype
    assert network.runs == 4


def test_the_memo_forgets_the_oldest_input_and_never_a_failed_run() -> None:
    network = Network(fail=True)
    session = SharedSession(network, memo=2)
    with pytest.raises(RuntimeError, match="out of memory"):
        session.run(None, x(1.0))
    session.run(None, x(1.0))  # the failure was not remembered: it runs again
    session.run(None, x(2.0))
    session.run(None, x(3.0))  # x(1.0) is the oldest of three: forgotten
    session.run(None, x(1.0))
    assert network.runs == 5


def test_a_run_for_an_input_being_computed_waits_for_it() -> None:
    network = Network()
    network.release.clear()
    session = SharedSession(network)
    got: list[np.ndarray] = []
    first = threading.Thread(target=lambda: got.append(session.run(None, x(1.0))[0]))
    first.start()
    assert network.started.wait(10)  # the first run is in the network, its input registered
    second = threading.Thread(target=lambda: got.append(session.run(None, x(1.0))[0]))
    second.start()
    network.release.set()
    first.join(10)
    second.join(10)
    assert network.runs == 1 and len(got) == 2 and np.array_equal(got[0], got[1])


def test_one_session_per_model_file_until_the_file_changes(tmp_path: Path) -> None:
    model = tmp_path / "model.onnx"
    model.write_bytes(b"weights")
    loads: list[Path] = []

    def load(path: Path) -> Network:
        loads.append(path)
        return Network()

    first = shared_session(model, load)
    assert shared_session(model, load) is first and len(loads) == 1
    model.write_bytes(b"new weights")
    assert shared_session(model, load) is not first and len(loads) == 2


class Meeting(Fake):
    """A source that waits until every other source of the sheet is reading too, then charges
    its call: read one after another, the first one never gets past the barrier."""

    def __init__(self, barrier: threading.Barrier, usd: float, **kw: Any) -> None:
        super().__init__(**kw)
        self.barrier, self.usd = barrier, usd

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        self.barrier.wait()
        cost.charge(self.usd)
        return super().extract(source, sheet)


def test_the_sources_read_a_sheet_at_the_same_time_and_their_cost_is_the_caller_s() -> None:
    barrier = threading.Barrier(3, timeout=10)
    plan = Plan(id="p", page=1, box=LEFT)
    readers: dict[str, Extractor] = {
        "a": Meeting(barrier, 0.25, plans=(plan,)),
        "b": Meeting(barrier, 0.5, elements=(element("door", LEFT),)),
        "c": Meeting(barrier, 0.125, elements=(element("window", LEFT),)),
    }
    before = cost.spent()
    found = composite({"plans": "a", "door": "b", "window": "c"}, readers).extract(FILE, SHEET)
    assert cost.spent() - before == 0.875
    assert [e.class_ for e in found.elements] == ["door", "window"]
    assert [n for n in found.notes if n.endswith("fake")] == ["a: fake", "b: fake", "c: fake"]

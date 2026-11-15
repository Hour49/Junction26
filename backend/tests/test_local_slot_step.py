"""Decision 0018: a local reading that waited for its slot (INGEST_LOCAL_IN_FLIGHT) reports the
wait as the `local_slot` step before its reader's steps, and shows it as its live step while it
waits; one with a slot at once reports and shows none."""

import threading
from collections.abc import Iterator

import pytest

from app.adapters.one_at_a_time import OneAtATime
from app.core.drawing.model import Scale
from app.core.ingest.timing import StageClock, TimedExtractor
from app.core.pipeline.model import DrawingFile, Extracted, Sheet, StepTrace
from app.core.pipeline.ports import Extractor
from app.core.pipeline.steps import without_steps

DETECTOR = StepTrace(id="detector", label="Symbol detector", at_ms=5, ms=1)


def drawing(path: str) -> DrawingFile:
    return DrawingFile(path=path, sha256="0" * 64, kind="png", size=1)


def read(path: str) -> Extracted:
    return Extracted(
        method="detector", scale=Scale(status="no_scale"), read=("door",), steps=(DETECTOR,)
    )


class Held:
    """The local reader: on a.png it holds its slot until `go`; it reports a detector step."""

    def __init__(self) -> None:
        self.inside, self.go = threading.Event(), threading.Event()

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        if source.path == "a.png":
            self.inside.set()
            assert self.go.wait(10)
        return read(source.path)


class Clock:
    """The steps' clock (`now_ms`), standing still until the test moves it; counts its reads."""

    def __init__(self) -> None:
        self.at_ms, self.reads = 0.0, 0
        self.changed = threading.Condition()

    def __call__(self) -> float:
        with self.changed:
            self.reads += 1
            self.changed.notify_all()
            return self.at_ms


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    fake = Clock()
    monkeypatch.setattr("app.adapters.one_at_a_time.now_ms", fake)
    return fake


def extract(reader: Extractor, path: str, into: dict[str, Extracted]) -> None:
    file = drawing(path)
    into[path] = reader.extract(file, Sheet(file=file, pages=()))


def test_a_reading_that_waited_for_the_slot_reports_the_wait_before_its_steps(
    clock: Clock,
) -> None:
    held = Held()
    reader = OneAtATime(held, 1)
    got: dict[str, Extracted] = {}
    first = threading.Thread(target=extract, args=(reader, "a.png", got))
    first.start()
    assert held.inside.wait(10)  # a.png holds the one slot; it read the clock twice, at 0
    clock.at_ms = 100.0
    second = threading.Thread(target=extract, args=(reader, "b.png", got))
    second.start()
    with clock.changed:  # b.png asked for the slot at 100 and can't have it while a.png reads
        assert clock.changed.wait_for(lambda: clock.reads == 3, timeout=10)
    clock.at_ms = 3000.0
    held.go.set()
    first.join(10)
    second.join(10)
    waited = StepTrace(
        id="local_slot",
        label="Waited for the local reader",
        did="waited 2.9 s: the local readers read one sheet at a time",
        at_ms=100,
        ms=2900,
    )
    assert got["b.png"].steps == (waited, DETECTOR)
    assert without_steps(got["b.png"]) == without_steps(read("b.png"))  # what was read is the same
    assert got["a.png"] == read("a.png")  # it had the slot at once: no step


def sequence(*at_ms: float) -> Iterator[float]:
    return iter(at_ms)


@pytest.mark.parametrize(
    ("slots", "times", "did"),
    [
        (1, (0.0, 0.0), None),  # the slot was free
        (1, (0.0, 9.9), None),  # under WAITED_MS: the lock's own cost
        (1, (0.0, 10.0), "waited 10 ms: the local readers read one sheet at a time"),
        (2, (40.0, 1540.0), "waited 1.5 s: the local readers read 2 sheets at a time"),
    ],
)
def test_a_wait_under_the_threshold_reports_no_step_and_a_longer_one_says_how_long(
    monkeypatch: pytest.MonkeyPatch, slots: int, times: tuple[float, float], did: str | None
) -> None:
    clock = sequence(*times)
    monkeypatch.setattr("app.adapters.one_at_a_time.now_ms", lambda: next(clock))
    got: dict[str, Extracted] = {}
    extract(OneAtATime(Held(), slots), "b.png", got)
    if did is None:
        assert got["b.png"] == read("b.png")
    else:
        assert [(s.id, s.did, s.at_ms, s.ms) for s in got["b.png"].steps] == [
            ("local_slot", did, times[0], times[1] - times[0]),
            ("detector", DETECTOR.did, DETECTOR.at_ms, DETECTOR.ms),
        ]


def test_a_reading_blocked_on_the_slot_shows_local_slot_as_its_live_step_while_it_waits() -> None:
    """The live step (`FileStatus.step_id`, through ingest's TimedExtractor) says `local_slot`
    while b.png waits for a.png's slot; a.png, which had the slot at once, never shows it."""
    held = Held()
    reader = OneAtATime(held, 1)
    heard: dict[str, list[str]] = {"a.png": [], "b.png": []}
    waiting = threading.Event()

    def live(path: str, step_id: str, label: str) -> None:
        heard[path].append(step_id)
        if path == "b.png" and step_id == "local_slot":
            assert label == "Waited for the local reader"
            waiting.set()

    def timed(path: str) -> Extractor:  # one per group, as ingest builds them
        return TimedExtractor(reader, StageClock(clock=lambda: 0.0, on_step=live))

    got: dict[str, Extracted] = {}
    first = threading.Thread(target=extract, args=(timed("a.png"), "a.png", got))
    first.start()
    assert held.inside.wait(10)  # a.png holds the one slot
    second = threading.Thread(target=extract, args=(timed("b.png"), "b.png", got))
    second.start()
    assert waiting.wait(10)  # b.png shows the wait ...
    assert "b.png" not in got and second.is_alive()  # ... while it is still blocked on the slot
    assert heard == {"a.png": [], "b.png": ["local_slot"]}
    held.go.set()
    first.join(10)
    second.join(10)
    assert heard == {"a.png": [], "b.png": ["local_slot"]}  # the live step is started once
    assert set(got) == {"a.png", "b.png"}

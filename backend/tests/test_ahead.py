"""The local reading's Gemini calls asked before its slot (app/adapters/ahead.py)."""

import threading

import pytest

from app.adapters.ahead import AheadDecisions, AheadExtractor, DecisionsReading
from app.adapters.decisions.client import DecisionsError
from app.adapters.decisions.g1main import CountDist, PageCounts
from app.adapters.decisions.uses import DecisionsCountExtractor
from app.adapters.one_at_a_time import OneAtATime
from app.adapters.raster import assemble
from app.core import cost
from app.core.drawing.model import Scale
from app.core.pipeline.model import DrawingFile, Extracted, Plan, Sheet
from app.core.pipeline.ports import Extractor

FILE = DrawingFile(path="a.png", size=3, sha256="a", kind="png")


def sheet(file: DrawingFile = FILE) -> Sheet:
    return Sheet(file=file, pages=())


def plan() -> Extracted:
    return Extracted(
        method="detector",
        scale=Scale(status="no_scale"),
        plans=(Plan(id="p1", page=1, box=(0.0, 0.0, 1.0, 1.0)),),
        read=("door",),
    )


class Files:
    def read(self, path: str) -> bytes:
        return path.encode()


class Model:
    """A model call: waits for `go`, charges 0.01 USD on its thread, says which bytes it read."""

    def __init__(self, fail: bool = False) -> None:
        self.asked: list[bytes] = []
        self.started, self.go = threading.Event(), threading.Event()
        self.fail = fail

    def read(self, image: bytes) -> PageCounts:
        self.asked.append(image)
        self.started.set()
        assert self.go.wait(10)
        cost.charge(0.01)
        if self.fail:
            raise DecisionsError("no answer")
        families = {name: CountDist({0: 1.0}) for name in ("toilet", "shower+bathtub", "sauna")}
        return PageCounts(families, f"read {image.decode()}")


class Rooms:
    """A rooms reader that only asks a model: the same Model, one Extracted per sheet."""

    def __init__(self, model: Model) -> None:
        self.model = model

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        note = self.model.read(source.path.encode()).note
        return plan().model_copy(update={"notes": (note,)})


class Held:
    """A local reader that holds the slot until `go`."""

    def __init__(self) -> None:
        self.inside, self.go = threading.Event(), threading.Event()

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        self.inside.set()
        assert self.go.wait(10)
        return plan()


def test_a_reading_asks_its_model_call_while_another_holds_the_slot() -> None:
    holder, model = Held(), Model()
    rooms = AheadExtractor(Rooms(model), workers=2)
    first = threading.Thread(target=OneAtATime(holder, 1).extract, args=(FILE, sheet()))
    first.start()
    assert holder.inside.wait(10)
    second = threading.Thread(target=OneAtATime(rooms, 1, [rooms]).extract, args=(FILE, sheet()))
    second.start()
    assert model.started.wait(10)  # asked although the slot is still held
    model.go.set()
    holder.go.set()
    first.join(10)
    second.join(10)
    assert model.asked == [b"a.png"]  # once: the reading took the started call


def test_the_taker_gets_the_started_result_and_pays_for_it_on_its_thread() -> None:
    model = Model()
    model.go.set()
    rooms = AheadExtractor(Rooms(model), workers=1)
    read = sheet()
    rooms.start(FILE, read)
    before = cost.mark()
    found = rooms.extract(FILE, read)
    assert cost.since(before) == pytest.approx(0.01)
    assert found.notes == ("read a.png",)
    assert model.asked == [b"a.png"]


def test_a_started_call_that_failed_raises_where_it_is_taken() -> None:
    model = Model(fail=True)
    model.go.set()
    early = AheadDecisions(model, Files(), workers=1)
    read = sheet()
    early.start(FILE, read)
    before = cost.mark()
    with early.reading(read), pytest.raises(DecisionsError):
        early.read(b"a.png")
    assert cost.since(before) == pytest.approx(0.01)
    assert model.asked == [b"a.png"]


class Fails:
    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        raise RuntimeError("the detector broke")


def test_a_call_the_reading_never_took_is_still_charged() -> None:
    model = Model()
    model.go.set()
    rooms = AheadExtractor(Rooms(model), workers=1)
    before = cost.mark()
    with pytest.raises(RuntimeError):
        OneAtATime(Fails(), 1, [rooms]).extract(FILE, sheet())
    assert cost.since(before) == pytest.approx(0.01)
    assert model.asked == [b"a.png"]


def test_two_readings_of_one_file_at_once_keep_their_own_calls() -> None:
    """Two projects reading the same file (same path and content) never take each other's."""
    model = Model()
    model.go.set()
    rooms = AheadExtractor(Rooms(model), workers=2)
    one, two = sheet(), sheet()
    rooms.start(FILE, one)
    rooms.start(FILE, two)
    rooms.extract(FILE, one)
    rooms.settle(one)  # the first reading ends: the second's call is not its to settle
    before = cost.mark()
    rooms.extract(FILE, two)
    assert cost.since(before) == pytest.approx(0.01)
    assert model.asked == [b"a.png", b"a.png"]  # two calls, as two readings asked


def test_the_composite_s_decisions_component_takes_the_call_started_for_its_reading() -> None:
    """Through the composite (its components on their own threads), the Decisions reader gets
    the call OneAtATime started, so the reading pays for one call, not two."""
    model = Model()
    model.go.set()
    early = AheadDecisions(model, Files(), workers=1)
    counted = DecisionsReading(DecisionsCountExtractor(Held(), Files(), early), early)
    built: dict[str, Extractor] = {"decisions": counted}
    composite = assemble({"plans": "decisions", "elements": "decisions"}, built.__getitem__)
    reader = OneAtATime(composite, 1, [early])
    counted._inner._inner.go.set()  # pyright: ignore[reportAttributeAccessIssue]
    before = cost.mark()
    found = reader.extract(FILE, sheet())
    assert model.asked == [b"a.png"]
    assert cost.since(before) == pytest.approx(0.01)
    assert any("read a.png" in note for note in found.notes)


def test_without_a_reading_the_decisions_reader_asks_as_before() -> None:
    model = Model()
    model.go.set()
    early = AheadDecisions(model, Files(), workers=1)
    assert early.read(b"x").note == "read x"
    assert model.asked == [b"x"]


class NoAnswer(Model):
    """A call that got no answer: counted on its own thread (`cost.fail`), as the clients do."""

    def read(self, image: bytes) -> PageCounts:
        cost.fail()
        return super().read(image)


@pytest.mark.parametrize("ends", ["taken", "settled"])
def test_a_started_call_s_failed_calls_reach_the_reading_s_thread(ends: str) -> None:
    model = NoAnswer(fail=True)
    early = AheadDecisions(model, Files(), workers=1)
    read = sheet()
    early.start(FILE, read)
    assert model.started.wait(10)  # running, so the reading uses it rather than asking again
    before = cost.faults()
    model.go.set()
    if ends == "taken":
        with early.reading(read), pytest.raises(DecisionsError):
            early.read(b"a.png")
    else:
        early.settle(read)
    assert cost.faults_since(before) == 1  # the reading is marked partial, not kept

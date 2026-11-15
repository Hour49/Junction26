"""Decision 0018: each reader that reads a sheet is a step of the extract stage, with what it
was read for, when it began, how long it ran, what it cost and what it found."""

import threading

from pdf_sheets import SheetPdf
from test_count_arbiter import FILE as ARBITER_FILE
from test_count_arbiter import SHEET as ARBITER_SHEET
from test_count_arbiter import Files as ArbiterFiles
from test_count_arbiter import Read as ArbiterRead
from test_count_arbiter import follows_second, l1
from test_ifc_model import DEMO, IfcModelExtractor, IfcModels, model_file, stored
from test_ifc_model import extract as ifc_extract
from test_pdf_tables import untitled_boxes
from test_raster_composite import FILE, LEFT, RIGHT, SHEET, Fake, composite, element, room
from test_vector_pdf import extract as vector_extract
from test_vector_pdf import swiss_sheet

from app.adapters.carbon import THINGS, CarbonChecked, CarbonSwitch, CarbonThings
from app.adapters.count_arbiter import ArbiterCountExtractor
from app.adapters.printed_scale import PrintedScale
from app.adapters.raster import assemble, parse_components, source_label
from app.core import cost
from app.core.drawing.model import Plan, Scale
from app.core.ingest.model import StageTrace
from app.core.ingest.timing import StageClock, TimedExtractor, with_steps
from app.core.pipeline.model import DrawingFile, Extracted, Sheet, StepTrace
from app.core.pipeline.ports import Extractor
from app.core.pipeline.printed import PrintedSheet
from app.core.pipeline.steps import now_ms

PLANS = (Plan(id="x", page=1, box=(0.0, 0.0, 1.0, 1.0)),)


class Meeting(Fake):
    """A component that waits at `barrier` while it reads, so every component sharing it is
    reading at the same time; it pays `usd` and has `faults` model calls fail."""

    def __init__(
        self, barrier: threading.Barrier, usd: float = 0.0, faults: int = 0, **found: object
    ) -> None:
        super().__init__(**found)  # type: ignore[arg-type]
        self.barrier, self.usd, self.faults = barrier, usd, faults

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        self.barrier.wait(timeout=10)
        cost.charge(self.usd)
        if self.faults:
            cost.fail(self.faults)
        return super().extract(source, sheet)


def test_each_source_is_a_step_and_parallel_sources_overlap() -> None:
    barrier = threading.Barrier(3)
    readers: dict[str, Extractor] = {
        "detector-v8:C": Meeting(
            barrier,
            elements=[element("door", LEFT), element("door", RIGHT), element("window", LEFT)],
            read=["door", "window"],
        ),
        "gemini": Meeting(barrier, usd=0.004, rooms=[room("kitchen", LEFT)], read=["room"]),
        "one-plan": Meeting(barrier, plans=PLANS),
    }
    got = composite(
        {"elements": "detector-v8:C", "rooms": "gemini", "plans": "one-plan"}, readers
    ).extract(FILE, SHEET)
    by_id = {step.id: step for step in got.steps}
    assert set(by_id) == {"detector", "rooms", "plans"}
    detector, rooms, plans = by_id["detector"], by_id["rooms"], by_id["plans"]
    assert detector.label == "Symbol detector, 8 views"
    assert detector.found == {"door": 2, "window": 1}
    assert detector.did.startswith("read for door, window") and "2 doors, 1 window" in detector.did
    assert (rooms.label, rooms.found) == ("Room reader (Gemini)", {"room": 1})
    assert rooms.cost_usd == 0.004
    assert plans.found == {"plan": 1}
    # all three met at the barrier: each began before every other one ended
    for one in got.steps:
        for other in got.steps:
            assert one.at_ms <= other.at_ms + other.ms
    assert [step.at_ms for step in got.steps] == sorted(step.at_ms for step in got.steps)


def test_a_source_whose_model_calls_failed_is_a_failed_step() -> None:
    barrier = threading.Barrier(1)
    readers: dict[str, Extractor] = {
        "carbon": Meeting(barrier, faults=2, elements=[element("door", LEFT)])
    }
    got = composite({"elements": "carbon", "plans": "carbon"}, readers).extract(FILE, SHEET)
    (step,) = got.steps
    assert (step.id, step.label, step.state) == ("carbon", "Gemini Carbon reader", "failed")
    assert step.did.endswith("2 model calls got no answer")


def test_a_double_check_reader_is_its_own_step_and_never_counted() -> None:
    readers = {
        "detector:A": Fake(elements=[element("door", LEFT)], read=["door"]),
        "detector:B": Fake(elements=[element("door", LEFT), element("door", RIGHT)], read=["door"]),
        "one-plan": Fake(plans=PLANS),
    }
    built = assemble(
        parse_components("elements=detector:A,plans=one-plan"),
        readers.__getitem__,
        double_check={"l1": "detector:B"},
    )
    got = built.extract(FILE, SHEET)
    check = next(step for step in got.steps if step.id == "double_check")
    assert check.label == "Double-check reader l1: Symbol detector"
    assert check.did.startswith("never counted") and check.found == {"door": 2}
    assert len(got.elements) == 1


def test_a_decisions_source_names_the_reader_it_wraps() -> None:
    assert source_label("decisions-s1536:region:C-yolo26s-1536") == (
        "decisions",
        "Gemini Decisions count swap (1536 px) over Symbol detector with region model",
    )
    assert source_label("someday:x") == ("reader", "Reader someday:x")


def test_the_vector_reader_is_one_step_naming_its_sheet_style() -> None:
    got = vector_extract(swiss_sheet().pdf())
    (step,) = got.steps
    assert (step.id, step.label) == ("vector", "Drawn-PDF reader (Swiss plan rules)")
    assert step.found["room"] == len(got.rooms) > 0
    assert step.ms > 0


def test_a_drawn_pdf_no_style_matches_is_a_step_saying_so() -> None:
    sheet = SheetPdf()
    untitled_boxes(sheet)
    (step,) = vector_extract(sheet.pdf()).steps
    assert step.label == "Drawn-PDF reader"
    assert step.did.startswith("no sheet style we have reading rules for")
    assert step.found == {}


def test_the_ifc_reader_is_one_step_on_a_sheet_and_on_the_model_itself() -> None:
    (on_sheet,) = ifc_extract().steps
    assert (on_sheet.id, on_sheet.label) == ("ifc", "IFC model placed on the sheet (SVG twin)")
    assert on_sheet.found and on_sheet.state == "done"
    files = stored(DEMO)
    itself = IfcModelExtractor(files, IfcModels(files)).extract(
        model_file(), Sheet(file=model_file(), pages=())
    )
    (step,) = itself.steps
    assert step.label == "IFC model reader"
    assert sum(step.found.values()) == len(itself.model_objects or ())


class Stepped:
    """An extractor that reports one step that began 1 ms after its call, on the steps' clock."""

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        step = StepTrace(id="vector", label="v", at_ms=now_ms() + 1, ms=2)
        return Extracted(method="parser", scale=Scale(status="no_scale"), steps=(step,))


def test_a_second_extract_call_lists_its_steps_after_the_first() -> None:
    now = iter([0.0, 0.010, 0.010, 0.030])  # the first call ran 10 ms, the second 20 ms
    timer = StageClock(lambda: next(now))
    timed = TimedExtractor(Stepped(), timer)
    timed.extract(FILE, SHEET)
    timed.extract(FILE, SHEET)
    steps = timer.steps[FILE.path]["extract"]
    # 1 ms into each call (plus the few µs the call took to get there)
    assert 1 <= steps[0].at_ms < 2 and 11 <= steps[1].at_ms < 12
    stage = StageTrace(stage="extract", did="read", ms=30)
    other = StageTrace(stage="takeoff", did="t", ms=1)
    traced = with_steps([stage, other], timer.steps[FILE.path])
    assert traced[0].steps == tuple(steps) and traced[1].steps == ()


class Waiting:
    """A wrapper that waits `ms` (a queue) before its inner reader runs, then passes its steps
    on as they are."""

    def __init__(self, inner: Extractor, ms: float) -> None:
        self.inner, self.ms = inner, ms

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        until = now_ms() + self.ms
        while now_ms() < until:
            pass
        return self.inner.extract(source, sheet)


def test_a_step_after_a_wait_in_a_wrapper_begins_after_the_wait() -> None:
    timer = StageClock(lambda: 0.0)
    TimedExtractor(Waiting(Stepped(), 20), timer).extract(FILE, SHEET)
    (step,) = timer.steps[FILE.path]["extract"]
    assert step.at_ms >= 21  # the 20 ms wait, then 1 ms into the inner call


class Paid(Fake):
    """A reader whose model calls cost `usd`, `faults` of them unanswered, and that reports one
    step of its own."""

    def __init__(self, usd: float = 0.0, faults: int = 0, **found: object) -> None:
        super().__init__(**found)  # type: ignore[arg-type]
        self.usd, self.faults = usd, faults

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        cost.charge(self.usd)
        if self.faults:
            cost.fail(self.faults)
        own = StepTrace(id="detector", label="Symbol detector", at_ms=0, ms=1)
        return super().extract(source, sheet).model_copy(update={"steps": (own,)})


def test_carbon_on_a_large_sheet_keeps_the_shipped_steps_and_adds_its_own() -> None:
    barrier = threading.Barrier(2)
    shipped = Meeting(barrier, rooms=[room("kitchen", LEFT)], plans=PLANS, read=["room"])
    carbon = Meeting(barrier, usd=0.02, elements=[element("door", LEFT)], plans=PLANS)
    shipped.found = shipped.found.model_copy(
        update={"steps": (StepTrace(id="rooms", label="Room reader (Gemini)"),)}
    )
    got = CarbonThings(shipped, carbon, lambda _: True).extract(FILE, SHEET)
    assert [step.id for step in got.steps] == ["rooms", "carbon"]
    step = got.steps[1]
    assert (step.label, step.state, step.cost_usd) == (THINGS, "done", 0.02)
    assert step.found == {"door": 1, "plan": 1} and step.did == "1 door, 1 plan"
    # both met at the barrier, so Carbon ran beside the shipped reader


def test_carbon_not_needed_by_the_few_clause_is_a_skipped_step() -> None:
    shipped = Fake(elements=[element("door", LEFT), element("door", RIGHT)], plans=PLANS)
    got = CarbonThings(shipped, Fake(), lambda _: False, few=2).extract(FILE, SHEET)
    (step,) = got.steps
    assert (step.id, step.state) == ("carbon", "skipped")
    assert (
        step.did == "not needed: the shipped reader found 2 elements (it reads a sheet with "
        "fewer than 2)"
    )


def test_carbon_that_read_nothing_is_a_failed_step_and_the_shipped_reading_stays() -> None:
    shipped = Fake(plans=PLANS)
    nothing = Paid(faults=1, read=[])
    nothing.found = nothing.found.model_copy(update={"notes": ("carbon: HTTP 503",)})
    got = CarbonThings(shipped, nothing, lambda _: False, few=3).extract(FILE, SHEET)
    (step,) = [step for step in got.steps if step.id == "carbon"]
    assert step.state == "failed"
    assert step.did == "read nothing: HTTP 503; the shipped reading stays"


def test_carbon_alone_and_carbon_as_a_check_are_steps() -> None:
    carbon = Paid(usd=0.01, elements=[element("window", LEFT)], plans=PLANS, read=["window"])
    alone = CarbonSwitch(Fake(), carbon, lambda _: True).extract(FILE, SHEET)
    assert [s.label for s in alone.steps] == [
        "Symbol detector",
        "Gemini Carbon reader (the whole sheet)",
    ]
    assert alone.steps[1].found == {"window": 1, "plan": 1}
    checked = CarbonChecked(Fake(plans=PLANS), carbon).extract(FILE, SHEET)
    (step,) = checked.steps
    assert (step.label, step.found, step.cost_usd) == (
        "Gemini Carbon check (never counted)",
        {"window": 1, "plan": 1},
        0.01,
    )


def test_the_printed_scale_is_a_step_after_the_inner_readers() -> None:
    printed = PrintedSheet(printed_scale="1:100")
    inner = Paid(plans=PLANS)
    got = PrintedScale(inner, PrintedFixed(printed), PrintedFiles()).extract(FILE, SHEET)
    assert [step.id for step in got.steps] == ["detector", "printed_scale"]
    step = got.steps[1]
    assert step.label == "Printed scale and counts (Gemini Carbon)"
    assert step.did.startswith("printed scale 1:100; the sheet's scale: ")


class PrintedFixed:
    def __init__(self, printed: PrintedSheet) -> None:
        self.printed = printed

    def read(self, source: DrawingFile, sheet: Sheet) -> PrintedSheet:
        return self.printed


class PrintedFiles:
    def read(self, path: str) -> bytes:
        return b""


def test_the_count_arbiter_lists_its_three_reads_in_order() -> None:
    base = ArbiterRead({"toilet": 1})
    second = ArbiterRead({"toilet": 2})
    got = ArbiterCountExtractor(
        base, second, l1(), follows_second("toilet"), ArbiterFiles()
    ).extract(ARBITER_FILE, ARBITER_SHEET)
    assert [(step.id, step.label) for step in got.steps] == [
        ("detector", "Symbol detector (arbiter base)"),
        ("detector", "Symbol detector (arbiter second read)"),
        ("arbiter", "Count arbiter (L1 page counts)"),
    ]
    assert got.steps[0].found == {"toilet": 1} and got.steps[1].found == {"toilet": 2}
    assert got.steps[2].did.startswith("toilet 1 -> 2 (P = ")
    assert got.steps[0].at_ms <= got.steps[1].at_ms <= got.steps[2].at_ms

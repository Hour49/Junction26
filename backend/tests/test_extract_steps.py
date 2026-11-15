"""Decision 0018: each reader that reads a sheet is a step of the extract stage, with what it
was read for, when it began, how long it ran, what it cost and what it found."""

import threading

import pytest
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
from app.core.pipeline.steps import listening, starting

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
    assert detector.did == "read for 14 element classes; 2 doors, 1 window"
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
    check = next(step for step in got.steps if step.id == "double_check:l1")
    assert check.label == "Double-check reader 1: Symbol detector"
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


class StepsClock:
    """The steps' clock (`now_ms`), standing still until a test moves it: exact bounds."""

    def __init__(self, at_ms: float = 100.0) -> None:
        self.at_ms = at_ms

    def __call__(self) -> float:
        return self.at_ms


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> StepsClock:
    fake = StepsClock()
    monkeypatch.setattr("app.core.ingest.timing.now_ms", fake)  # what TimedExtractor reads
    return fake


class Stepped:
    """An extractor that reports one step that began 1 ms after its call, on the steps' clock."""

    def __init__(self, clock: StepsClock) -> None:
        self._clock = clock

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        step = StepTrace(id="vector", label="v", at_ms=self._clock() + 1, ms=2)
        return Extracted(method="parser", scale=Scale(status="no_scale"), steps=(step,))


def test_a_second_extract_call_lists_its_steps_after_the_first(clock: StepsClock) -> None:
    now = iter([0.0, 0.010, 0.010, 0.030])  # the first call ran 10 ms, the second 20 ms
    timer = StageClock(lambda: next(now))
    timed = TimedExtractor(Stepped(clock), timer)
    timed.extract(FILE, SHEET)
    clock.at_ms += 500  # the steps' clock moved on between the calls: it does not matter
    timed.extract(FILE, SHEET)
    steps = timer.steps[FILE.path]["extract"]
    # 1 ms into each call; the second call starts 10 ms into the stage
    assert (steps[0].at_ms, steps[1].at_ms) == (1, 11)
    stage = StageTrace(stage="extract", did="read", ms=30)
    other = StageTrace(stage="takeoff", did="t", ms=1)
    traced = with_steps([stage, other], timer.steps[FILE.path])
    # the same id twice in one stage: the second is numbered, so a live step_id names one step
    assert [step.id for step in traced[0].steps] == ["vector", "vector-2"]
    assert traced[1].steps == ()


class Waiting:
    """A wrapper that waits `ms` (a queue) before its inner reader runs, then passes its steps
    on as they are."""

    def __init__(self, inner: Extractor, ms: float, clock: StepsClock) -> None:
        self.inner, self.ms, self._clock = inner, ms, clock

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        self._clock.at_ms += self.ms  # the wait, on the steps' clock
        return self.inner.extract(source, sheet)


def test_a_step_after_a_wait_in_a_wrapper_begins_after_the_wait(clock: StepsClock) -> None:
    timer = StageClock(lambda: 0.0)
    TimedExtractor(Waiting(Stepped(clock), 20, clock), timer).extract(FILE, SHEET)
    (step,) = timer.steps[FILE.path]["extract"]
    assert step.at_ms == 21  # the 20 ms wait, then 1 ms into the inner call


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
    assert step.found == {"door": 1, "plan": 1}
    assert step.did == "1 door, 1 plan; replaces the shipped reading's things drawn (a large sheet)"
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
    assert (step.id, step.label, step.found, step.cost_usd) == (
        "carbon_check",
        "Gemini Carbon check (never counted)",
        {"window": 1, "plan": 1},
        0.01,
    )


def test_the_carbon_check_over_carbon_things_keeps_both_ids_without_a_number() -> None:
    carbon = Paid(elements=[element("window", LEFT)], plans=PLANS, read=["window"])
    things = CarbonThings(Fake(plans=PLANS), carbon, lambda _: True)
    got = CarbonChecked(things, carbon).extract(FILE, SHEET)
    stage = StageTrace(stage="extract", did="read", ms=1.0)
    (traced,) = with_steps([stage], {"extract": list(got.steps)})
    assert sorted(step.id for step in traced.steps) == ["carbon", "carbon_check"]


def test_the_printed_scale_is_a_step_after_the_inner_readers() -> None:
    printed = PrintedSheet(printed_scale="1:100")
    inner = Paid(plans=PLANS)
    got = PrintedScale(inner, PrintedFixed(printed), PrintedFiles()).extract(FILE, SHEET)
    assert [step.id for step in got.steps] == ["detector", "printed_scale"]
    step = got.steps[1]
    assert step.label == "Printed scale and counts (Gemini Carbon)"
    # no resolution to turn the ratio into metres per pixel: read, not used, and the step says so
    assert step.did.startswith("printed scale 1:100: read, not used (")


class PrintedFixed:
    def __init__(self, printed: PrintedSheet) -> None:
        self.printed = printed

    def read(self, source: DrawingFile, sheet: Sheet) -> PrintedSheet:
        return self.printed


def test_double_check_readers_are_numbered_in_words_and_keep_their_ids() -> None:
    # QA R4 (detail's audit): "Double-check reader l1 / m1" showed config names on screen
    readers = {
        "detector:A": Fake(elements=[element("door", LEFT)], read=["door"]),
        "detector:B": Fake(read=["door"]),
        "detector:C": Fake(read=["door"]),
        "one-plan": Fake(plans=PLANS),
    }
    built = assemble(
        parse_components("elements=detector:A,plans=one-plan"),
        readers.__getitem__,
        double_check={"l1": "detector:B", "m1": "detector:C"},
    )
    got = built.extract(FILE, SHEET)
    checks = [(s.id, s.label) for s in got.steps if s.id.startswith("double_check:")]
    assert sorted(checks) == [
        ("double_check:l1", "Double-check reader 1: Symbol detector"),
        ("double_check:m1", "Double-check reader 2: Symbol detector"),
    ]


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
        ("base", "Symbol detector (arbiter base)"),
        ("second", "Symbol detector (arbiter second read)"),
        ("pick", "Count arbiter (a page-level count model)"),
    ]
    assert got.steps[0].found == {"toilet": 1} and got.steps[1].found == {"toilet": 2}
    assert got.steps[2].did.startswith("toilet 1 -> 2 (P = ")
    assert got.steps[0].at_ms <= got.steps[1].at_ms <= got.steps[2].at_ms


def test_a_source_counts_only_the_classes_it_gives() -> None:
    both = [element("door", LEFT), element("window", RIGHT)]
    readers: dict[str, Extractor] = {
        "detector:A": Fake(elements=both, read=["door", "window"]),
        "detector:B": Fake(elements=[*both, element("door", RIGHT)], read=["door", "window"]),
        "one-plan": Fake(plans=PLANS),
    }
    got = composite(
        {"elements": "detector:A", "door": "detector:B", "plans": "one-plan"}, readers
    ).extract(FILE, SHEET)
    by_did = {step.did.split(";")[0]: step.found for step in got.steps}
    assert by_did["read for door"] == {"door": 2}
    assert by_did["read for 13 element classes"] == {"window": 1}


def test_each_source_is_heard_live_as_it_starts_on_its_own_thread() -> None:
    readers: dict[str, Extractor] = {
        "detector:A": Fake(elements=[element("door", LEFT)], read=["door"]),
        "detector:B": Fake(read=["door"]),
        "one-plan": Fake(plans=PLANS),
    }
    built = assemble(
        parse_components("elements=detector:A,plans=one-plan"),
        readers.__getitem__,
        double_check={"l1": "detector:B"},
    )
    heard: list[tuple[str, str]] = []
    with listening(lambda step_id, label: heard.append((step_id, label))):
        built.extract(FILE, SHEET)
    assert sorted(heard) == [
        ("detector", "Symbol detector"),
        ("double_check:l1", "Double-check reader 1: Symbol detector"),
        ("plans", "Whole page as one plan"),
    ]
    starting("vector", "nobody listens")  # outside the block: heard by no one
    assert len(heard) == 3


class Inner(Fake):
    """A source that runs two steps of its own, and says so live."""

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        starting("pick", "Pick")
        own = (StepTrace(id="base", label="Base"), StepTrace(id="pick", label="Pick"))
        return super().extract(source, sheet).model_copy(update={"steps": own})


def test_a_sources_own_steps_are_nested_under_its_id_and_heard_so() -> None:
    readers: dict[str, Extractor] = {
        "arbiter-t1:C": Inner(elements=[element("door", LEFT)], read=["door"]),
        "one-plan": Fake(plans=PLANS),
    }
    heard: list[str] = []
    with listening(lambda step_id, label: heard.append(step_id)):
        got = composite({"door": "arbiter-t1:C", "plans": "one-plan"}, readers).extract(FILE, SHEET)
    ids = [step.id for step in got.steps]
    assert {"arbiter", "arbiter/base", "arbiter/pick", "plans"} == set(ids)
    assert ids.index("arbiter") + 1 == ids.index("arbiter/base")  # right after its parent
    assert "arbiter/pick" in heard and len(ids) == len(set(ids))


def test_carbon_says_it_replaces_the_shipped_things_and_what_it_found_none_of() -> None:
    shipped = Fake(elements=[element("door", LEFT)], plans=PLANS, read=["door", "room"])
    carbon = Fake(elements=[element("window", LEFT)], plans=PLANS, read=["door", "window", "sink"])
    few = CarbonThings(shipped, carbon, lambda _: False, few=3).extract(FILE, SHEET)
    step = next(step for step in few.steps if step.id == "carbon")
    assert step.did == (
        "1 plan, 1 window; replaces the shipped reading's things drawn (1 element, fewer than 3); "
        "looked for, none found: door, sink"
    )
    large = CarbonThings(shipped, carbon, lambda _: True).extract(FILE, SHEET)
    step = next(step for step in large.steps if step.id == "carbon")
    assert step.did.endswith(
        "replaces the shipped reading's things drawn (a large sheet); "
        "looked for, none found: door, sink"
    )


def test_a_printed_scale_read_and_not_used_says_why() -> None:
    # a JPEG with no stated resolution: the printed ratio can't become metres per pixel
    printed = PrintedSheet(printed_scale="1/100")
    got = PrintedScale(Paid(plans=PLANS), PrintedFixed(printed), PrintedFiles()).extract(
        FILE, SHEET
    )
    step = got.steps[-1]
    assert step.did == (
        "printed scale 1/100: read, not used (no scale bar was measured and the image states no "
        "resolution to trust); the sheet's scale: no scale on the sheet"
    )

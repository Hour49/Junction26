"""PRINTED_TOTAL_ANSWERS=on (app/core/pipeline/printed_answer.py): a count the sheet prints for
exactly what a stage-8 entry counts (same subject, the floor the sheet shows, one value) is the
answer; the count read off the drawing stays on the entry, so the difference still shows. QA round 4
R4-D1: T2 prints "SECOND FLOOR = 48 DORMS" (and the first and third floors' 48, and TOTAL = 144);
the reader counted 40 bedrooms and the answer was 40."""

from pathlib import Path

import pytest
from test_answering import NoPrior
from test_printed_scale import FILE, SHEET, Around, Files, Fixed, Reader, png

from app.adapters.printed_scale import PrintedScale
from app.adapters.raster_scale import PriorScale
from app.composition import build_ingest
from app.core.answering.answer import answer_question
from app.core.answering.model import Query, Question, Unsupported
from app.core.drawing.model import Drawing, Plan
from app.core.pipeline.ingest import ingest
from app.core.pipeline.model import Extracted, Quantity
from app.core.pipeline.printed import PrintedFact, PrintedSheet
from app.core.pipeline.printed_answer import answered, printed_answers
from app.core.pipeline.rules import apply_rules
from app.core.pipeline.second_count import measured, second_count
from app.core.pipeline.takeoff import take_off
from app.settings import Settings


def dorms(text: str, value: float = 48, subject: str = "room:bedroom") -> PrintedFact:
    return PrintedFact(text=text, subject=subject, value=value, unit="count",
                       box=(0.76, 0.17, 0.87, 0.19))  # fmt: skip


T2 = (  # what Carbon read on T2's room count table, in its order
    dorms("FIRST FLOOR = 48 DORMS"),
    dorms("SECOND FLOOR = 48 DORMS", 48.0),
    dorms("THIRD FLOOR = 48 DORMS"),
    dorms("TOTAL = 144 DORMS", 144),
)
SECOND = (Plan(id="p1", page=1, box=(0, 0, 1, 1), storey="SECOND FLOOR"),)


class Planned(Fixed):
    """`Fixed`'s reading of `bedrooms` bedrooms, on the plans given."""

    def __init__(self, bedrooms: int, plans: tuple[Plan, ...] = SECOND) -> None:
        super().__init__(side_px=40.0, bedrooms=bedrooms)
        self.found = self.found.model_copy(update={"plans": plans})


def read(inner: Fixed, facts: tuple[PrintedFact, ...], answers: bool = True) -> Extracted:
    reader = Reader(PrintedSheet(printed_facts=facts))
    return PrintedScale(PriorScale(inner), reader, Files(png(None)), answers=answers).extract(
        FILE, SHEET
    )


def drawing_of(found: Extracted) -> Drawing:
    """Stage 8 as ingest runs it: the entries, then the printed answers on them."""
    compared = answered(second_count(measured(found), found.printed), found.printed_answers)
    return Drawing(file=FILE.path, pages=SHEET.pages, scale=found.scale, plans=found.plans,
                   elements=found.elements, rooms=found.rooms, conflicts=tuple(compared),
                   read=found.read)  # fmt: skip


class Bedrooms:
    def parse(self, text: str) -> Query | Unsupported:
        return Query(subject="room:bedroom")


def bedrooms(found: Extracted) -> Quantity:
    drawing = drawing_of(found)
    return take_off(drawing, apply_rules(drawing.marks_by_quantity()))["room:bedroom"]


def test_t2_the_printed_count_of_the_sheets_floor_is_the_answer_and_the_drawn_one_stays() -> None:
    found = bedrooms(read(Planned(40), T2))
    assert found.value == 48
    assert found.conflict is not None and found.conflict.resolution is not None
    assert [(v.value, v.method) for v in found.conflict.values] == [
        (40, "detector"),
        (48, "printed_total"),
    ]
    assert found.conflict.resolution.rule == (
        "printed on the sheet: SECOND FLOOR = 48 DORMS (40 drawn)"
    )
    assert found.marks and found.marks[0].box == T2[1].box  # the printed text is the evidence


def test_off_keeps_the_count_read_off_the_drawing() -> None:
    found = bedrooms(read(Planned(40), T2, answers=False))
    assert found.value == 40 and found.conflict is not None
    assert found.conflict.resolution is None


def test_the_answer_card_says_both_numbers() -> None:
    drawing = drawing_of(read(Planned(40), T2))
    quantities = take_off(drawing, apply_rules(drawing.marks_by_quantity()))
    question = Question(id=1, file=FILE.path, text="How many bedrooms are there?")
    answer = answer_question(question, quantities, Bedrooms(), iter(range(9)).__next__, NoPrior())
    assert answer.answer == 48 and not answer.abstain
    assert answer.explanation is not None and "40" in answer.explanation
    assert "SECOND FLOOR = 48 DORMS" in answer.explanation
    assert answer.conflicts is not None and {c.value for c in answer.conflicts} == {40, 48}


@pytest.mark.parametrize(
    ("facts", "plans", "why"),
    [
        ((dorms("FIRST FLOOR = 48 DORMS"),), SECOND, "another floor's count"),
        ((dorms("TOTAL = 144 DORMS", 144), dorms("FIRST FLOOR = 48 DORMS")), SECOND,
         "the building's total, beside a floor's"),
        ((dorms("SECOND FLOOR = 48 DORMS"), dorms("SECOND FLOOR: 46 DORMS", 46)), SECOND,
         "two printed values that disagree"),
        ((dorms("48 DORMS"),),
         (*SECOND, Plan(id="p2", page=1, box=(0, 0, 1, 1), storey="THIRD FLOOR")),
         "a sheet of two floors"),
        ((dorms("SECOND FLOOR = 48 DORMS"),), (), "a sheet whose floor is not known"),
        ((dorms("WEST WING = 48 DORMS"),), SECOND, "one wing of the floor"),
        ((dorms("SECOND FLOOR = 48 ROOMS", subject="room"),), SECOND,
         "all rooms, not the bedrooms asked"),
    ],
)  # fmt: skip
def test_a_partial_match_keeps_the_count_read(
    facts: tuple[PrintedFact, ...], plans: tuple[Plan, ...], why: str
) -> None:
    found = bedrooms(read(Planned(40, plans), facts))
    assert found.value == 40, why
    assert found.conflict is None or found.conflict.resolution is None, why


def test_a_sheet_level_count_on_a_one_floor_sheet_is_the_answer() -> None:
    assert bedrooms(read(Planned(40), (dorms("48 DORMS"),))).value == 48
    unnamed = (Plan(id="p1", page=1, box=(0, 0, 1, 1)),)  # one plan, no storey: the sheet's
    assert bedrooms(read(Planned(40, unnamed), (dorms("TOTAL 48 DORMS"),))).value == 48


def test_a_printed_count_that_agrees_changes_nothing() -> None:
    found = bedrooms(read(Planned(48), T2))
    assert found.value == 48
    assert found.conflict is None or found.conflict.status == "agree"


def test_a_printed_count_of_an_element_class_is_the_answer_too() -> None:
    facts = (PrintedFact(text="SECOND FLOOR: 12 DOORS", subject="door", value=12, unit="count"),)
    drawing = drawing_of(read(Planned(1), facts))
    doors = take_off(drawing, apply_rules(drawing.marks_by_quantity()))["door"]
    assert doors.value == 12 and doors.conflict is not None


@pytest.mark.parametrize("method", ["detector", "parser", "plan_drawing"])
def test_the_rule_is_the_same_whatever_read_the_sheet(method: str) -> None:
    """related.md #3: a drawn (vector) sheet's printed count gets the same rule as a scan's; only
    the raster route has a printed-count reader today, so this checks the core function."""
    found = Planned(40).found.model_copy(update={"method": method})
    marked = printed_answers(found, T2)
    ((answer,),) = [marked.printed_answers]
    assert answer.measurement.value.value == 48 and answer.text == "SECOND FLOOR = 48 DORMS"


def test_ingest_reports_the_printed_count() -> None:
    around = Around()
    reader = PrintedScale(PriorScale(Planned(40)), Reader(PrintedSheet(printed_facts=T2)),
                          Files(png(None)), answers=True)  # fmt: skip
    ingest([FILE.path], files=around, finder=around, pages=around,
           extractors={"raster": reader}, second_counter=around, sink=around)  # fmt: skip
    (drawing,) = around.drawings
    (entry,) = [c for c in drawing.conflicts or () if c.quantity == "room_count"]
    assert entry.status == "conflict" and entry.resolution is not None
    assert entry.resolution.value == 48


def test_the_setting_is_off_by_default_and_part_of_the_reuse_key_only_when_on(
    tmp_path: Path,
) -> None:
    assert Settings(_env_file=None).printed_total_answers == "off"  # pyright: ignore[reportCallIssue]

    def names(**on: str) -> dict[str, str]:
        key = {"gemini_api_key": "unused", "raster_printed_scale": "carbon"}
        settings = Settings(_env_file=None, **key, **on)  # pyright: ignore[reportCallIssue]
        service = build_ingest(settings, tmp_path / "projects", background=False)
        service.close()
        return service._names  # pyright: ignore[reportPrivateUsage]

    assert "printed_total_answers" not in names()
    assert names(printed_total_answers="on")["printed_total_answers"] == "on"

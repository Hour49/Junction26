"""Partial totals (label-area task 2, fable-rooms item 6): a room total over the rooms a reader
picked off a picture keeps its value, says it is the sum of the rooms found and which rooms
another source names that it lacks, and is Low (app/core/pipeline/takeoff.py `_mark_partial`,
app/core/answering/answer.py `partial_text`, app/core/review/ask.py, app/api/ask.py)."""

from app.adapters.answer_prior import NoPrior
from app.adapters.question_templates import TemplateParser
from app.api.ask import partial_fields
from app.core.drawing.model import Drawing, Page, Room, Scale, Table, TableRow
from app.core.pipeline.model import Partial
from app.core.pipeline.takeoff import known_quantities
from app.core.review.ask import Asked, ask
from app.core.review.check import CheckPolicy, Counts
from app.core.review.model import ReviewState

PAGE = Page(page=1, width=100, height=100, unit="px")
SCALE = Scale(status="estimated", m_per_unit=0.05, uncertainty=0.1)
POLICY = CheckPolicy(
    thresholds={"door": 0.8},
    counts={"high": Counts(units=10, exact=10), "medium": Counts(units=10, exact=9),
            "low": Counts(units=10, exact=5)},
)  # fmt: skip
TOTAL = "What is the total area of all rooms?"


def room(at: int, label: str, area: float, reader: bool = True) -> Room:
    return Room(
        id=f"r{at}",
        type="other",
        label=label,
        page=1,
        box=(0.1 * at, 0.1, 0.1 * at + 0.05, 0.2),
        area_m2=area,
        area_status="exact",
        area_source="printed",
        attrs={"reader": "gemini"} if reader else {},
    )


def drawing(rooms: tuple[Room, ...], tables: tuple[Table, ...] | None = None) -> Drawing:
    return Drawing(file="scan.png", pages=(PAGE,), scale=SCALE, rooms=rooms, tables=tables)


SCHEDULE = Table(
    id="t1",
    page=1,
    box=(0.0, 0.8, 1.0, 1.0),
    title="ROOM SCHEDULE",
    columns=("NO.", "ROOM NAME", "AREA"),
    rows=tuple(
        TableRow(cells=cells)
        for cells in (("101", "OFFICE", "10"), ("102", "HALL", "5"), ("104", "LOBBY", "20"),
                      ("107", "STAIR", "8"), ("108", "STOR", "3"), ("109", "WC", "2"))
    ),
)  # fmt: skip
READ = (room(1, "OFFICE", 10.0), room(2, "HALL", 5.5))


def asked(shown: Drawing, check: CheckPolicy | None = POLICY) -> Asked:
    return ask(
        TOTAL, shown, parser=TemplateParser(), clock=lambda: 0.0, prior=NoPrior(),
        state=ReviewState(), check=check, raster=True, route="raster",
    )  # fmt: skip


def test_a_total_of_rooms_a_reader_found_is_partial_and_keeps_its_value() -> None:
    found = known_quantities(drawing(READ))
    assert found["area:room"].value == 15.5
    assert found["area:room"].partial == Partial(counted=2)
    assert found["area:room|indoor"].partial == Partial(counted=2)
    assert found["area:room|label=office"].partial is None  # one room by its label: not a total


def test_a_complete_room_list_is_not_partial_unless_a_schedule_names_rooms_it_lacks() -> None:
    vector = tuple(r.model_copy(update={"attrs": {}}) for r in READ)
    assert known_quantities(drawing(vector))["area:room"].partial is None
    found = known_quantities(drawing(vector, (SCHEDULE,)))["area:room"]
    assert found.partial is not None
    assert found.partial.missing == ("104 LOBBY", "107 STAIR", "108 STOR", "109 WC")


def test_the_answer_says_it_is_the_sum_of_the_rooms_found_and_names_a_few_missing() -> None:
    got = asked(drawing(READ, (SCHEDULE,)))
    assert got.answer.answer == 15.5
    assert got.answer.explanation == (
        "This is the sum of the 2 rooms the reader found; rooms it missed are not in it. "
        "Not in it: 104 LOBBY, 107 STAIR, 108 STOR and 1 more."
    )
    assert got.level is not None and got.level.level == "low"
    assert got.level.text.startswith("Low confidence: This is the sum of the 2 rooms")
    assert got.answer.sure is False and got.check is not None
    assert partial_fields(got) == {
        "partial": True,
        "rooms_counted": 2,
        "rooms_missing": ["104 LOBBY", "107 STAIR", "108 STOR", "109 WC"],
    }


def test_a_total_that_is_not_partial_has_no_partial_fields() -> None:
    vector = tuple(r.model_copy(update={"attrs": {}}) for r in READ)
    got = asked(drawing(vector))
    assert got.answer.answer == 15.5 and got.answer.explanation is None
    assert got.partial is None and partial_fields(got) == {}

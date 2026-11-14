"""Partial totals (label-area task 2, fable-rooms item 6): a room total over the rooms a reader
picked off a picture keeps its value, says it is the sum of the rooms found and which rooms
another source names that it lacks, and is Low (app/core/pipeline/takeoff.py `_mark_partial`,
app/core/answering/answer.py `partial_text`, app/core/review/ask.py, app/api/ask.py)."""

import pytest

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
        attrs={"number": f"10{at}", **({"reader": "gemini"} if reader else {})},
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
                      ("107", "STAIR", "8"), ("108", "STOR", "3"), ("109", "WC", "2"),
                      ("201", "GYM", "40"))  # another storey's room: never missing
    ),
)  # fmt: skip
READ = (room(1, "OFFICE", 10.0), room(2, "HALL", 5.5))


FINISH_KEY = Table(
    id="t2",
    page=1,
    box=(0.0, 0.6, 1.0, 0.8),
    title="FINISH KEY",
    columns=("KEY", "MATERIAL", "MANUFACTURER"),
    rows=tuple(TableRow(cells=(key, "PAINT", "ACME")) for key in ("B1", "B2", "C1")),
)  # A-801's finish key: finish codes, not rooms


def asked(shown: Drawing, check: CheckPolicy | None = POLICY, route: str = "raster") -> Asked:
    return ask(
        TOTAL, shown, parser=TemplateParser(), clock=lambda: 0.0, prior=NoPrior(),
        state=ReviewState(), check=check, raster=route == "raster", route=route,
    )  # fmt: skip


VECTOR = tuple(r.model_copy(update={"attrs": {"number": r.attrs["number"]}}) for r in READ)


def test_a_total_of_rooms_a_reader_found_is_partial_and_keeps_its_value() -> None:
    found = known_quantities(drawing(READ))
    assert found["area:room"].value == 15.5
    assert found["area:room"].partial == Partial(counted=2)
    assert found["area:room|indoor"].partial == Partial(counted=2)
    assert found["area:room|label=office"].partial is None  # one room by its label: not a total


def test_a_complete_room_list_is_not_partial_unless_a_schedule_names_rooms_it_lacks() -> None:
    vector = VECTOR
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
    vector = VECTOR
    got = asked(drawing(vector))
    assert got.answer.answer == 15.5 and got.answer.explanation is None
    assert got.partial is None and partial_fields(got) == {}


# Numeric codes on the sheet's storey (its rooms are 101, 102): only the columns keep them out
NUMERIC_KEY = FINISH_KEY.model_copy(
    update={"rows": tuple(TableRow(cells=(key, "PAINT", "ACME")) for key in ("110", "111"))}
)
NUMBERED = NUMERIC_KEY.model_copy(update={"title": None, "columns": ("NO.", "MATERIAL", "MAKE")})


@pytest.mark.parametrize("table", [FINISH_KEY, NUMERIC_KEY, NUMBERED], ids=["codes", "key", "no"])
def test_a_table_without_a_room_column_is_not_a_room_schedule(table: Table) -> None:
    assert known_quantities(drawing(VECTOR, (table,)))["area:room"].partial is None


def test_the_sentence_names_the_table_that_lists_more_rooms() -> None:
    door = SCHEDULE.model_copy(update={"title": "DOOR SCHEDULE"})
    untitled = SCHEDULE.model_copy(update={"title": None})
    door_said = asked(drawing(VECTOR, (door,)), route="vector").answer.explanation or ""
    untitled_said = asked(drawing(VECTOR, (untitled,)), route="vector").answer.explanation or ""
    assert "; the DOOR SCHEDULE lists more: 104 LOBBY" in door_said
    assert "; a schedule on the sheet lists more: 104 LOBBY" in untitled_said


def test_a_vector_total_a_schedule_shows_partial_is_never_certified() -> None:
    vector_sure = POLICY.model_copy(update={"routes": frozenset({"vector"})})
    got = asked(drawing(VECTOR, (SCHEDULE, FINISH_KEY)), vector_sure, route="vector")
    assert got.answer.explanation == (
        "This is the sum of the 2 rooms drawn on the sheet; the ROOM SCHEDULE lists more: "
        "104 LOBBY, 107 STAIR, 108 STOR and 1 more."
    )
    assert got.answer.sure is False and got.check is not None
    assert got.level is None or got.level.level == "low"


def test_a_schedule_s_rows_count_only_on_the_sheet_s_storey() -> None:
    no_numbers = tuple(r.model_copy(update={"attrs": {}}) for r in READ)
    assert known_quantities(drawing(no_numbers, (SCHEDULE,)))["area:room"].partial is None


# --- refused partial (fail-1 S1 on #349): a refused room box keeps the sheet total ------------


def boxed(at: int, label: str, box: tuple[float, float, float, float]) -> Room:
    """A room a reader boxed, with no area of its own yet."""
    return Room(id=f"b{at}", type="other", label=label, page=1, box=box, attrs={"reader": "gemini"})


def measured(rooms: tuple[Room, ...], scale: Scale = SCALE) -> Drawing:
    """The rooms measured at `scale` as the raster route does (refused boxes get no area)."""
    from app.core.pipeline.raster_scale import rooms_with_areas

    got, _ = rooms_with_areas(rooms, scale, [PAGE])
    return Drawing(file="scan.png", pages=(PAGE,), scale=scale, rooms=tuple(got))


HALLS = (boxed(1, "OFFICE", (0.0, 0.0, 0.5, 0.5)), boxed(2, "HALL", (0.5, 0.0, 1.0, 0.5)))
LOBBY = boxed(3, "LOBBY", (0.1, 0.6, 0.22, 0.66))  # 0.6 x 0.3 m at 0.05 m/px: 0.18 m²


def test_refused_partial_a_refused_room_keeps_the_total_partial_and_named() -> None:
    from app.core.pipeline.raster_scale import AREA_REFUSED

    lobby_two = boxed(4, "LOBBY", (0.5, 0.6, 1.0, 1.0))  # a second lobby, a room-sized box
    shown = measured((*HALLS, LOBBY, lobby_two))
    lobby = shown.rooms[2]
    assert lobby.area_m2 is None and "smaller than any room" in str(lobby.attrs[AREA_REFUSED])
    found = known_quantities(shown)
    kept = [shown.rooms[at].area_m2 or 0.0 for at in (0, 1, 3)]
    assert found["area:room"].value == pytest.approx(sum(kept))
    assert found["area:room"].partial == Partial(counted=3, refused=("LOBBY",))
    assert found["area:room|indoor"].partial == Partial(counted=3, refused=("LOBBY",))
    assert "area:room|label=lobby" not in found  # a sum by label stays unknown, as before
    got = asked(shown)
    assert (  # after the estimate's own sentence
        "This is the sum of the 3 rooms with a measured area; not measured: LOBBY (its box "
        "cannot be the room); rooms the reader missed are not in it either."
    ) in (got.answer.explanation or "")
    assert got.level is not None and got.level.level == "low" and got.answer.sure is False


def test_refused_partial_the_api_lists_refused_rooms_as_missing_after_the_schedule_s_once() -> None:
    got = asked(measured((*HALLS, LOBBY)))
    assert partial_fields(got) == {"partial": True, "rooms_counted": 2, "rooms_missing": ["LOBBY"]}
    both = Partial(counted=2, missing=("104 LOBBY", "107 STAIR"), refused=("LOBBY", "107 STAIR"))
    assert partial_fields(got.model_copy(update={"partial": both})) == {
        "partial": True,
        "rooms_counted": 2,
        "rooms_missing": ["104 LOBBY", "107 STAIR", "LOBBY"],  # in order, no repeat
    }


def test_refused_partial_a_room_without_an_area_that_was_not_refused_still_gives_no_total() -> None:
    unmeasured = room(3, "LOBBY", 1.0).model_copy(update={"area_m2": None})
    found = known_quantities(drawing((*READ, unmeasured)))
    assert "area:room" not in found and "area:room|indoor" not in found


def test_refused_partial_a_room_refused_at_a_replaced_scale_is_measured_again() -> None:
    from app.core.pipeline.raster_scale import AREA_REFUSED, rooms_with_areas

    small = measured((*HALLS, LOBBY))  # refused at 0.05 m/px
    larger = Scale(status="scaled", m_per_unit=0.2, evidence=("scale_bar",))  # 0.72 m²: a room
    again, _ = rooms_with_areas(small.rooms, larger, [PAGE])
    assert again[2].area_m2 is not None and AREA_REFUSED not in again[2].attrs

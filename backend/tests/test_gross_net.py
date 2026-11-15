"""GROSS_NET_CHECK: a floor area the sheet prints (gross, to the outside walls) against the rooms
found summed (net, inside walls). Outside NET_TO_GROSS the indoor area answer keeps the net number,
shows the gross as the other value with a note, and is held for a person; inside it the gross is
only a note. A fake reader stands in for the Carbon call. Synthetic."""

from pathlib import Path

import pytest
from test_answering import NoPrior
from test_printed_scale import FILE, PAGE, SHEET, Files, Reader, png

from app.adapters.printed_scale import PrintedScale
from app.composition import build_ingest
from app.core.answering.answer import answer_question
from app.core.answering.model import Answer, Query, Question, Unsupported
from app.core.drawing.model import Attr, Drawing, Room, Scale
from app.core.pipeline.gross_net import (
    NET_TO_GROSS,
    gross_net_checked,
    net_area,
    printed_gross,
)
from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from app.core.pipeline.printed import PrintedFact, PrintedSheet
from app.core.pipeline.raster_scale import AREA_REFUSED
from app.core.pipeline.second_count import measured, second_count
from app.core.pipeline.takeoff import known_quantities
from app.settings import Settings

BOX = (0.6, 0.6, 0.9, 0.62)
# T2's area table as the Carbon reader gives it (us_daf dorm p003, ft² in m²), trimmed: wing
# totals are "other", circulation "room:hall", the floor's subtotal and total floor_area
T2_FACTS = (
    PrintedFact(text="SECOND FLOOR = 48 DORMS", subject="room:bedroom", value=48, unit="count"),
    PrintedFact(text="WEST WING CIRCULATION = 914 SF", subject="room:hall", value=84.91, unit="m2"),
    PrintedFact(text="TOTAL WEST WING = 7,009 SF", subject="other", value=651.16, unit="m2"),
    PrintedFact(text="SUBTOTAL 26,181 SF", subject="floor_area", value=2432.29, unit="m2"),
    PrintedFact(text="EXTERIOR STAIR (1/2 SF) 381 SF", subject="room:shaft", value=35.4, unit="m2"),
    PrintedFact(text="TOTAL SECOND FLOOR = 26,562 SF", subject="floor_area", value=2467.68,
                unit="m2", box=BOX),
)  # fmt: skip


def room(id_: str, area: float | None, outdoor: bool = False, refused: bool = False) -> Room:
    attrs: dict[str, Attr] = {AREA_REFUSED: "too small"} if refused else {}
    return Room(id=id_, type="other", page=1, box=(0.1, 0.1, 0.2, 0.2), area_m2=area,
                outdoor=outdoor, attrs=attrs)  # fmt: skip


def gross_m2(m2: float) -> tuple[PrintedFact, ...]:
    return (PrintedFact(text=f"GROSS FLOOR AREA {m2:g} m2", subject="other", value=m2, unit="m2",
                        box=BOX),)  # fmt: skip


def extracted(*rooms: Room) -> Extracted:
    return Extracted(method="detector", scale=Scale(status="no_scale"), rooms=rooms)


@pytest.mark.parametrize(
    ("facts", "picked"),
    [
        (T2_FACTS, ("TOTAL SECOND FLOOR = 26,562 SF", 2467.68)),  # the largest total
        (gross_m2(300), ("GROSS FLOOR AREA 300 m2", 300.0)),  # GROSS in the text
        ((PrintedFact(text="1200 m2", subject="floor_area", value=1200, unit="m2"),),
         ("1200 m2", 1200.0)),  # floor_area alone
        (T2_FACTS[:2], None),  # a room type's area and a count: no total of the floor
        ((PrintedFact(text="TOTAL 40", subject="other", value=40, unit="other"),), None),
        ((PrintedFact(text="TOTAL 0 m2", subject="floor_area", value=0, unit="m2"),), None),
        ((), None),
    ],
)  # fmt: skip
def test_printed_gross_is_the_largest_area_total_in_square_metres(
    facts: tuple[PrintedFact, ...], picked: tuple[str, float] | None
) -> None:
    got = printed_gross(facts)
    if picked is None:
        assert got is None
    else:
        assert got is not None
        assert (got[1].text, got[0]) == (picked[0], pytest.approx(picked[1]))


@pytest.mark.parametrize(
    ("rooms", "net"),
    [
        ((room("a", 10), room("b", 20)), 30.0),
        ((room("a", 10), room("b", 20, outdoor=True)), 10.0),  # a balcony is not indoor
        ((room("a", 10), room("b", None, refused=True)), 10.0),  # a refused box is left out
        ((room("a", 10), room("b", None)), None),  # any other room without an area: unknown
        ((room("b", None, outdoor=True), room("a", 10)), 10.0),  # an outdoor one never counts
        ((room("b", None, refused=True),), None),  # nothing left to sum
        ((), None),
    ],
)
def test_net_area_is_the_indoor_rooms_as_the_takeoff_sums_them(
    rooms: tuple[Room, ...], net: float | None
) -> None:
    assert net_area(rooms) == net


@pytest.mark.parametrize(
    ("net", "flagged"),
    [(59.0, True), (60.0, False), (80.0, False), (102.0, False), (103.0, True), (45.0, True)],
)
def test_only_a_ratio_outside_the_band_becomes_a_floor_area_conflict(
    net: float, flagged: bool
) -> None:
    found = gross_net_checked(extracted(room("a", net)), gross_m2(100))
    pair = [(m.quantity, m.subject.kind, m.value.value, m.value.method) for m in found.printed]
    said = f"the rooms found sum to {net:,.0f} m² (inside walls), {net:.0f}% of it"
    if flagged:
        assert pair == [("floor_area", "sheet", net, "summed_rooms"),
                        ("floor_area", "sheet", 100.0, "printed_total")]  # fmt: skip
        assert found.printed[1].value.box == BOX and found.printed[1].value.page == 1
        assert said in (found.printed[1].note or "") and found.printed[0].note is None
    else:
        assert pair == []
    (note,) = [n for n in found.notes if n.startswith("the sheet prints a gross area")]
    assert note.startswith('the sheet prints a gross area of 100 m² ("GROSS FLOOR AREA 100 m2", '
                           "to the outside walls); " + said)  # fmt: skip
    assert NET_TO_GROSS == (0.60, 1.02)


def test_no_printed_total_or_no_net_leaves_the_reading_as_it_is() -> None:
    plain = extracted(room("a", 10))
    assert gross_net_checked(plain, T2_FACTS[:2]) is plain
    unknown = extracted(room("a", None))
    assert gross_net_checked(unknown, gross_m2(100)) is unknown


class IndoorArea:
    def parse(self, text: str) -> Query | Unsupported:
        return Query(measure="area", subject="room", indoor=True)


def ask(found: Extracted) -> Answer:
    drawing = Drawing(file=FILE.path, pages=(PAGE,), scale=found.scale, rooms=found.rooms,
                      conflicts=tuple(second_count(measured(found), found.printed)))  # fmt: skip
    question = Question(id=1, file=FILE.path, text="What is the total indoor area?")
    return answer_question(question, known_quantities(drawing), IndoorArea(),
                           iter(range(9)).__next__, NoPrior())  # fmt: skip


def test_t2_the_indoor_area_keeps_the_net_number_and_is_held_with_the_gross_beside_it() -> None:
    """Pass line 1: the answer's value stays the rooms' sum, the printed gross is the other
    value, no rule decides (a person does), and the note says which is which."""
    gross = 2467.68
    found = gross_net_checked(extracted(room("a", 700.0), room("b", 411.0)), T2_FACTS)
    answer = ask(found)
    assert answer.answer == 1111.0 and answer.abstain is True
    assert [(v.value, v.method) for v in answer.conflicts or ()] == [
        (1111.0, "summed_rooms"),
        (pytest.approx(gross), "printed_total"),
    ]
    assert "no rule decides" in (answer.explanation or "")
    assert "the sheet prints a gross area of 2,468 m²" in (answer.explanation or "")
    assert "(inside walls), 45% of it" in (answer.explanation or "")


def test_inside_the_band_the_answer_is_unchanged() -> None:
    found = gross_net_checked(extracted(room("a", 80.0)), gross_m2(100))
    answer = ask(found)
    assert (answer.answer, answer.abstain, answer.conflicts) == (80.0, None, None)


class Fixed:
    def __init__(self, *rooms: Room) -> None:
        self.found = extracted(*rooms)

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        return self.found


@pytest.mark.parametrize("on", [False, True])
def test_printed_scale_checks_gross_against_net_only_when_on(on: bool) -> None:
    printed = PrintedSheet(printed_facts=gross_m2(300))
    reader = PrintedScale(Fixed(room("a", 100.0)), Reader(printed), Files(png(None)),
                          gross_net=on)  # fmt: skip
    found = reader.extract(FILE, SHEET)
    assert [m.quantity for m in found.printed] == (["floor_area", "floor_area"] if on else [])


def test_the_setting_is_off_by_default_and_part_of_the_reuse_key_only_when_on(
    tmp_path: Path,
) -> None:
    assert Settings(_env_file=None).gross_net_check == "off"  # pyright: ignore[reportCallIssue]

    def names(**on: str) -> dict[str, str]:
        key = {"gemini_api_key": "unused", "raster_printed_scale": "carbon"}
        settings = Settings(_env_file=None, **key, **on)  # pyright: ignore[reportCallIssue]
        service = build_ingest(settings, tmp_path / "projects", background=False)
        service.close()
        return service._names  # pyright: ignore[reportPrivateUsage]

    assert "gross_net_check" not in names()
    assert names(gross_net_check="on")["gross_net_check"] == "on"

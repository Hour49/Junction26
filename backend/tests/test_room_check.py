"""Rooms: the room schedule's numbers against the room tags (a name above a number) on a set's
plans (TABLES=pdf, stage 8). The sets are drawn here; no partner data."""

import ctypes

import pypdfium2.raw as raw
from pdf_sheets import SheetPdf
from test_pdf_tables import ruled
from test_schedule_check import Files, itself, joined

from app.adapters.hello import HelloSecondCounter
from app.adapters.pdf_tables.room_check import rooms
from app.adapters.pdf_tables.schedule_check import ScheduleTagCounter
from app.adapters.pdf_tables.set_pages import PdfSet
from app.core.pipeline.second_count import second_count

XS = (20.0, 80.0, 180.0)


class Sheet(SheetPdf):
    def upward(self, text: str, x: float, y: float, size: float = 6.0) -> None:
        """A text object that reads upwards from (x, y), its letters' tops to the left."""
        obj = raw.FPDFPageObj_NewTextObj(self._document.raw, b"Helvetica", size)
        encoded = (text + "\x00").encode("utf-16-le")
        buffer = ctypes.create_string_buffer(encoded, len(encoded))
        raw.FPDFText_SetText(obj, ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ushort)))
        raw.FPDFPageObj_Transform(obj, 0, 1, -1, 0, x, self.height - y)
        raw.FPDFPage_InsertObject(self._page.raw, obj)


def room_schedule(*rows: tuple[str, str], number: str = "Number") -> SheetPdf:
    """A room schedule: title, a <number> | Name header, one row per room."""
    sheet = SheetPdf()
    ys = (20.0, 35.0, 50.0, *(62.0 + 12 * n for n in range(len(rows))))
    ruled(sheet, XS, ys, no_down=frozenset({(0, 1)}))
    sheet.text("ROOM SCHEDULE", 60, 32)
    sheet.text(number, XS[0] + 2, 47)
    sheet.text("Name", XS[1] + 2, 47)
    for (room, name), bottom in zip(rows, ys[3:], strict=True):
        sheet.text(room, XS[0] + 2, bottom - 3)
        sheet.text(name, XS[1] + 2, bottom - 3)
    return sheet


def plan() -> Sheet:
    sheet = Sheet()
    sheet.path([(10, 10), (590, 10), (590, 390), (10, 390), (10, 10)])
    for name, number, x in (("OFFICE", "101", 100), ("LOBBY", "102", 200), ("CLOSET", "104", 300)):
        sheet.text(name, x, 95)
        sheet.text(number, x + 3, 105)
    sheet.text("103", 400, 200)  # a number with no name above: no tag (a ceiling plan's, a note's)
    # a long name centred on the whole tag line "105 - (22 SF)", not on the number
    sheet.text("BASEMENT STAIR", 118, 240)
    sheet.text("105", 100, 250)
    sheet.text("- (22 SF)", 111.5, 250)
    # a tag turned to read upwards: its name is to the number's left
    sheet.upward("STORAGE", 492, 300)
    sheet.upward("106", 502, 300)
    return sheet


SCHEDULE = room_schedule(
    ("101", "OFFICE"),
    ("102", "LOUNGE"),
    ("103", "STORAGE"),
    ("105", "BASEMENT STAIR"),
    ("106", "STORAGE"),
    ("107", "MECH."),
)


def test_rooms_scheduled_and_tagged_are_compared_room_by_room() -> None:
    found = rooms(PdfSet(joined(plan(), SCHEDULE)))
    assert found is not None
    assert sorted(found.named) == ["101", "102", "104", "105", "106"]
    assert found.undrawn == ["103", "107"]
    assert found.unscheduled == ["104"]
    assert found.renamed == ["102"]
    assert found.note() == (
        "room schedule (page 2, 6 rooms) against the room tags on pages 1 (5 rooms): on the "
        "schedule, tagged on no plan: 103, 107; tagged, not on the schedule: 104; named "
        "differently (schedule / plan): 102 LOUNGE / LOBBY"
    )


def test_the_two_room_counts_are_a_conflict_no_rule_resolves() -> None:
    pdf = joined(plan(), SCHEDULE)
    source, sheet = itself(pdf)
    measured = ScheduleTagCounter(HelloSecondCounter(), Files(source, pdf)).measure(source, sheet)
    (entry,) = second_count([], measured)
    assert (entry.quantity, entry.subject.kind, entry.subject.ref) == ("room_count", "sheet", None)
    assert entry.status == "conflict" and entry.resolution is None
    assert [(v.method, v.value, v.page) for v in entry.values] == [
        ("schedule", 6, 2),
        ("plan_drawing", 5, None),
    ]


def test_no_check_without_numbers_or_with_short_ones() -> None:
    assert rooms(PdfSet(joined(plan(), room_schedule(("101", "OFFICE"), number="Area")))) is None
    short = room_schedule(("1", "OFFICE"), ("2", "LOBBY"))
    assert rooms(PdfSet(joined(plan(), short))) is None
    assert rooms(PdfSet(SCHEDULE.pdf())) is None  # a schedule sheet alone

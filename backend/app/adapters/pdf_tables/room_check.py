"""Rooms: the room (finish) schedule's room numbers against the room tags of the plans in the same
PDF (a schedule rule, schedule_check.py).

A room schedule is a table whose title says "room" and that is no legend, with a column of room
numbers ("Room Number", "Number") and one of names. A room tag on a plan is the room's name with
its number below: a text object whose whole text has the shape of a scheduled number (tags.py),
with a text of letters right above it. A number with no name above is no tag (a ceiling plan's
bare numbers, a dimension, the project number), so a room only those show is not drawn.

What is compared, per set: rooms on the schedule no plan tags, tags of numbers the schedule does
not have, and rooms whose tags never give the schedule's name.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass, replace

from app.adapters.pdf_tables import tags
from app.adapters.pdf_tables.set_pages import PdfSet
from app.adapters.vector_pdf.objects import Bounds, PdfText
from app.core.drawing.model import MeasuredValue, Subject, Table
from app.core.pipeline.model import Measurement

SCHEDULE_PAGE = re.compile(r"room", re.IGNORECASE)
SCHEDULE_WORD = re.compile(r"schedul", re.IGNORECASE)
NUMBER_HEADER = re.compile(r"number|^no\.?$|^#$", re.IGNORECASE)
NAME_HEADER = re.compile(r"name", re.IGNORECASE)
LETTERS = re.compile(r"[A-Za-z]{2,}")
MIN_NUMBER = 3  # "1" or "12" has the shape of too much else under a word on a plan
NAME_GAP = 2.5  # a name line sits at most this many text heights above the line below it
NAME_LINES = 3


@dataclass(frozen=True)
class RoomCheck:
    schedule_page: int
    schedule: Table
    rooms: dict[str, str]  # number -> name, as the schedule lists them
    named: dict[str, set[str]]  # number -> the names its tags give
    pages: tuple[int, ...]  # the pages with a room tag

    @property
    def undrawn(self) -> list[str]:
        return [number for number in self.rooms if number not in self.named]

    @property
    def unscheduled(self) -> list[str]:
        return sorted(number for number in self.named if number not in self.rooms)

    @property
    def renamed(self) -> list[str]:
        """Scheduled rooms none of whose tags gives the schedule's name (a tag's name may have a
        note stacked above it, so the schedule's name may be its end)."""
        return [
            number
            for number, name in self.rooms.items()
            if number in self.named
            and not any(_same(name) in _same(given) for given in self.named[number])
        ]

    def measurements(self) -> list[Measurement]:
        """The rooms as the schedule lists them and as the plans tag them."""
        sheet = Subject(kind="sheet", ref=None)
        return [
            Measurement(
                quantity="room_count",
                subject=sheet,
                value=MeasuredValue(
                    value=len(self.rooms),
                    unit="rooms",
                    method="schedule",
                    page=self.schedule_page,
                    box=self.schedule.box,
                ),
            ),
            Measurement(
                quantity="room_count",
                subject=sheet,
                value=MeasuredValue(value=len(self.named), unit="rooms", method="plan_drawing"),
            ),
        ]

    def note(self) -> str:
        """What differs, room by room, for the drawing's notes."""

        def listed(numbers: Sequence[str]) -> str:
            return ", ".join(numbers) if numbers else "none"

        renamed = [
            f"{number} {self.rooms[number]} / {' or '.join(sorted(self.named[number]))}"
            for number in self.renamed
        ]
        return (
            f"room schedule (page {self.schedule_page}, {len(self.rooms)} rooms) against the room "
            f"tags on pages {', '.join(map(str, self.pages))} ({len(self.named)} rooms): on the "
            f"schedule, tagged on no plan: {listed(self.undrawn)}; tagged, not on the schedule: "
            f"{listed(self.unscheduled)}; named differently (schedule / plan): {listed(renamed)}"
        )


def room_schedule(tables: Sequence[Table]) -> tuple[Table, int, int] | None:
    """The one room schedule with numbers among a page's tables, with its number and name
    columns, or None when there is none or several."""
    found: list[tuple[Table, int, int]] = []
    for table in tables:
        title = (table.title or "").casefold()
        if "room" not in title or any(word in title for word in tags.LEGEND_WORDS):
            continue
        number = _column(table, NUMBER_HEADER)
        name = _column(table, NAME_HEADER)
        if number is not None and name is not None:
            found.append((table, number, name))
    return found[0] if len(found) == 1 else None


def _column(table: Table, header: re.Pattern[str]) -> int | None:
    return next((n for n, text in enumerate(table.columns) if header.search(text.strip())), None)


def rooms(pdf: PdfSet) -> RoomCheck | None:
    """The room rule: None when the set has no single room schedule with numbers, a number is
    too short, or no page tags a room."""
    schedule: tuple[int, tuple[Table, int, int], list[Table]] | None = None
    for index, text in enumerate(pdf.text):
        if SCHEDULE_PAGE.search(text) and SCHEDULE_WORD.search(text):
            found = pdf.tables(index)
            table = room_schedule(found)
            if table is not None:
                if schedule is not None:
                    return None  # two room schedules: which one the plans follow is unclear
                schedule = (index + 1, table, found)
    if schedule is None:
        return None
    page_number, (table, number, name), page_tables = schedule
    listed = {
        " ".join(room.split()): " ".join((row.cells[name] or "").split())
        for row in table.rows
        if (room := row.cells[number]) is not None
    }
    if not listed or any(len(room) < MIN_NUMBER for room in listed):
        return None
    pattern = tags.shapes(listed)
    if pattern is None:
        return None
    named: dict[str, set[str]] = {}
    pages: list[int] = []
    for index in range(pdf.pages):
        page = pdf.objects(index)
        skip = (
            [tags.box_bounds(t.box, page.width, page.height) for t in page_tables]
            if index + 1 == page_number
            else []
        )
        tagged = False
        for tag in tags.tags_on(page.texts, index + 1, pattern, skip):
            above = name_above(tag.bounds, page.texts)
            if above is not None:
                named.setdefault(tag.mark, set()).add(above)
                tagged = True
        if tagged:
            pages.append(index + 1)
    if not named:
        return None
    return RoomCheck(page_number, table, listed, named, tuple(pages))


def name_above(bounds: Bounds, texts: Sequence[PdfText]) -> str | None:
    """The lines of letters stacked right above a text's line (a room tag's name), top line first.
    The text's line is the text with the texts next to it on its baseline ("127" "- (22 SF)"): a
    long name is centred on the whole line, not on the number."""
    if bounds[3] - bounds[1] > bounds[2] - bounds[0]:  # a tag turned to read upwards: its
        bounds = _turned(bounds)  # name is to its left, so read the page turned with it
        texts = [replace(text, bounds=_turned(text.bounds)) for text in texts]
    lines: list[str] = []
    below = line_of(bounds, texts)
    while len(lines) < NAME_LINES:
        height = below[3] - below[1]
        line = next(
            (
                text
                for text in texts
                if LETTERS.search(text.text)
                and -0.2 * height <= below[1] - text.bounds[3] <= NAME_GAP * height
                and text.bounds[0] < below[2]
                and below[0] < text.bounds[2]
                and text.bounds != below
            ),
            None,
        )
        if line is None:
            break
        lines.append(" ".join(line.text.split()))
        below = line.bounds
    return " ".join(reversed(lines)) or None


def line_of(bounds: Bounds, texts: Sequence[PdfText]) -> Bounds:
    """`bounds` grown by the texts that continue it on its baseline, each at most a text height
    from the last."""
    x0, y0, x1, y1 = bounds
    height = y1 - y0
    grown = True
    while grown:
        grown = False
        for text in texts:
            tx0, ty0, tx1, ty1 = text.bounds
            if abs((ty0 + ty1) / 2 - (y0 + y1) / 2) > height / 2 or (tx0 >= x0 and tx1 <= x1):
                continue
            if 0 <= tx0 - x1 <= height or 0 <= x0 - tx1 <= height:
                x0, x1, grown = min(x0, tx0), max(x1, tx1), True
    return x0, y0, x1, y1


def _turned(bounds: Bounds) -> Bounds:
    """Bounds on the page turned a quarter clockwise, so text that reads upwards reads across."""
    return -bounds[3], bounds[0], -bounds[1], bounds[2]


def _same(name: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", name.upper())

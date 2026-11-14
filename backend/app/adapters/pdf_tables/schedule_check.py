"""The schedules of a PDF set against what its plans draw (ingest stage 8).

A drawing set is often one PDF: the plans on some pages, the schedules on another. A schedule and
the plans' tags are two independent counts: what the schedule lists, and what the plans show.
`ScheduleTagCounter` wraps the route's `SecondCounter` and adds both counts of every rule that
could check the set, by `schedule` and by `plan_drawing` (docs/PIPELINE.md section 2: no rule,
both are shown). What differs, mark by mark, is in the drawing's notes (`PdfTables` adds them): a
conflict entry carries values, not lists.

The rules (`RULES`): doors here (the door schedule's marks against the door tags; tags.py says
what a tag is), window types (window_check.py) and rooms (room_check.py). Only a PDF read as
itself is checked (the boxes are its own pages'), and a rule that can't tell its tags from other
text checks nothing: a schedule sheet alone has no plan to compare with.
"""

import re
import threading
from collections import OrderedDict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from app.adapters.pdf_tables import room_check, tags, window_check
from app.adapters.pdf_tables.set_pages import PdfSet
from app.core.drawing.model import MeasuredValue, Subject, Table
from app.core.pipeline.model import DrawingFile, Measurement, Sheet
from app.core.pipeline.ports import DrawingFiles, SecondCounter

SCHEDULE_PAGE = re.compile(r"door", re.IGNORECASE)  # a page worth reading tables on also says
SCHEDULE_WORD = re.compile(r"schedul", re.IGNORECASE)  # "door" and "schedule"
# A mark of fewer characters ("D1", "01") or of digits only ("019", "101") has the shape of too much
# else on a plan: room numbers, keynotes, the project number in the title block.
MIN_MARK = 3
KEPT = 8  # sets whose checks are kept, so the extractor and the second counter read a set once


class Found(Protocol):
    """What one rule found on a set: its two counts and the note naming what differs."""

    def measurements(self) -> list[Measurement]: ...

    def note(self) -> str: ...


@dataclass(frozen=True)
class SetCheck:
    check: tags.Check
    pages: int  # pages in the PDF

    def measurements(self) -> list[Measurement]:
        return measurements(self)

    def note(self) -> str:
        return note(self)


def check_set(data: bytes) -> SetCheck | None:
    """The door rule on a PDF's bytes."""
    return doors(PdfSet(data))


def doors(pdf: PdfSet) -> SetCheck | None:
    """The door schedule of a PDF against the tags on its pages, or None when it has no single
    door schedule, its marks can't be told from other text, or no page tags a door."""
    schedule: tuple[int, Table] | None = None
    page_tables: list[Table] = []
    for index, text in enumerate(pdf.text):
        if SCHEDULE_PAGE.search(text) and SCHEDULE_WORD.search(text):
            found = pdf.tables(index)
            door = tags.door_schedule(found)
            if door is not None:
                if schedule is not None:
                    return None  # two door schedules: which one the plans follow is unclear
                schedule, page_tables = (index + 1, door), found
    if schedule is None:
        return None
    page_number, table = schedule
    marks = tags.marks_of(table)
    if not marks or any(len(mark) < MIN_MARK or mark.isdigit() for mark in marks):
        return None
    pattern = tags.shapes(marks)
    if pattern is None:
        return None
    found_tags: list[tags.Tag] = []
    for index in range(pdf.pages):
        page = pdf.objects(index)
        skip = (
            [tags.box_bounds(t.box, page.width, page.height) for t in page_tables]
            if index + 1 == page_number
            else []
        )
        found_tags += tags.tags_on(page.texts, index + 1, pattern, skip)
    if not found_tags:
        return None
    return SetCheck(tags.compare(page_number, table, found_tags), pdf.pages)


# The registration: every rule a set is checked with, in the order its entries are written.
RULES: tuple[Callable[[PdfSet], Found | None], ...] = (
    doors,
    window_check.windows,
    room_check.rooms,
)


def checks(data: bytes) -> tuple[Found, ...]:
    """What every rule found on a PDF set, read once."""
    pdf = PdfSet(data)
    return tuple(found for rule in RULES if (found := rule(pdf)) is not None)


_kept: OrderedDict[str, tuple[Found, ...]] = OrderedDict()
_keeping = threading.Lock()


def checks_of(files: DrawingFiles, source: DrawingFile) -> tuple[Found, ...]:
    """`checks` of a source PDF, kept for the last few sets by content."""
    with _keeping:
        if source.sha256 in _kept:
            _kept.move_to_end(source.sha256)
            return _kept[source.sha256]
    found = checks(files.read(source.path))
    with _keeping:
        _kept[source.sha256] = found
        while len(_kept) > KEPT:
            _kept.popitem(last=False)
    return found


def measurements(found: SetCheck) -> list[Measurement]:
    """The doors as the schedule lists them and as the plans tag them."""
    check = found.check
    doors = Subject(kind="class", ref="door")
    return [
        Measurement(
            quantity="element_count",
            subject=doors,
            value=MeasuredValue(
                value=len(check.rows),
                unit="count",
                method="schedule",
                page=check.schedule_page,
                box=check.schedule.box,
            ),
        ),
        Measurement(
            quantity="element_count",
            subject=doors,
            value=MeasuredValue(value=len(check.tagged), unit="count", method="plan_drawing"),
        ),
    ]


def note(found: SetCheck) -> str:
    """What differs, mark by mark, for the drawing's notes."""
    check = found.check
    pages = sorted({tag.page for tag in check.tags})

    def listed(marks: Sequence[str]) -> str:
        return ", ".join(marks) if marks else "none"

    repeated = [f"{mark} ({n}x on page {page})" for (page, mark), n in check.repeated.items()]
    return (
        f"door schedule (page {check.schedule_page}, {len(check.rows)} rows) against the door "
        f"tags on pages {', '.join(map(str, pages))} ({len(check.tagged)} marks): on the "
        f"schedule, tagged on no plan: {listed(check.untagged)}; tagged, not on the schedule: "
        f"{listed(check.unscheduled)}; tagged twice on one page: {listed(repeated)}"
    )


def reads_itself(source: DrawingFile, sheet: Sheet) -> bool:
    """The sheet is the source PDF itself, so page numbers and boxes are its own."""
    return source.kind == "pdf" and sheet.file.path == source.path


class ScheduleTagCounter:
    def __init__(self, inner: SecondCounter, files: DrawingFiles) -> None:
        self._inner = inner
        self._files = files

    def measure(self, source: DrawingFile, sheet: Sheet) -> list[Measurement]:
        found = list(self._inner.measure(source, sheet))
        if not reads_itself(source, sheet):
            return found
        return [
            *found,
            *(one for rule in checks_of(self._files, source) for one in rule.measurements()),
        ]

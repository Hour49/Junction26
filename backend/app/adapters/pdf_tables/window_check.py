"""Window types: the window schedule's count per type against the type tags on the floor plans of
the same PDF (a schedule rule, schedule_check.py).

A window schedule is a table whose title says "window" and that is no legend, with the type marks
in its key column and a count column ("Count", "Qty"): one row per type, its count the windows of
that type. A floor plan (a page whose text says "floor plan") tags each window with its type mark,
so the tags of a type are its windows. Elevations tag the same windows again, so only floor plans
are counted.

A tag is a text object whose whole text has the shape of a mark (tags.py), outside the schedule.
The set is checked only when the marks' shape is the window tags' alone: when a floor plan prints a
text of that shape that is no row (door numbers "16" or grid labels "09" beside type marks
"01".."14"), a window tag can't be told from the others. A mark of one character is never checked
(grid letters).
"""

import re
from collections import Counter
from dataclasses import dataclass

from app.adapters.pdf_tables import tags
from app.adapters.pdf_tables.set_pages import PdfSet
from app.core.drawing.model import MeasuredValue, Subject, Table
from app.core.pipeline.model import Measurement

SCHEDULE_PAGE = re.compile(r"window", re.IGNORECASE)
SCHEDULE_WORD = re.compile(r"schedul", re.IGNORECASE)
PLAN_PAGE = re.compile(r"floor\s+plan", re.IGNORECASE)
COUNT_HEADERS = ("count", "qty", "qty.", "quantity")
MIN_MARK = 2


@dataclass(frozen=True)
class WindowCheck:
    schedule_page: int
    schedule: Table
    scheduled: dict[str, int]  # windows per type, as the schedule counts them
    tagged: dict[str, int]  # tags per type on the floor plans
    plan_pages: tuple[int, ...]

    def measurements(self) -> list[Measurement]:
        """The windows as the schedule counts them and as the floor plans tag them."""
        windows = Subject(kind="class", ref="window")
        return [
            Measurement(
                quantity="element_count",
                subject=windows,
                value=MeasuredValue(
                    value=sum(self.scheduled.values()),
                    unit="count",
                    method="schedule",
                    page=self.schedule_page,
                    box=self.schedule.box,
                ),
            ),
            Measurement(
                quantity="element_count",
                subject=windows,
                value=MeasuredValue(
                    value=sum(self.tagged.values()), unit="count", method="plan_drawing"
                ),
            ),
        ]

    def note(self) -> str:
        """The types whose count differs, for the drawing's notes."""
        differ = [
            f"{mark} {count} vs {self.tagged.get(mark, 0)}"
            for mark, count in self.scheduled.items()
            if count != self.tagged.get(mark, 0)
        ]
        return (
            f"window schedule (page {self.schedule_page}, {len(self.scheduled)} types, "
            f"{sum(self.scheduled.values())} windows) against the window tags on the floor plans "
            f"(pages {', '.join(map(str, self.plan_pages))}, {sum(self.tagged.values())} tags): "
            f"types whose count differs (schedule vs tags): {', '.join(differ) or 'none'}"
        )


def window_schedule(tables: list[Table]) -> Table | None:
    """The one window schedule among a page's tables, or None when there is none or several."""
    found = [
        table
        for table in tables
        if "window" in (title := (table.title or "").casefold())
        and not any(word in title for word in tags.LEGEND_WORDS)
    ]
    return found[0] if len(found) == 1 else None


def counts_of(table: Table) -> dict[str, int] | None:
    """Windows per type mark, or None without a count column or with a count that is no number."""
    column = next(
        (n for n, header in enumerate(table.columns) if header.strip().casefold() in COUNT_HEADERS),
        None,
    )
    if column is None or column == table.key_column:
        return None
    counts: Counter[str] = Counter()
    for row in table.rows:
        mark, count = row.cells[table.key_column], row.cells[column]
        if mark is None:
            continue
        if count is None or not count.strip().isdigit():
            return None
        counts[" ".join(mark.split())] += int(count)
    return dict(counts)


def windows(pdf: PdfSet) -> WindowCheck | None:
    """The window rule: None when the set has no single window schedule with counts, no floor
    plan, a mark too short, a floor-plan text of a mark's shape that is no row, or no tag."""
    schedule: tuple[int, Table, list[Table]] | None = None
    for index, text in enumerate(pdf.text):
        if SCHEDULE_PAGE.search(text) and SCHEDULE_WORD.search(text):
            found = pdf.tables(index)
            table = window_schedule(found)
            if table is not None:
                if schedule is not None:
                    return None  # two window schedules: which one the plans follow is unclear
                schedule = (index + 1, table, found)
    if schedule is None:
        return None
    page_number, table, page_tables = schedule
    scheduled = counts_of(table)
    if not scheduled or any(len(mark) < MIN_MARK for mark in scheduled):
        return None
    pattern = tags.shapes(scheduled)
    plans = tuple(n + 1 for n, text in enumerate(pdf.text) if PLAN_PAGE.search(text))
    if pattern is None or not plans:
        return None
    tagged: Counter[str] = Counter()
    for number in plans:
        page = pdf.objects(number - 1)
        skip = (
            [tags.box_bounds(t.box, page.width, page.height) for t in page_tables]
            if number == page_number
            else []
        )
        for tag in tags.tags_on(page.texts, number, pattern, skip):
            if tag.mark not in scheduled:
                return None  # the marks' shape is also another tag's
            tagged[tag.mark] += 1
    if not tagged:
        return None
    return WindowCheck(page_number, table, scheduled, dict(tagged), plans)

"""Door marks: the rows of a door schedule against the tags the plans of the same set print.

A door schedule is a table whose title says "door" and that is no legend; its key column holds
the marks ("100.A1", "128.B"). A tag is a text object on another page whose whole text has the
shape of a mark (digits and capitals in the same places: "122.C" has the shape of "100.A"), so
room numbers, grid labels and sheet references ("A-101.B") are not tags. Text inside a schedule
is never a tag.

What is compared, per set:
- rows no plan tags (the schedule lists a door no plan shows);
- tags no row lists (a plan shows a door the schedule does not have);
- marks tagged more than once on one page (a page may repeat a mark across two views of one
  room, so these are listed, not counted as wrong);
- per door type: the rows of that type, and how many of them some plan tags.
"""

import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from app.adapters.vector_pdf.objects import Bounds, PdfText
from app.core.drawing.model import Box, Table

LEGEND_WORDS = ("key", "keynote", "legend")
TYPE_WORDS = ("type",)  # the column whose header says "type" holds the door type


@dataclass(frozen=True)
class Tag:
    mark: str
    page: int
    bounds: Bounds  # points on the page as rendered


@dataclass
class Check:
    """The comparison of one set's door schedule with its plans' tags."""

    schedule_page: int
    schedule: Table
    rows: list[str]  # the marks, in the schedule's order
    tags: list[Tag]
    untagged: list[str] = field(default_factory=list[str])  # rows no plan tags
    unscheduled: list[str] = field(default_factory=list[str])  # tags no row lists
    repeated: dict[tuple[int, str], int] = field(default_factory=dict[tuple[int, str], int])
    types: dict[str, tuple[int, int]] = field(default_factory=dict[str, tuple[int, int]])

    @property
    def tagged(self) -> set[str]:
        return {tag.mark for tag in self.tags}


def door_schedule(tables: Iterable[Table]) -> Table | None:
    """The one door schedule among a page's tables, or None when there is none or several."""
    found = [
        table
        for table in tables
        if "door" in (title := (table.title or "").casefold())
        and not any(word in title for word in LEGEND_WORDS)
    ]
    return found[0] if len(found) == 1 else None


def marks_of(table: Table) -> list[str]:
    return [
        " ".join(cell.split())
        for row in table.rows
        if (cell := row.cells[table.key_column]) is not None
    ]


def shapes(marks: Iterable[str]) -> re.Pattern[str] | None:
    """A pattern that matches a text with the shape of one of the marks: each digit a digit,
    each capital a capital, everything else itself."""
    found = sorted({_shape(mark) for mark in marks})
    if not found:
        return None
    return re.compile("|".join(f"(?:{shape})" for shape in found))


def _shape(mark: str) -> str:
    return "".join(
        r"\d" if char.isdigit() else "[A-Z]" if char.isupper() else re.escape(char) for char in mark
    )


def tags_on(
    texts: Sequence[PdfText], page: int, pattern: re.Pattern[str], skip: Sequence[Bounds] = ()
) -> list[Tag]:
    """The text objects of a page whose whole text has a mark's shape, outside `skip`."""
    return [
        Tag(text.text, page, text.bounds)
        for text in texts
        if pattern.fullmatch(text.text) and not any(_inside(text.bounds, box) for box in skip)
    ]


def _inside(inner: Bounds, outer: Bounds) -> bool:
    x, y = (inner[0] + inner[2]) / 2, (inner[1] + inner[3]) / 2
    return outer[0] <= x <= outer[2] and outer[1] <= y <= outer[3]


def compare(schedule_page: int, schedule: Table, tags: Sequence[Tag]) -> Check:
    rows = marks_of(schedule)
    check = Check(schedule_page, schedule, rows, list(tags))
    tagged, listed = check.tagged, set(rows)
    check.untagged = [mark for mark in rows if mark not in tagged]
    check.unscheduled = sorted(tagged - listed)
    per_page = Counter((tag.page, tag.mark) for tag in tags)
    check.repeated = {key: n for key, n in sorted(per_page.items()) if n > 1}
    check.types = _types(schedule, tagged)
    return check


def _types(schedule: Table, tagged: set[str]) -> dict[str, tuple[int, int]]:
    """Per door type: (rows of that type, rows of it some plan tags)."""
    column = next(
        (
            n
            for n, header in enumerate(schedule.columns)
            if n != schedule.key_column
            and any(w in header.casefold() for w in TYPE_WORDS)
            and "frame" not in header.casefold()
        ),
        None,
    )
    if column is None:
        return {}
    counts: Mapping[str, list[int]] = defaultdict(lambda: [0, 0])
    for row in schedule.rows:
        mark = row.cells[schedule.key_column]
        kind = row.cells[column] or "(none)"
        counts[kind][0] += 1
        counts[kind][1] += mark is not None and " ".join(mark.split()) in tagged
    return {kind: (a, b) for kind, (a, b) in sorted(counts.items())}


def box_bounds(box: Box, width: float, height: float) -> Bounds:
    """A page-fraction box back in points."""
    return box[0] * width, box[1] * height, box[2] * width, box[3] * height

"""Window types: the window schedule's counts against the type tags on a set's floor plans
(TABLES=pdf, stage 8). The sets are drawn here; no partner data."""

from pdf_sheets import SheetPdf
from test_pdf_tables import ruled
from test_schedule_check import Files, itself, joined, plan_page

from app.adapters.hello import HelloSecondCounter
from app.adapters.pdf_tables.schedule_check import ScheduleTagCounter
from app.adapters.pdf_tables.set_pages import PdfSet
from app.adapters.pdf_tables.window_check import windows
from app.core.pipeline.second_count import second_count

XS = (20.0, 80.0, 140.0)


def window_schedule(*rows: tuple[str, str], count: str = "Count") -> SheetPdf:
    """A window schedule: title, a Type Mark | <count> header, one row per type."""
    sheet = SheetPdf()
    ys = (20.0, 35.0, 50.0, *(62.0 + 12 * n for n in range(len(rows))))
    ruled(sheet, XS, ys, no_down=frozenset({(0, 1)}))
    sheet.text("WINDOW SCHEDULE", 45, 32)
    sheet.text("Type Mark", XS[0] + 2, 47)
    sheet.text(count, XS[1] + 2, 47)
    for (mark, n), bottom in zip(rows, ys[3:], strict=True):
        sheet.text(mark, XS[0] + 2, bottom - 3)
        sheet.text(n, XS[1] + 2, bottom - 3)
    return sheet


# Type 01: 2 windows, both tagged; 02: 1, tagged; 03: 1, tagged on the elevation only (an elevation
# tags the windows again, so it is not counted).
SCHEDULE = window_schedule(("01", "2"), ("02", "1"), ("03", "1"))
PLAN = plan_page(
    ("FLOOR PLAN - 1ST FLOOR", 30, 380), ("01", 100, 100), ("01", 200, 100), ("02", 300, 100)
)
ELEVATION = plan_page(("NORTH ELEVATION", 30, 380), ("01", 100, 100), ("03", 200, 100))


def test_the_schedule_counts_against_the_floor_plan_tags_per_type() -> None:
    found = windows(PdfSet(joined(PLAN, ELEVATION, SCHEDULE)))
    assert found is not None
    assert found.scheduled == {"01": 2, "02": 1, "03": 1}
    assert found.tagged == {"01": 2, "02": 1}
    assert found.plan_pages == (1,)
    assert found.note() == (
        "window schedule (page 3, 3 types, 4 windows) against the window tags on the floor plans "
        "(pages 1, 3 tags): types whose count differs (schedule vs tags): 03 1 vs 0"
    )


def test_the_two_window_counts_are_a_conflict_no_rule_resolves() -> None:
    pdf = joined(PLAN, ELEVATION, SCHEDULE)
    source, sheet = itself(pdf)
    measured = ScheduleTagCounter(HelloSecondCounter(), Files(source, pdf)).measure(source, sheet)
    (entry,) = second_count([], measured)
    assert (entry.quantity, entry.subject.kind, entry.subject.ref) == (
        "element_count",
        "class",
        "window",
    )
    assert entry.status == "conflict" and entry.resolution is None
    assert [(v.method, v.value, v.page) for v in entry.values] == [
        ("schedule", 4, 3),
        ("plan_drawing", 3, None),
    ]


def test_no_check_when_a_tag_cannot_be_told_from_other_text() -> None:
    # a door numbered "16" on the plan has the shape of the window types "01".."03"
    door = plan_page(("FLOOR PLAN", 30, 380), ("01", 100, 100), ("16", 200, 100))
    assert windows(PdfSet(joined(door, SCHEDULE))) is None
    # one-letter types have the shape of grid letters
    letters = plan_page(("FLOOR PLAN", 30, 380), ("A", 100, 100))
    assert windows(PdfSet(joined(letters, window_schedule(("A", "1"))))) is None
    # no count column, no floor plan
    assert windows(PdfSet(joined(PLAN, window_schedule(("01", "2"), count="Width")))) is None
    assert windows(PdfSet(joined(ELEVATION, SCHEDULE))) is None

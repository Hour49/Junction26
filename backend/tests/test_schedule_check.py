"""The door schedule against the plans' door tags in one PDF set (TABLES=pdf, stage 8): which
marks differ, which text is no tag, and the two counts as an unresolved conflict. The sets are
drawn here; no partner data."""

import hashlib
import io

import pypdfium2
from pdf_sheets import SheetPdf
from test_pdf_tables import ruled

from app.adapters.hello import HelloSecondCounter
from app.adapters.pdf_tables import PdfTables
from app.adapters.pdf_tables.schedule_check import (
    ScheduleTagCounter,
    check_set,
    measurements,
    note,
)
from app.core.drawing.model import Page, Scale
from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from app.core.pipeline.second_count import second_count

XS = (20.0, 80.0, 140.0)


def schedule_page(*marks: str) -> SheetPdf:
    """A door schedule: title, a Mark | Width header, one row per mark."""
    sheet = SheetPdf()
    ys = (20.0, 35.0, 50.0, *(62.0 + 12 * n for n in range(len(marks))))
    ruled(sheet, XS, ys, no_down=frozenset({(0, 1)}))
    sheet.text("DOOR SCHEDULE", 50, 32)
    sheet.text("Mark", XS[0] + 2, 47)
    sheet.text("Width", XS[1] + 2, 47)
    for mark, bottom in zip(marks, ys[3:], strict=True):
        sheet.text(mark, XS[0] + 2, bottom - 3)
        sheet.text("3'-0\"", XS[1] + 2, bottom - 3)
    return sheet


def plan_page(*texts: tuple[str, float, float]) -> SheetPdf:
    sheet = SheetPdf()
    sheet.path([(10, 10), (590, 10), (590, 390), (10, 390), (10, 10)])  # a wall, no grid
    for text, x, y in texts:
        sheet.text(text, x, y)
    return sheet


def joined(*sheets: SheetPdf) -> bytes:
    """The sheets as the pages of one PDF, in order."""
    document = pypdfium2.PdfDocument(sheets[0].pdf())
    for sheet in sheets[1:]:
        other = pypdfium2.PdfDocument(sheet.pdf())
        document.import_pages(other)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


# A plan that tags 101.A, 102.A twice and 103.A, and prints a room number, the project number and
# a sheet reference, none of them a tag; the schedule lists 101.A, 102.A, 104.A and 105.A.
PLAN = plan_page(
    ("101.A", 100, 100),
    ("102.A", 200, 100),
    ("102.A", 260, 100),
    ("103.A", 300, 200),
    ("101", 120, 150),
    ("019", 500, 380),
    ("A-101.B", 400, 300),
)
SET = (PLAN, schedule_page("101.A", "102.A", "104.A", "105.A"))


def test_rows_and_tags_are_compared_mark_by_mark() -> None:
    found = check_set(joined(*SET))
    assert found is not None
    check = found.check
    assert check.schedule_page == 2
    assert check.rows == ["101.A", "102.A", "104.A", "105.A"]
    # the schedule's own cells, the room number, the project number and the sheet reference
    # are no tags
    assert sorted(check.tagged) == ["101.A", "102.A", "103.A"]
    assert check.untagged == ["104.A", "105.A"]
    assert check.unscheduled == ["103.A"]
    assert check.repeated == {(1, "102.A"): 2}


def test_the_two_counts_are_a_conflict_no_rule_resolves() -> None:
    pdf = joined(*SET)
    source, sheet = itself(pdf)
    measured = ScheduleTagCounter(HelloSecondCounter(), Files(source, pdf)).measure(source, sheet)
    (entry,) = second_count([], measured)
    assert (entry.quantity, entry.subject.kind, entry.subject.ref) == (
        "element_count",
        "class",
        "door",
    )
    assert entry.status == "conflict" and entry.resolution is None
    assert [(v.method, v.value, v.page) for v in entry.values] == [
        ("schedule", 4, 2),
        ("plan_drawing", 3, None),
    ]


def test_the_extractor_notes_the_marks_that_differ() -> None:
    pdf = joined(*SET)
    source, sheet = itself(pdf)
    got = PdfTables(Nothing(), Files(source, pdf)).extract(source, sheet)
    assert got.notes == (
        "door schedule (page 2, 4 rows) against the door tags on pages 1 (3 marks): on the "
        "schedule, tagged on no plan: 104.A, 105.A; tagged, not on the schedule: 103.A; tagged "
        "twice on one page: 102.A (2x on page 1)",
    )


def test_a_set_that_agrees_is_two_equal_counts() -> None:
    found = check_set(joined(plan_page(("101.A", 100, 100)), schedule_page("101.A")))
    assert found is not None
    (entry,) = second_count([], measurements(found))
    assert entry.status == "agree"
    assert "tagged on no plan: none; tagged, not on the schedule: none" in note(found)


def test_no_check_without_plans_or_with_marks_that_look_like_other_text() -> None:
    assert check_set(schedule_page("101.A", "102.A").pdf()) is None  # a schedule sheet alone
    plan = plan_page(("101", 100, 100), ("102", 200, 100))
    assert check_set(joined(plan, schedule_page("101", "102"))) is None  # digits only
    assert check_set(joined(plan_page(("D1", 9, 9)), schedule_page("D1", "D2"))) is None  # short
    assert check_set(plan.pdf()) is None  # no schedule


def test_a_sheet_that_is_not_the_pdf_itself_is_not_checked() -> None:
    pdf = joined(*SET)
    source, _ = itself(pdf)
    render = Sheet(
        file=source.model_copy(update={"path": "data/demo/set.png", "kind": "png"}),
        pages=(Page(page=1, width=1200, height=800, unit="px"),),
    )
    files = Files(source, pdf)
    assert ScheduleTagCounter(HelloSecondCounter(), files).measure(source, render) == []
    assert files.reads == 0


class Files:
    def __init__(self, source: DrawingFile, pdf: bytes) -> None:
        self.source, self.pdf, self.reads = source, pdf, 0

    def read(self, path: str) -> bytes:
        assert path == self.source.path
        self.reads += 1
        return self.pdf


class Nothing:
    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        return Extracted(method="parser", scale=Scale(status="no_scale"), read=())


def itself(pdf: bytes) -> tuple[DrawingFile, Sheet]:
    """The PDF as source and sheet; its content hash keys the kept checks."""
    source = DrawingFile(
        path="data/demo/set.pdf", size=len(pdf), sha256=hashlib.sha256(pdf).hexdigest(), kind="pdf"
    )
    pages = (
        Page(page=1, width=600, height=400, unit="pt"),
        Page(page=2, width=600, height=400, unit="pt"),
    )
    return source, Sheet(file=source, pages=pages)

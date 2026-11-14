"""A file's end state and reason (app/core/ingest/judge.py)."""

from app.core.drawing.model import Drawing, Page, Scale, Table, TableRow
from app.core.ingest.judge import judge, reading_flags

SCHEDULE_NOTE = "no sheet style we have reading rules for: only the scale was read"


def sheet(tables: tuple[Table, ...] | None) -> Drawing:
    """A drawn PDF sheet the vector reader found no plan style on (`read` empty)."""
    return Drawing(
        file="schedules/a-801.pdf",
        pages=(Page(page=1, width=3024, height=2160, unit="pt"),),
        scale=Scale(status="no_scale"),
        read=(),
        tables=tables,
        notes=(SCHEDULE_NOTE,),
    )


DOORS = Table(
    id="t1",
    page=1,
    box=(0.05, 0.05, 0.3, 0.3),
    title="Door Schedule",
    columns=("Door Number", "Room Name"),
    rows=(TableRow(cells=("100.A1", "VEST.")),),
)


def test_a_schedule_sheet_whose_tables_were_read_is_not_said_to_have_read_nothing() -> None:
    state, reason = judge(sheet((DOORS,)), "pdf_vector", "vector", "pdf")
    assert (state, reason) == (
        "ready",
        "read on the drawn PDF route: 0 elements, 0 rooms, 1 schedule, no scale on the sheet",
    )


def test_a_sheet_with_no_plan_and_no_schedule_still_read_nothing() -> None:
    for tables in (None, ()):
        state, reason = judge(sheet(tables), "pdf_vector", "vector", "pdf")
        assert state == "flagged"
        assert reason.startswith(f"the drawn PDF reader read nothing: {SCHEDULE_NOTE}")


def test_the_reading_flags_are_the_photo_s_and_the_scan_s_not_a_conflict() -> None:
    """R3-qa4-1: the flags an answer must carry are about how the page was read (a phone photo,
    a scan); a conflict is shown on its own row already."""
    photo = Drawing(file="027.jpg", pages=(Page(page=1, width=10, height=10, unit="px"),),
                    scale=Scale(status="no_scale"), read=("door", "room"))  # fmt: skip
    assert reading_flags("photo_plan", None) == (
        "a phone photo, read without perspective correction",
    )
    assert reading_flags("pdf_scan", None) == ("a scanned PDF, read as an image",)
    assert reading_flags("png_plan", None) == ()
    state, reason = judge(photo, "photo_plan", "raster", "composite")
    assert state == "flagged" and reason.startswith(reading_flags("photo_plan", None)[0])

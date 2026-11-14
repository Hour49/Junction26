"""A file's end state and reason (app/core/ingest/judge.py)."""

from app.core.drawing.model import Drawing, Page, Scale, Table, TableRow
from app.core.ingest.judge import judge

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
        "read on the vector route: 0 elements, 0 rooms, 1 schedule, scale no_scale",
    )


def test_a_sheet_with_no_plan_and_no_schedule_still_read_nothing() -> None:
    for tables in (None, ()):
        state, reason = judge(sheet(tables), "pdf_vector", "vector", "pdf")
        assert state == "flagged"
        assert reason.startswith(f"the vector reader read nothing: {SCHEDULE_NOTE}")

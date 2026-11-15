"""A file's end state and reason (app/core/ingest/judge.py)."""

from app.core.drawing.model import (
    Drawing,
    MeasuredValue,
    MeasureMethod,
    Page,
    Resolution,
    Scale,
    Subject,
    Table,
    TableRow,
)
from app.core.ingest.judge import judge, reading_flags
from app.core.pipeline.model import Measurement
from app.core.pipeline.second_count import second_count

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


def scale_read_twice(estimate: float, printed: float, method: MeasureMethod) -> Drawing:
    """A plan whose scale was estimated from the doors and printed, as second_count compares
    them (printed.scale_measurements)."""
    sheet = Subject(kind="sheet", ref=None)

    def value(quantity: str, subject: Subject, at: float, by: MeasureMethod) -> Measurement:
        return Measurement(quantity=quantity, subject=subject,  # type: ignore[arg-type]
                           value=MeasuredValue(value=at, method=by))  # fmt: skip

    conflicts = second_count(
        [value("scale", sheet, estimate, "detector")],
        [value("scale", sheet, printed, method)],
    )
    return Drawing(
        file="plans/t1.png",
        pages=(Page(page=1, width=100, height=100, unit="px"),),
        scale=Scale(status="scaled", m_per_unit=printed),
        read=("door", "room"),
        conflicts=tuple(conflicts),
    )


def test_a_scale_read_two_ways_is_not_called_a_conflict_a_person_settles() -> None:
    """QA R3-A1: a file said "1 conflict between the two methods (scale)" while its project's
    Conflicts list said none: a scale disagreement is never a row there (no takeoff quantity is
    the scale). The file is still flagged, saying what the disagreement is and who decided."""
    ruled = scale_read_twice(0.010, 0.0125, "scale_text")  # 25% apart: the printed one is kept
    state, reason = judge(ruled, "png_plan", "raster", "composite")
    assert state == "flagged"
    assert "conflict" not in reason, reason
    assert reason.startswith(
        "the scale read two ways disagrees: a rule keeps the printed scale over the scale "
        "estimated from the doors ("
    ), reason
    unruled = scale_read_twice(0.010, 0.030, "scale_text")  # 3x apart: no rule decides
    state, reason = judge(unruled, "png_plan", "raster", "composite")
    assert state == "flagged"
    assert reason.startswith(
        "the scale read two ways disagrees and no rule decides between them ("
    ), reason


def test_a_scale_disagreement_does_not_count_as_one_of_the_file_s_conflicts() -> None:
    drawing = scale_read_twice(0.010, 0.0125, "scale_bar")
    area = second_count(
        [Measurement(quantity="room_area", subject=Subject(kind="room", ref="r1"),
                     value=MeasuredValue(value=10.0, method="polygon_x_scale"))],
        [Measurement(quantity="room_area", subject=Subject(kind="room", ref="r1"),
                     value=MeasuredValue(value=12.0, method="printed_label"))],
    )  # fmt: skip
    unruled = [entry.model_copy(update={"resolution": None}) for entry in area]  # R4-B7
    both = drawing.model_copy(update={"conflicts": (*(drawing.conflicts or ()), *unruled)})
    state, reason = judge(both, "png_plan", "raster", "composite")
    assert state == "flagged"
    assert reason.startswith(
        "1 conflict between the two methods (room areas); the scale read two ways disagrees: "
        "a rule keeps the printed scale bar over the scale estimated from the doors ("
    ), reason


def test_a_conflict_a_rule_settled_says_so_in_the_file_s_reason() -> None:
    """Tudor QA round 4, R4-B7: the file's only flag reason was a conflict a rule settled (its
    card: "1 conflict found · 1 settled by a rule", the Conflicts tile 0 open), yet the file's
    reason read as if a person still had to settle it. It stays flagged (golden demo step 3:
    flat-b), and its reason says a rule settled it; one no rule decides reads as before."""
    area = second_count(
        [Measurement(quantity="room_area", subject=Subject(kind="room", ref="r1"),
                     value=MeasuredValue(value=10.0, method="polygon_x_scale"))],
        [Measurement(quantity="room_area", subject=Subject(kind="room", ref="r1"),
                     value=MeasuredValue(value=12.0, method="printed_label"))],
    )  # fmt: skip
    [found] = [entry for entry in area if entry.status == "conflict"]
    ruled = found.model_copy(update={"resolution": Resolution(rule="printed label", value=12.0)})
    open_one = found.model_copy(update={"resolution": None})
    plan = sheet(None).model_copy(update={"scale": Scale(status="scaled"), "read": ("swiss",)})
    state, reason = judge(plan.model_copy(update={"conflicts": (ruled,)}), "pdf_vector",
                          "vector", "pdf")  # fmt: skip
    assert state == "flagged", reason
    ruled_reason = "1 conflict between the two methods (room areas), settled by a rule ("
    assert reason.startswith(ruled_reason), reason
    state, reason = judge(plan.model_copy(update={"conflicts": (open_one, ruled)}), "pdf_vector",
                          "vector", "pdf")  # fmt: skip
    assert state == "flagged"
    assert reason.startswith(
        "1 conflict between the two methods (room areas); 1 conflict between the two methods "
        "(room areas), settled by a rule ("
    ), reason

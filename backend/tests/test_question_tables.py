"""Schedule questions to a TableQuery: what is done, which rows (values and the words before
them), which table; superlatives, two quantities and breakdowns are refused."""

from app.adapters.question_templates import TemplateParser
from app.core.answering.model import Query, TableFilter, TableQuery, Unsupported

PARSE = TemplateParser().parse
SHEET = "On sheet A-801 of the Xcel Sports Complex drawings, "


def test_counts_name_rows_by_code_note_dimension_and_room() -> None:
    assert PARSE(SHEET + "how many doors in the door schedule are door type A1 (swing door)?") == (
        TableQuery(
            op="count",
            kind="door",
            filters=(TableFilter(values=("A1",), cue=("are", "door", "type")),),
        )
    )
    frames = PARSE("How many doors have aluminium storefront frames (AL-1 or AL-2)?")
    assert isinstance(frames, TableQuery)
    assert frames.filters == (
        TableFilter(values=("AL-1", "AL-2"), cue=("aluminium", "storefront", "frames")),
    )
    note = PARSE("How many doors in the door schedule carry note B (opens 180°)?")
    assert isinstance(note, TableQuery) and note.filters == (
        TableFilter(values=("B",), cue=("note",)),
    )
    wide = PARSE("How many doors in the door schedule are 3'-0\" wide?")
    assert isinstance(wide, TableQuery)
    assert wide.filters == (TableFilter(values=("3'-0\"",), cue=("wide",)),)
    walls = PARSE("How many rooms have all four walls finished with W1 (painted gypsum board)?")
    assert isinstance(walls, TableQuery) and walls.kind == "room"
    assert walls.filters == (TableFilter(values=("W1",), cue=("wall",), every=True),)
    listed = PARSE(SHEET + "how many rooms are listed in the finish room schedule?")
    assert listed == TableQuery(op="count", kind="room", every_row=True)


def test_areas_sum_and_reads_name_their_columns() -> None:
    area = PARSE(
        SHEET + "what is the total area of the rooms named OFFICE in the finish room schedule?"
    )
    assert area == TableQuery(
        op="sum",
        kind="room",
        column=(("area",),),
        filters=(TableFilter(values=("OFFICE",), cue=("name",)),),
    )
    size = PARSE(SHEET + "what are the width and height of door 128.B?")
    assert size == TableQuery(
        op="read",
        kind="door",
        column=(("width",), ("height",)),
        filters=(TableFilter(values=("128.B",), cue=("door", "number")),),
    )
    finish = PARSE("What is the floor finish of room 113 (Aerobics & Yoga), and what does it mean?")
    assert isinstance(finish, TableQuery)
    assert (finish.op, finish.kind, finish.column, finish.meaning) == (
        "read",
        "room",
        (("floor", "finish"),),
        True,
    )
    # a door range names both ends; the type code is a second filter
    four = PARSE(
        "What is the height of the four doors of type B2 that serve the Fitness Center"
        " (118.A1-118.B2)?"
    )
    assert isinstance(four, TableQuery)
    assert TableFilter(values=("118.A1", "118.B2"), cue=("door", "number")) in four.filters


def test_what_a_schedule_cannot_answer_in_one_lookup_is_refused() -> None:
    for text in (
        "Which room in the finish room schedule has the largest area?",
        "How many rooms have floor finish F0, and what is their total area?",
        "How many doors of each type are listed in the door schedule?",
        "What is the hardware group in the door schedule?",  # no row named
    ):
        assert isinstance(PARSE(text), Unsupported), text


def test_a_count_in_an_unquoted_plan_is_refused_not_answered_for_the_sheet() -> None:
    text = "How many lavatories are drawn inside the two restrooms of enlarged plan 6A?"
    assert isinstance(PARSE(text), Unsupported)
    assert PARSE("How many sinks are shown on this floor plan?") == Query(subject="sink")

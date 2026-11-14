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
            table=("door",),
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
    assert listed == TableQuery(op="count", kind="room", table=("finish", "room"), every_row=True)


def test_areas_sum_and_reads_name_their_columns() -> None:
    area = PARSE(
        SHEET + "what is the total area of the rooms named OFFICE in the finish room schedule?"
    )
    assert area == TableQuery(
        op="sum",
        kind="room",
        table=("finish", "room"),
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
        "Which office in the finish room schedule has the largest area?",  # no kind of row
        "Which door in the door schedule has the longest frame?",
        "How many doors are listed in the door schedule, and what is their total width?",
        "How many doors of each type are listed in the door schedule?",
        "What is the hardware group in the door schedule?",  # no row named
    ):
        assert isinstance(PARSE(text), Unsupported), text


def test_a_count_in_an_unquoted_plan_is_refused_not_answered_for_the_sheet() -> None:
    text = "How many lavatories are drawn inside the two restrooms of enlarged plan 6A?"
    assert isinstance(PARSE(text), Unsupported)
    assert PARSE("How many sinks are shown on this floor plan?") == Query(subject="sink")


def test_a_count_can_be_asked_without_how_many() -> None:
    whole = TableQuery(op="count", kind="door", table=("door",), every_row=True)
    for text in (
        "Count the doors listed in the door schedule on sheet A-801 of the Xcel Sports Complex.",
        "What is the number of doors listed in the door schedule?",
    ):
        assert PARSE(text) == whole, text


CTR = "On sheet A700 of the Cannery Trail Residences drawings (1750 N Oxford Ave, Eau Claire, WI), "


def test_the_sheet_context_ends_at_the_first_comma_outside_parentheses() -> None:
    fire = PARSE(CTR + "what fire rating is scheduled for the unit doors (type U01)?")
    assert fire == TableQuery(
        op="read",
        kind="door",
        column=(("fire", "rating"),),
        filters=(TableFilter(values=("U01",), cue=("unit", "doors", "type")),),
    )


def test_a_count_names_its_rows_with_any_noun_phrase() -> None:
    for text, kind, values in (
        ("how many unit entry doors (type U01) are scheduled?", "door", ("U01",)),
        ("how many 2'-10\" x 6'-8\" privacy swing doors (type U02) are scheduled?", "door",
         ("U02",)),
        ("how many sliding flush wood doors (types U06 and U44) are scheduled?", "door",
         ("U06", "U44")),
        ("how many chain-link gates (type U22) are scheduled?", "door", ("U22",)),
        ("how many doors with an acoustical seal (type U41) are scheduled?", "door", ("U41",)),
    ):  # fmt: skip
        parsed = PARSE(CTR + text)
        assert isinstance(parsed, TableQuery), text
        assert (parsed.op, parsed.kind) == ("count", kind), text
        assert [f.values for f in parsed.filters] == [values], text


def test_windows_are_counted_by_type_marks_of_capitals_only() -> None:
    one = PARSE(CTR + "how many windows of type SS (2-WIDE (TEMP ALL LOW) ESDH3066) are scheduled?")
    assert one == TableQuery(
        op="count", kind="window", filters=(TableFilter(values=("SS",), cue=("type",)),)
    )
    three = PARSE(CTR + "how many 2-wide window assemblies (types SS, TT and UU) are scheduled?")
    assert isinstance(three, TableQuery) and three.kind == "window"
    assert three.filters == (TableFilter(values=("SS", "TT", "UU"), cue=("type",)),)
    listed = PARSE(
        CTR + "how many windows (window assemblies) are listed in the window schedule in total?"
    )
    assert listed == TableQuery(op="count", kind="window", table=("window",), every_row=True)


def test_a_count_of_any_item_in_a_named_schedule_keeps_the_name() -> None:
    items = PARSE(
        CTR + "how many items in total are counted in the door type schedule (all type marks,"
        " including gates, access panels and clear openings)?"
    )
    assert items == TableQuery(op="count", kind="door", table=("door", "type"), every_row=True)


def test_a_count_of_what_is_no_row_is_not_a_count() -> None:
    for text in (
        "How many square feet is room 128 in the finish room schedule?",
        "How many hardware sets are used in the door schedule?",
        "What is the room number of the office in the finish room schedule?",
    ):
        parsed = PARSE(text)
        assert not (isinstance(parsed, TableQuery) and parsed.op == "count"), text


def test_a_count_names_rows_by_a_printed_name_a_floor_or_a_description_start() -> None:
    marvin = PARSE(
        CTR + "how many Marvin Essential sliding patio doors are scheduled on the 3rd floor?"
    )
    assert marvin == TableQuery(
        op="count",
        kind="door",
        filters=(
            TableFilter(values=("3rd floor",), match="contains"),
            TableFilter(values=("Marvin Essential",), match="contains"),
        ),
    )
    swing = PARSE(
        CTR
        + "how many door leaves of the types whose description starts with 'SWING' are scheduled?"
    )
    assert isinstance(swing, TableQuery) and swing.op == "count" and swing.kind == "door"
    assert swing.filters == (TableFilter(values=("SWING",), match="starts"),)


def test_the_row_with_the_largest_or_smallest_area_is_asked_of_a_kind_of_row() -> None:
    largest = PARSE(SHEET + "which room in the finish room schedule has the largest area?")
    assert largest == TableQuery(
        op="max", kind="room", table=("finish", "room"), column=(("area",),)
    )
    smallest = PARSE("Which room has the smallest area in the finish room schedule?")
    assert isinstance(smallest, TableQuery) and (smallest.op, smallest.kind) == ("min", "room")


def test_a_count_and_the_total_area_of_the_same_rows_is_one_query() -> None:
    both = PARSE(
        SHEET + "how many rooms have floor finish F0 (unfinished concrete slab), and what is"
        " their total area?"
    )
    assert isinstance(both, TableQuery)
    assert (both.op, both.kind, both.column) == ("count_sum", "room", (("area",),))
    assert [f.values for f in both.filters] == [("F0",)]

"""Schedule answers: a filter's column is found from its values (and the words before them), the
column to sum or read from its header, and anything that does not resolve to one table and one
column is no answer."""

from app.core.answering.model import TableFilter, TableQuery
from app.core.answering.tables import MEANING_WHY, TableAnswer, answer_table
from app.core.drawing.model import Table, TableRow

BOX = (0.1, 0.1, 0.5, 0.5)


def table(
    title: str, columns: tuple[str, ...], *rows: tuple[str | None, ...], key: int = 0
) -> Table:
    return Table(
        id=title,
        page=1,
        box=BOX,
        title=title,
        columns=columns,
        key_column=key,
        rows=tuple(
            TableRow(cells=cells, box=(0.1, 0.1 + i / 100, 0.5, 0.11 + i / 100))
            for i, cells in enumerate(rows)
        ),
    )


DOORS = table(
    "Door Schedule",
    ("Door Number", "Room Number", "Door Width", "Door Height", "Door Type", "Door Matl",
     "Frame Matl", "Hardware Group - see Specs", "Notes"),
    ("100.A", "100", "3' - 0\"", "7' - 0\"", "A1", "WD-1", "STL-1", "01", "A, B"),
    ("100.B", "100", "2' - 8\"", "7' - 0\"", "B2", "AL-1/GL-1", "AL-1", "04", None),
    ("101.A", "101", "3' - 0\"", "8' - 0\"", "B2", "AL-2/GL-2", "AL-2", "04", "A"),
)  # fmt: skip
ROOMS = table(
    "FINISH ROOM SCHEDULE",
    ("Area", "Room Number", "Room Name", "Floor Finish", "Base Finish",
     "Wall Finishes North Wall", "Wall Finishes South Wall"),
    ("108 SF", "100", "VEST.", "F1", "B1", "W1", "W1"),
    ("145 SF", "101", "OFFICE", "F4", "B2", "W1", "W2"),
    ("123 SF", "102", "OFFICE", "F2 & F3", "B2", "W1", "W1"),
    ("Redundant Room", "103", "CORRIDOR", None, None, None, None),
    key=1,
)  # fmt: skip
KEY = table(
    "FINISH KEY",
    ("Finish Key", "Finish - Description"),
    ("F2", "ARTIFICIAL TURF"),
    ("F3", "BASKETBALL FLOORING"),
    ("F4", "RESILIENT FLOORING (T.B.D.)"),
)
SHEET = (DOORS, ROOMS, KEY)


def ask(op: str, *filters: TableFilter, **fields: object) -> object:
    found = answer_table(TableQuery.model_validate({"op": op, "filters": filters, **fields}), SHEET)
    return None if found is None else (found.value, found.unit)


def test_counts_find_the_column_from_the_value_and_the_words_before_it() -> None:
    assert ask("count", TableFilter(values=("B2",), cue=("door", "type")), kind="door") == (
        2,
        "count",
    )
    assert ask("count", TableFilter(values=("WD-1",)), kind="door") == (1, "count")
    # AL-1 is in Door Matl (AL-1/GL-1) and Frame Matl: the cue picks the frame
    frames = TableFilter(values=("AL-1", "AL-2"), cue=("storefront", "frames"))
    assert ask("count", frames, kind="door") == (2, "count")
    assert ask("count", TableFilter(values=("AL-1",)), kind="door") is None  # two columns
    assert ask("count", TableFilter(values=("A",), cue=("note",)), kind="door") == (2, "count")
    assert ask("count", TableFilter(values=("3'-0\"",), cue=("wide",)), kind="door") == (2, "count")
    assert ask("count", TableFilter(values=("100",), cue=("room",)), kind="door") == (2, "count")
    walls = TableFilter(values=("W1",), cue=("wall",), every=True)
    assert ask("count", walls, kind="room") == (2, "count")


def test_a_whole_table_is_counted_only_when_asked_and_legends_are_never_counted() -> None:
    assert ask("count", kind="door", every_row=True) == (3, "count")
    assert ask("count", kind="room", every_row=True) == (4, "count")
    assert ask("count", kind="door") is None  # no rows named, no "all": no answer


def test_sums_add_printed_areas_and_skip_cells_that_are_no_area() -> None:
    area = (("area",),)
    assert ask("sum", kind="room", column=area, every_row=True) == (376, "ft2")
    assert ask("sum", TableFilter(values=("OFFICE",), cue=("name",)), column=area) == (268, "ft2")
    assert ask("sum", TableFilter(values=("F4",), cue=("floor",)), column=area) == (145, "ft2")
    assert ask("sum", TableFilter(values=("103",), cue=("room",)), column=area, kind="room") is None


def test_reads_give_the_one_printed_text_and_its_meaning_when_asked() -> None:
    door = TableFilter(values=("100.B",), cue=("door",))
    assert ask("read", door, column=(("width",),)) == ("2'-8\"", None)
    assert ask("read", door, column=(("door", "material"),)) == ("AL-1/GL-1", None)
    assert ask("read", door, column=(("hardware", "group"),)) == ("04", None)
    assert ask("read", door, column=(("width",), ("height",))) == (
        "2'-8\" wide x 7'-0\" high",
        None,
    )
    room = TableFilter(values=("102",), cue=("room",))
    assert ask("read", room, column=(("floor", "finish"),), meaning=True) == (
        "F2 & F3 - ARTIFICIAL TURF and BASKETBALL FLOORING",
        None,
    )
    # rows that print different heights have no one height
    both = TableFilter(values=("100.A", "101.A"), cue=("door",))
    assert ask("read", both, column=(("height",),)) is None
    assert ask("read", both, column=(("door", "type"),)) is None
    assert ask("read", room, column=(("colour",),)) is None  # no such column


def answer(op: str, *filters: TableFilter, **fields: object) -> TableAnswer | None:
    return answer_table(TableQuery.model_validate({"op": op, "filters": filters, **fields}), SHEET)


def test_a_meaning_asked_of_a_code_no_legend_explains_is_no_answer() -> None:
    """Door type B2 is explained only by the door type drawings, not by a legend table: the
    code alone would not answer "and what kind of door is that?"."""
    door = TableFilter(values=("100.B",), cue=("door",))
    assert answer("read", door, column=(("door", "type"),), meaning=True) is None
    assert ask("read", door, column=(("door", "type"),)) == ("B2", None)


def test_a_finish_is_read_with_its_key_and_abstains_on_the_wording() -> None:
    """A finish code means nothing without the finish key, so it is read with it, asked or
    not; the key's words are the sheet's, which a question may expect in other words."""
    room = TableFilter(values=("102",), cue=("room",))
    for meaning in (False, True):
        found = answer("read", room, column=(("floor", "finish"),), meaning=meaning)
        assert found is not None
        assert found.value == "F2 & F3 - ARTIFICIAL TURF and BASKETBALL FLOORING"
        assert found.abstain_why == MEANING_WHY
    # a finish code the key does not list is read as printed, and stands
    plain = answer("read", TableFilter(values=("100",), cue=("room",)), column=(("floor",),))
    assert plain is not None and (plain.value, plain.abstain_why) == ("F1", None)
    # a column that is no finish keeps its codes as printed
    door = TableFilter(values=("100.B",), cue=("door",))
    material = answer("read", door, column=(("door", "material"),))
    assert material is not None and (material.value, material.abstain_why) == ("AL-1/GL-1", None)


# A schedule of door types (one row per type, its count printed) beside a schedule of door
# numbers, and a window schedule whose type marks are capitals only: the CTR sheet's layout.
BY_NUMBER = table(
    "DOOR SCHEDULE - NUMBER",
    ("Level", "Mark", "Type", "Fire Rating", "Door Type"),
    ("1ST FLOOR", "101A", "HM - METAL LEAF", "1HR", "A1"),
    ("1ST FLOOR", "104", "ALUM. STILE W/ GLASS INSET", None, "B1"),
)
BY_TYPE = table(
    "DOOR SCHEDULE - TYPE",
    ("Count", "Type Mark", "Type", "Fire Rating", "Frame Material"),
    ("71", "U01", "UNIT DOOR", "20 MIN.", "HM"),
    ("55", "U06", "SLIDING - FLUSH - 5-0 x 6-8", None, "WD"),
    ("52", "U41", "SWING - WITH ACOUSTICAL SEAL", None, "WD"),
    ("10", "U44", "SLIDING - FLUSH - 6-0 x 6-8", None, "WD"),
    ("2", "U2-LR", "LR-MARVIN ESSENTIAL SLIDING - 2ND FLOOR", None, "AL"),
    ("6", "U3-LR", "LR-MARVIN ESSENTIAL SLIDING - 3RD FLOOR", None, "AL"),
    ("14", "U46", "SWING - PRIVACY AT 3RD FLOOR (AT 1ST AND 2ND FLOOR ONLY)", None, "WD"),
    key=1,
)
WINDOWS = table(
    "WINDOW SCHEDULE - SIMPLIFIED",
    ("Type Mark", "Type", "Qty", "Width"),
    ("RR", "1-WIDE (TEMP LOWER) ESDH3066", "84", '35 1/2"'),
    ("SS", "2-WIDE (TEMP ALL LOW) ESDH3066", "118", '35 1/2"'),
    ("TT", "2-WIDE (TEMP LOW L/ ALL R) ESDH3066", "4", '35 1/2"'),
)
TYPES_SHEET = (BY_NUMBER, BY_TYPE, WINDOWS)


def on_types(op: str, *filters: TableFilter, **fields: object) -> object:
    query = TableQuery.model_validate({"op": op, "filters": filters, **fields})
    found = answer_table(query, TYPES_SHEET)
    return None if found is None else (found.value, found.unit)


def test_a_count_over_a_schedule_with_a_count_column_adds_the_counts() -> None:
    """A row of a type schedule is one type: "how many doors of type U41" is its printed Count
    (52), not one row."""
    u41 = TableFilter(values=("U41",), cue=("seal", "type"))
    assert on_types("count", u41, kind="door") == (52, "count")
    both = TableFilter(values=("U06", "U44"), cue=("doors", "types"))
    assert on_types("count", both, kind="door") == (65, "count")
    ss = TableFilter(values=("SS",), cue=("type",))
    assert on_types("count", ss, kind="window") == (118, "count")  # a Qty column too
    assert on_types("count", kind="window", every_row=True) == (206, "count")
    # a schedule of numbered doors has no count column: a row is a door
    assert on_types("count", TableFilter(values=("1HR",)), kind="door") == (1, "count")


def test_a_count_cell_that_is_no_number_is_no_answer() -> None:
    blank = table("DOOR SCHEDULE - TYPE", ("Count", "Type Mark"), ("12", "U01"), (None, "U02"))
    query = TableQuery(op="count", kind="door", every_row=True)
    assert answer_table(query, (blank,)) is None


def test_the_schedule_the_question_names_is_the_one_counted() -> None:
    """Both door schedules can count all their rows; "the door type schedule" names one."""
    assert on_types("count", kind="door", every_row=True) is None  # 2 rows or 136 doors
    named = on_types("count", kind="door", table=("door", "type"), every_row=True)
    assert named == (210, "count")
    # a name no title carries narrows nothing
    assert on_types("count", kind="door", table=("hardware",), every_row=True) is None


def test_a_type_is_read_from_the_type_schedule() -> None:
    u01 = TableFilter(values=("U01",), cue=("unit", "doors", "type"))
    assert on_types("read", u01, kind="door", column=(("fire", "rating"),)) == ("20 MIN.", None)
    assert on_types("read", u01, kind="door", column=(("frame", "material"),)) == ("HM", None)


def test_rows_are_named_by_words_their_description_has_or_starts_with() -> None:
    marvin = TableFilter(values=("Marvin Essential",), match="contains")
    assert on_types("count", marvin, kind="door") == (8, "count")
    third = TableFilter(values=("3rd floor",), match="contains")
    assert on_types("count", marvin, third, kind="door") == (6, "count")
    # "3RD FLOOR" is in U3-LR and U46; only U3-LR is a Marvin door
    assert on_types("count", third, kind="door") == (20, "count")
    swing = TableFilter(values=("SWING",), match="starts")
    assert on_types("count", swing, kind="door") == (66, "count")  # not "...SLIDING", not U01
    # whole words only: "Marvin Ess" is no name the schedule prints
    part = TableFilter(values=("Marvin Ess",), match="contains")
    assert on_types("count", part, kind="door") is None

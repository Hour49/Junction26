"""Two schedule reads (r8 BH, from golden's schedule diagnosis), on synthetic tables only:

- a read that names no row ("the width and height of a window in the window schedule") is
  answered when every row prints the same value, and refused when the rows differ;
- the area of a room named by its name or number, or of the rooms with a printed name, comes
  from a room schedule's area column when the takeoff has no such room (a schedule sheet with
  no plan); the takeoff's own room wins when it has one.
"""

from app.adapters.question_templates import TemplateParser
from app.core.answering.answer import SCHEDULE, answer_question
from app.core.answering.model import Answer, Prior, Question, TableQuery
from app.core.answering.tables import answer_table
from app.core.drawing.model import Table, TableRow
from app.core.pipeline.model import Quantity

PARSE = TemplateParser().parse
FILE = "data/demo/schedules.pdf"
BOX = (0.1, 0.1, 0.5, 0.5)


def table(title: str, columns: tuple[str, ...], *rows: tuple[str, ...]) -> Table:
    return Table(
        id=title,
        page=1,
        box=BOX,
        title=title,
        columns=columns,
        key_column=0,
        rows=tuple(
            TableRow(cells=cells, box=(0.1, 0.1 + i / 100, 0.5, 0.11 + i / 100))
            for i, cells in enumerate(rows)
        ),
    )


SAME = table(
    "WINDOW SCHEDULE",
    ("Type", "Width", "Height", "Frame"),
    ("W1", "3' - 0\"", "5' - 0\"", "AL"),
    ("W2", "3' - 0\"", "5' - 0\"", "WD"),
)
DIFFERENT = table(
    "WINDOW SCHEDULE",
    ("Type", "Width", "Height", "Frame"),
    ("W1", "3' - 0\"", "5' - 0\"", "AL"),
    ("W2", "4' - 0\"", "5' - 0\"", "WD"),
)
ROOMS = table(
    "ROOM FINISH SCHEDULE",
    ("Room Number", "Room Name", "Area", "Floor Finish"),
    ("1.01", "OFFICE", "145 SF", "F1"),
    ("1.02", "OFFICE", "123 SF", "F1"),
    ("1.03", "STORAGE", "40 SF", "F2"),
)


def test_a_schedule_read_that_names_no_row_is_a_read_of_every_row() -> None:
    parsed = PARSE("What are the width and height of a window in the window schedule?")
    assert isinstance(parsed, TableQuery)
    assert (parsed.op, parsed.kind, parsed.filters) == ("read", "window", ())
    assert parsed.column == (("width",), ("height",))


def test_it_is_answered_only_when_every_row_prints_the_same_value() -> None:
    parsed = PARSE("What are the width and height of a window in the window schedule?")
    assert isinstance(parsed, TableQuery)
    found = answer_table(parsed, (SAME,))
    assert found is not None and found.value == "3'-0\" wide x 5'-0\" high"
    assert answer_table(parsed, (DIFFERENT,)) is None  # the rows differ: no one answer


class NoPrior:
    def prior(self, source: str, family: str) -> Prior | None:
        return None


def ask(text: str, quantities: dict[str, Quantity], tables: tuple[Table, ...]) -> Answer:
    clock = iter(float(n) for n in range(100))
    return answer_question(
        Question(id=1, file=FILE, text=text),
        quantities,
        TemplateParser(),
        clock.__next__,
        NoPrior(),
        tables,
    )


def test_a_room_s_area_comes_from_the_room_schedule_on_a_sheet_with_no_plan() -> None:
    named = ask("What is the net floor area of room 1.01 ('OFFICE') in m²?", {}, (ROOMS,))
    assert (named.answer, named.unit, named.method) == (145, "ft2", SCHEDULE)
    assert named.evidence and named.evidence[0].page == 1
    labelled = ask("What is the total net area of all rooms labelled 'OFFICE'?", {}, (ROOMS,))
    assert (labelled.answer, labelled.unit, labelled.method) == (268, "ft2", SCHEDULE)


def test_without_a_room_schedule_or_that_room_it_is_still_refused() -> None:
    assert ask("What is the net floor area of room 1.01 ('OFFICE') in m²?", {}, ()).answer is None
    missing = ask("What is the net floor area of room 2.01 ('HALL') in m²?", {}, (ROOMS,))
    assert missing.answer is None and missing.method != SCHEDULE


def test_the_takeoff_s_own_room_wins_over_the_schedule() -> None:
    measured = Quantity(
        key="area:room|name=1.01", value=13.2, unit="m2", rule="room_area", marks=()
    )
    found = ask(
        "What is the net floor area of room 1.01 ('OFFICE') in m²?",
        {"area:room|name=1.01": measured},
        (ROOMS,),
    )
    assert (found.answer, found.unit) == (13.2, "m2") and found.method != SCHEDULE

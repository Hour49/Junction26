"""Answering: a query is looked up in the drawing's takeoff; everything else is a refusal with
its reason in `method`."""

from collections.abc import Iterator

from app.core.answering.answer import (
    NO_DRAWING,
    NOT_IN_DRAWING,
    TAKEOFF,
    UNSUPPORTED_QUESTION,
    answer_question,
    answer_questions,
)
from app.core.answering.model import Answer, Evidence, Query, Question, Unsupported
from app.core.drawing.model import Drawing, Element, Page, Scale
from app.core.pipeline.takeoff import known_quantities

BOX_1, BOX_2 = (0.1, 0.2, 0.3, 0.4), (0.5, 0.5, 0.6, 0.6)
FILE = "data/demo/a.png"


def drawing(counts: dict[str, int] | None = None) -> Drawing:
    return Drawing(
        file=FILE,
        pages=(Page(page=1, width=100, height=50, unit="px"),),
        scale=Scale(status="no_scale"),
        elements=()
        if counts
        else (
            Element(id="e1", class_="door", page=1, box=BOX_1),
            Element(id="e2", class_="door", page=1, box=BOX_2),
        ),
        counts=counts,
    )


class DoorParser:
    """Understands exactly one question."""

    def __init__(self) -> None:
        self.asked: list[str] = []

    def parse(self, text: str) -> Query | Unsupported:
        self.asked.append(text)
        if text == "How many doors?":
            return Query(quantity="door")
        if text == "How many saunas?":
            return Query(quantity="room:sauna")
        return Unsupported(reason="not a question this parser knows")


def ticking_clock() -> Iterator[float]:
    """0.0, 0.25, 0.5, ... so every answer takes exactly 0.25 s."""
    now = 0.0
    while True:
        yield now
        now += 0.25


def ask(text: str, source: Drawing | None, parser: DoorParser | None = None) -> Answer:
    quantities = None if source is None else known_quantities(source)
    question = Question(id=7, file=FILE, text=text)
    return answer_question(question, quantities, parser or DoorParser(), ticking_clock().__next__)


def test_a_count_is_answered_from_the_takeoff_with_its_marks_as_evidence() -> None:
    answer = ask("How many doors?", drawing())
    assert answer == Answer(
        id=7,
        answer=2,
        unit="count",
        evidence=(
            Evidence(file=FILE, page=1, box=BOX_1),
            Evidence(file=FILE, page=1, box=BOX_2),
        ),
        method=TAKEOFF,
        cost_usd=0.0,
        latency_s=0.25,
    )


def test_a_class_the_drawing_lists_nothing_of_counts_zero() -> None:
    answer = ask("How many saunas?", drawing())
    assert (answer.answer, answer.unit, answer.evidence, answer.method) == (0, "count", (), TAKEOFF)


def test_an_unsupported_question_is_refused() -> None:
    answer = ask("What is the fire rating of door 101A?", drawing())
    assert (answer.answer, answer.unit, answer.evidence) == (None, None, ())
    assert answer.method == UNSUPPORTED_QUESTION


def test_a_file_without_a_drawing_model_is_refused_before_the_parser_is_asked() -> None:
    parser = DoorParser()
    answer = ask("How many doors?", None, parser)
    assert (answer.answer, answer.method) == (None, NO_DRAWING)
    assert parser.asked == []


def test_a_quantity_the_stated_totals_leave_out_is_refused_not_zero() -> None:
    totals = drawing(counts={"door": 9})
    assert ask("How many doors?", totals).answer == 9
    missing = ask("How many saunas?", totals)
    assert (missing.answer, missing.method) == (None, NOT_IN_DRAWING)


class Drawings:
    def __init__(self) -> None:
        self.loaded: list[str] = []

    def drawing(self, file: str) -> Drawing | None:
        self.loaded.append(file)
        return drawing() if file == FILE else None


class Collected:
    def __init__(self) -> None:
        self.answers: list[Answer] = []

    def write(self, answer: Answer) -> None:
        self.answers.append(answer)


def test_answer_questions_loads_each_drawing_once_and_tallies_the_methods() -> None:
    questions = [
        Question(id=1, file=FILE, text="How many doors?"),
        Question(id=2, file="data/demo/missing.pdf", text="How many doors?"),
        Question(id=3, file=FILE, text="Is this a nice plan?"),
        Question(id=4, file=FILE, text="How many doors?"),
    ]
    drawings, sink = Drawings(), Collected()

    methods = answer_questions(
        questions,
        drawings=drawings,
        parser=DoorParser(),
        clock=ticking_clock().__next__,
        sink=sink,
    )

    assert methods == {TAKEOFF: 2, UNSUPPORTED_QUESTION: 1, NO_DRAWING: 1}
    assert drawings.loaded == [FILE, "data/demo/missing.pdf"]
    assert {answer.id: answer.answer for answer in sink.answers} == {1: 2, 2: None, 3: None, 4: 2}

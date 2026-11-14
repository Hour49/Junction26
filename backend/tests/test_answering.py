"""Answering: a query is looked up in the drawing's takeoff; everything else is a refusal with
its reason in `method`, which keeps the prior's best estimate when there is one."""

import logging
from collections.abc import Iterator
from dataclasses import dataclass

import pytest

from app.core.answering.answer import (
    NO_DRAWING,
    NOT_IN_DRAWING,
    POLICY_WHY,
    PRIOR_BY_POLICY,
    SCHEDULE,
    TAKEOFF,
    UNSUPPORTED_QUESTION,
    answer_question,
    answer_questions,
)
from app.core.answering.model import (
    Answer,
    Evidence,
    Prior,
    Query,
    Question,
    TableFilter,
    TableQuery,
    Unsupported,
    source_of,
)
from app.core.answering.tables import MEANING_WHY
from app.core.drawing.model import (
    Drawing,
    Element,
    Page,
    Plan,
    ReadClass,
    Room,
    Scale,
    Table,
    TableRow,
)
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
            return Query(subject="door")
        if text == "How many saunas?":
            return Query(subject="room:sauna")
        if text == "How mnay doros?":
            return Query(subject="door", read_as=("'mnay' as 'many'", "'doros' as 'doors'"))
        if text == "How mnay saunas?":
            return Query(subject="room:sauna", read_as=("'mnay' as 'many'",))
        return Unsupported(reason="not a question this parser knows")


def ticking_clock() -> Iterator[float]:
    """0.0, 0.25, 0.5, ... so every answer takes exactly 0.25 s."""
    now = 0.0
    while True:
        yield now
        now += 0.25


class NoPrior:
    def prior(self, source: str, family: str) -> Prior | None:
        return None


class SaunaPrior:
    """A prior for one family on the demo source."""

    def __init__(self) -> None:
        self.asked: list[tuple[str, str]] = []

    def prior(self, source: str, family: str) -> Prior | None:
        self.asked.append((source, family))
        if (source, family) == ("demo", "room:sauna"):
            return Prior(value=1, unit="count", confidence=0.57, n=40)
        return None


def ask(
    text: str,
    source: Drawing | None,
    parser: DoorParser | None = None,
    prior: NoPrior | SaunaPrior | None = None,
) -> Answer:
    quantities = None if source is None else known_quantities(source)
    question = Question(id=7, file=FILE, text=text)
    return answer_question(
        question, quantities, parser or DoorParser(), ticking_clock().__next__, prior or NoPrior()
    )


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
    assert (answer.abstain, answer.explanation) == (True, "not a question this parser knows")


def test_every_refusal_abstains_and_an_answer_does_not() -> None:
    assert ask("How many doors?", None).abstain is True
    missing = ask("How many saunas?", drawing(counts={"door": 9}))
    assert (missing.abstain, missing.explanation) == (
        True,
        "the drawing model does not give room:sauna",
    )
    answered = ask("How many doors?", drawing())
    assert (answered.abstain, answered.explanation) == (None, None)


def test_an_answer_to_a_misspelt_question_says_how_it_was_read() -> None:
    answered = ask("How mnay doros?", drawing())
    assert (answered.answer, answered.explanation) == (
        2,
        "read 'mnay' as 'many', 'doros' as 'doors'",
    )
    missing = ask("How mnay saunas?", drawing(counts={"door": 9}))
    assert missing.explanation == (
        "read 'mnay' as 'many'; the drawing model does not give room:sauna"
    )


def test_a_file_without_a_drawing_model_is_refused() -> None:
    answer = ask("How many doors?", None)
    assert (answer.answer, answer.method) == (None, NO_DRAWING)
    assert answer.explanation == "the file has no drawing model"


def test_a_refusal_with_a_prior_carries_its_value_and_abstains() -> None:
    prior = SaunaPrior()
    answer = ask("How many saunas?", drawing(counts={"door": 9}), prior=prior)
    assert (answer.answer, answer.unit, answer.evidence) == (1, "count", ())
    assert (answer.method, answer.abstain, answer.confidence) == (NOT_IN_DRAWING, True, 0.57)
    assert answer.explanation == (
        "not read from the drawing; dev prior for demo room:sauna "
        "(the drawing model does not give room:sauna)"
    )
    assert prior.asked == [("demo", "room:sauna")]
    no_drawing = ask("How many saunas?", None, prior=prior)
    assert (no_drawing.answer, no_drawing.method, no_drawing.abstain) == (1, NO_DRAWING, True)


def test_a_refusal_without_a_prior_stays_null() -> None:
    prior = SaunaPrior()
    answer = ask("How many doors?", None, prior=prior)  # no prior for doors
    assert (answer.answer, answer.unit, answer.confidence, answer.abstain) == (
        None,
        None,
        None,
        True,
    )
    unsupported = ask("Is this a nice plan?", drawing(), prior=prior)
    assert (unsupported.answer, unsupported.method) == (None, UNSUPPORTED_QUESTION)
    assert prior.asked == [("demo", "door")]  # an unsupported question has no family


def test_an_answer_from_the_takeoff_never_asks_the_prior() -> None:
    prior = SaunaPrior()
    assert ask("How many saunas?", drawing(), prior=prior).answer == 0
    assert prior.asked == []


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
        prior=NoPrior(),
    )

    assert methods == {TAKEOFF: 2, UNSUPPORTED_QUESTION: 1, NO_DRAWING: 1}
    assert drawings.loaded == [FILE, "data/demo/missing.pdf"]
    assert {answer.id: answer.answer for answer in sink.answers} == {1: 2, 2: None, 3: None, 4: 2}


def test_a_family_masks_every_filter_value_and_keeps_the_rest() -> None:
    room = Query(measure="area", subject="room", name="Office (0.04)", storey="EG")
    assert room.family() == "area:room|name=*|storey=*"
    assert Query(subject="room", label="Bad").family() == "room|label=*"
    assert Query(subject="door", storey="EG", model=True).family() == "door|storey=*|model"
    assert Query(measure="area", subject="room", indoor=True).family() == "area:room|indoor"
    assert Query(subject="window").family() == Query(subject="window").key() == "window"
    assert (source_of("data/ifc_models/a.pdf"), source_of("elsewhere.pdf")) == ("ifc_models", "")


class AreaParser:
    def parse(self, text: str) -> Query | Unsupported:
        return Query(measure="area", subject="room")


def test_an_answer_resting_on_an_estimated_scale_is_labelled_an_estimate() -> None:
    estimated = Drawing(
        file=FILE,
        pages=(Page(page=1, width=100, height=50, unit="px"),),
        scale=Scale(status="estimated", m_per_unit=0.02, source="door widths"),
        rooms=(Room(id="r1", type="sauna", page=1, box=BOX_1, area_m2=4.0),),
    )
    question = Question(id=7, file=FILE, text="How big are the rooms?")
    answer = answer_question(
        question, known_quantities(estimated), AreaParser(), ticking_clock().__next__, NoPrior()
    )
    assert (answer.answer, answer.unit, answer.method) == (4.0, "m2", TAKEOFF)
    assert (answer.estimate, answer.abstain) == (True, None)
    assert answer.explanation == "rests on an estimated scale (door widths)"
    assert ask("How many saunas?", estimated).estimate is None  # a count: no scale in it


class WindowPrior:
    def prior(self, source: str, family: str) -> Prior | None:
        return Prior(value=4, unit="count", confidence=0.13, n=7656) if family == "window" else None


class WindowParser:
    def parse(self, text: str) -> Query | Unsupported:
        return Query(subject="window")


def test_a_class_the_extraction_did_not_read_gets_the_prior_never_a_confident_zero() -> None:
    def window_count(read: tuple[ReadClass, ...] | None) -> Answer:
        sheet = Drawing(file=FILE, pages=(Page(page=1, width=1, height=1, unit="px"),),
                        scale=Scale(status="no_scale"), read=read)  # fmt: skip
        question = Question(id=7, file=FILE, text="How many windows?")
        quantities = known_quantities(sheet)
        return answer_question(
            question, quantities, WindowParser(), ticking_clock().__next__, WindowPrior()
        )

    unread = window_count(())
    assert (unread.answer, unread.method, unread.abstain) == (4, NOT_IN_DRAWING, True)
    read_all = window_count(None)
    assert (read_all.answer, read_all.method, read_all.abstain) == (0, TAKEOFF, None)


class TableParser:
    def parse(self, text: str) -> Query | TableQuery | Unsupported:
        return TableQuery(op="count", kind="door", every_row=True)


def test_a_schedule_question_is_answered_from_the_sheet_s_tables_with_its_rows_as_evidence() -> (
    None
):
    rows = (TableRow(cells=("1",), box=BOX_1), TableRow(cells=("2",), box=BOX_2))
    doors = Table(id="t1", page=1, box=BOX_1, title="Door Schedule", columns=("Mark",), rows=rows)
    question = Question(id=7, file=FILE, text="How many doors are listed?")
    quantities = known_quantities(drawing())
    answer = answer_question(
        question, quantities, TableParser(), ticking_clock().__next__, NoPrior(), (doors,)
    )
    assert (answer.answer, answer.unit, answer.method) == (2, "count", SCHEDULE)
    assert [e.box for e in answer.evidence] == [BOX_1, BOX_2]
    missing = answer_question(
        question, quantities, TableParser(), ticking_clock().__next__, NoPrior()
    )
    assert (missing.answer, missing.method, missing.abstain) == (None, NOT_IN_DRAWING, True)
    assert (answer.abstain, answer.explanation) == (None, None)


class FinishParser:
    def parse(self, text: str) -> Query | TableQuery | Unsupported:
        room = TableFilter(values=("128",), cue=("room",))
        return TableQuery(op="read", kind="room", column=(("ceiling", "finish"),), filters=(room,))


def test_a_schedule_answer_in_the_sheet_s_key_words_abstains_and_keeps_its_value() -> None:
    finishes = Table(id="t1", page=1, box=BOX_1, title="FINISH ROOM SCHEDULE",
                     columns=("Room Number", "Ceiling Finish"),
                     rows=(TableRow(cells=("128", "C2"), box=BOX_1),))  # fmt: skip
    key = Table(id="t2", page=1, box=BOX_2, title="FINISH KEY", columns=("Key", "Description"),
                rows=(TableRow(cells=("C2", "LINER - COLOR: WHITE")),))  # fmt: skip
    question = Question(id=7, file=FILE, text="What is the ceiling finish of room 128?")
    answer = answer_question(
        question,
        known_quantities(drawing()),
        FinishParser(),
        ticking_clock().__next__,
        NoPrior(),
        (finishes, key),
    )
    assert (answer.answer, answer.method) == ("C2 - LINER - COLOR: WHITE", SCHEDULE)
    assert (answer.abstain, answer.explanation) == (True, MEANING_WHY)


def _windows_on_storey_0(*conflicts: dict[str, object]) -> Drawing:
    """5 windows drawn on a plan of storey 0, and the drawing's stage-8 entries."""
    return Drawing.model_validate(
        {
            "file": FILE,
            "pages": [{"page": 1, "width": 100, "height": 50, "unit": "px"}],
            "scale": {"status": "scaled"},
            "plans": [{"id": "p1", "page": 1, "box": BOX_2, "storey": "0"}],
            "elements": [
                {"id": f"e{n}", "class": "window", "page": 1, "box": BOX_1, "plan": "p1"}
                for n in range(5)
            ],
            "conflicts": list(conflicts),
        }
    )


def _window_entry(status: str, other: int, resolution: dict[str, object] | None) -> dict:
    return {
        "id": "c1",
        "quantity": "element_count",
        "subject": {"kind": "class", "ref": "window"},
        "status": status,
        "tolerance": 0,
        "values": [
            {"value": 5, "unit": "count", "method": "plan_drawing", "page": 1, "box": BOX_1},
            {"value": other, "unit": "count", "method": "ifc_model", "page": 1, "box": BOX_2},
        ],
        "resolution": resolution,
        "note": "the undrawn IFC windows sit above the 1.20 m cut",
    }


class StoreyWindowParser:
    def parse(self, text: str) -> Query | Unsupported:
        return Query(subject="window", storey="0")


def _ask_windows(sheet: Drawing) -> Answer:
    question = Question(id=7, file=FILE, text="How many windows are shown on the plan of '0'?")
    return answer_question(
        question, known_quantities(sheet), StoreyWindowParser(), ticking_clock().__next__, NoPrior()
    )


def test_a_conflicted_count_answers_the_resolved_value_and_shows_both_values() -> None:
    rule = {"rule": "count what the sheet draws", "value": 5}
    answer = _ask_windows(_windows_on_storey_0(_window_entry("conflict", 7, rule)))
    assert (answer.answer, answer.unit, answer.method, answer.abstain) == (
        5,
        "count",
        TAKEOFF,
        None,
    )
    assert answer.conflicts is not None
    shown = [(c.value, c.unit, c.method, c.file, c.page, c.box) for c in answer.conflicts]
    assert shown == [
        (5, "count", "plan_drawing", FILE, 1, BOX_1),
        (7, "count", "ifc_model", FILE, 1, BOX_2),
    ]
    assert answer.resolution == "kept 5: count what the sheet draws"
    assert answer.explanation == (
        "two methods disagree (plan_drawing 5, ifc_model 7); kept 5: count what the sheet draws; "
        "the undrawn IFC windows sit above the 1.20 m cut"
    )
    assert len(answer.evidence) == 5  # the resolved value is the takeoff's own, so its marks


def test_an_agree_entry_changes_nothing() -> None:
    agree = _window_entry("agree", 5, {"rule": "both methods agree", "value": 5})
    assert _ask_windows(_windows_on_storey_0(agree)) == _ask_windows(_windows_on_storey_0())


def test_an_unresolved_conflict_shows_both_values_and_abstains() -> None:
    answer = _ask_windows(_windows_on_storey_0(_window_entry("conflict", 7, None)))
    assert (answer.answer, answer.abstain, answer.resolution) == (5, True, None)
    assert answer.conflicts is not None and [c.value for c in answer.conflicts] == [5, 7]
    assert answer.explanation is not None
    assert answer.explanation.startswith(
        "two methods disagree (plan_drawing 5, ifc_model 7) and no rule decides between them"
    )


class PlanParser:
    def parse(self, text: str) -> Query | Unsupported:
        return Query(subject="plan")


class PlanPrior:
    def prior(self, source: str, family: str) -> Prior | None:
        return Prior(value=3, unit="count", confidence=0.8, n=100) if family == "plan" else None


def test_a_sheet_that_read_nothing_gets_the_prior_for_its_plan_count_not_zero() -> None:
    def plan_count(read: tuple[ReadClass, ...]) -> Answer:
        sheet = Drawing(file=FILE, pages=(Page(page=1, width=1, height=1, unit="px"),),
                        scale=Scale(status="no_scale"), read=read,
                        plans=(Plan(id="p1", page=1, box=BOX_1),))  # fmt: skip
        question = Question(id=7, file=FILE, text="How many floors (storeys) are drawn?")
        return answer_question(
            question, known_quantities(sheet), PlanParser(), ticking_clock().__next__, PlanPrior()
        )

    unread = plan_count(())
    assert (unread.answer, unread.method, unread.abstain) == (3, NOT_IN_DRAWING, True)
    swiss = plan_count(("door", "window", "room"))  # what the vector extractor reads
    assert (swiss.answer, swiss.method, swiss.abstain) == (1, TAKEOFF, None)


def test_the_answer_policy_sends_a_family_to_the_prior_on_its_source_only() -> None:
    """ANSWER_POLICY: a (source, family) the reader loses to the prior on val is answered from
    the prior, abstaining, although the drawing gives a value. Other families, other sources
    and a family the prior has no value for keep the takeoff's answer."""
    prior = SaunaPrior()
    question = Question(id=7, file=FILE, text="How many saunas?")
    quantities = known_quantities(drawing())

    def answer(pairs: frozenset[tuple[str, str]], q: Question = question) -> Answer:
        clock = ticking_clock().__next__
        return answer_question(q, quantities, DoorParser(), clock, prior, (), pairs)

    sent = answer(frozenset({("demo", "room:sauna")}))
    assert (sent.answer, sent.unit, sent.evidence, sent.method) == (1, "count", (), PRIOR_BY_POLICY)
    assert (sent.abstain, sent.confidence, sent.explanation) == (True, 0.57, POLICY_WHY)
    assert answer(frozenset({("other", "room:sauna")})).method == TAKEOFF  # another source
    assert answer(frozenset()).answer == 0  # no policy: the takeoff's 0
    doors = Question(id=8, file=FILE, text="How many doors?")
    no_prior = answer(frozenset({("demo", "door")}), doors)  # the prior has no doors value
    assert (no_prior.answer, no_prior.method) == (2, TAKEOFF)


@dataclass(frozen=True)
class Rated:
    value: float | None
    note: str


class FakeConfidence:
    """DECISIONS_CONFIDENCE's stand-in: a fixed probability, or None with a note."""

    def __init__(self, value: float | None) -> None:
        self.value = value
        self.asked: list[tuple[str, str, object]] = []

    def probability(self, path: str, family: str, value: object) -> Rated:
        self.asked.append((path, family, value))
        return Rated(self.value, "decisions: P(2) = 0.81" if self.value else "decisions: down")


def rated(
    text: str,
    source: Drawing | None,
    confidence: FakeConfidence,
    parser: DoorParser | AreaParser | None = None,
) -> Answer:
    quantities = None if source is None else known_quantities(source)
    question = Question(id=7, file=FILE, text=text)
    clock = ticking_clock().__next__
    return answer_question(
        question, quantities, parser or DoorParser(), clock, SaunaPrior(), confidence=confidence
    )


def test_a_takeoff_answer_gets_the_probability_of_its_value() -> None:
    sure = FakeConfidence(0.81)
    answer = rated("How many doors?", drawing(), sure)
    assert (answer.answer, answer.method, answer.confidence) == (2, TAKEOFF, 0.81)
    assert answer.explanation is None  # the note only says why when there is no probability
    assert sure.asked == [(FILE, "door", 2)]


def test_without_a_probability_the_answer_is_unchanged_and_the_reason_is_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    down = FakeConfidence(None)
    with caplog.at_level(logging.INFO, logger="app.core.answering.answer"):
        answer = rated("How many doors?", drawing(), down)
    assert (answer.confidence, answer.explanation) == (None, None)
    assert "question 7: no confidence: decisions: down" in caplog.text
    estimated = Drawing(
        file=FILE,
        pages=(Page(page=1, width=100, height=50, unit="px"),),
        scale=Scale(status="estimated", m_per_unit=0.02, source="door widths"),
        rooms=(Room(id="r1", type="sauna", page=1, box=BOX_1, area_m2=4.0),),
    )
    area = rated("How big?", estimated, down, AreaParser())
    assert area.explanation == "rests on an estimated scale (door widths)"  # the takeoff's own


def test_refusals_and_prior_answers_are_not_rated() -> None:
    sure = FakeConfidence(0.81)
    assert rated("How many doors?", None, sure).confidence is None  # no drawing
    assert rated("What colour?", drawing(), sure).method == UNSUPPORTED_QUESTION
    assert sure.asked == []


def test_answer_questions_passes_the_confidence_on() -> None:
    sink, sure = Collected(), FakeConfidence(0.81)
    answer_questions(
        [Question(id=1, file=FILE, text="How many doors?")],
        drawings=Drawings(),
        parser=DoorParser(),
        clock=ticking_clock().__next__,
        sink=sink,
        prior=NoPrior(),
        confidence=sure,
    )
    assert [a.confidence for a in sink.answers] == [0.81]

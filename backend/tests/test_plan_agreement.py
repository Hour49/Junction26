"""Plans on page are sure only when Gemini's own plan count is the answered one (two readers
agree), whatever its score: the gate certified every val plan answer (threshold 0.014), and three
hand-drawn sketches got sure, wrong plan counts while Gemini's count was another
(.agents/exp/handdrawn.md, brief answer-next, 2026-11-14)."""

from test_answering import NoPrior, ticking_clock
from test_decisions import FILE, Files, fake, reply

from app.adapters.decisions.g1main import G1MainReader
from app.adapters.decisions.uses import DecisionsConfidence
from app.adapters.question_templates import TemplateParser
from app.core.answering.answer import answer_question
from app.core.answering.model import Question
from app.core.drawing.model import Drawing, Page, Plan, Scale
from app.core.pipeline.takeoff import known_quantities

FLOORS = "How many floors (storeys) does this floor plan show?"
DOORS = "How many doors are shown on this floor plan?"
GATE = {"plan": 0.014, "door": 0.5}  # gate-C-L-swap's plan threshold


def two_plans() -> Drawing:
    return Drawing(
        file=FILE.path,
        pages=(Page(page=1, width=100, height=50, unit="px"),),
        scale=Scale(status="no_scale"),
        plans=(
            Plan(id="p1", page=1, box=(0.0, 0.0, 0.5, 1.0)),
            Plan(id="p2", page=1, box=(0.5, 0.0, 1.0, 1.0)),
        ),
    )


def answered(text: str, dists: dict[str, dict[int, float]]) -> tuple[object, float | None, object]:
    confidence = DecisionsConfidence(Files(), G1MainReader(fake(reply(dists)), None))
    found = answer_question(
        Question(id=1, file=FILE.path, text=text), known_quantities(two_plans()), TemplateParser(),
        ticking_clock().__next__, NoPrior(), confidence=confidence, sure_at=GATE,
    )  # fmt: skip
    return found.answer, found.confidence, found.sure


def test_a_plan_count_gemini_counts_otherwise_is_not_sure_however_high_its_score() -> None:
    # hd05 Parshall: 2 plans read, Gemini 0.93 on 1 and 0.05 on 2 (above the 0.014 threshold)
    assert answered(FLOORS, {"plan": {1: 0.93, 2: 0.055, 0: 0.015}}) == (2, 0.055, False)
    assert answered(FLOORS, {"plan": {2: 0.6, 1: 0.4}}) == (2, 0.6, True)  # the readers agree
    assert answered(FLOORS, {"plan": {2: 0.5, 1: 0.5}}) == (2, 0.5, False)  # a tie goes to 1


def test_other_families_keep_the_score_alone() -> None:
    """Doors (0 here) are sure on the score, even where Gemini's own count is another."""
    assert answered(DOORS, {"door": {1: 0.9, 0: 0.6}}) == (0, 0.6, True)


def test_the_confidence_says_whether_gemini_s_own_count_is_the_answered_one() -> None:
    confidence = DecisionsConfidence(Files(), G1MainReader(fake(reply({"plan": {1: 0.7}})), None))
    assert confidence.probability(FILE.path, "plan", 1).agrees is True
    assert confidence.probability(FILE.path, "plan", 2).agrees is False
    assert confidence.probability(FILE.path, "area:room:*", 3).agrees is None  # not scored

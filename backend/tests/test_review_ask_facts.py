"""The chat's ask answers from the drawing's fact sheet (an IFC model's, a services picture's) the
way answer_questions does: only when the takeoff, the schedules and the dev prior give nothing;
Low, never sure, its marks the facts' spots."""

from collections.abc import Callable

from test_levels import POLICY, SCAN, Scored

from app.adapters.answer_prior import NoPrior
from app.adapters.question_templates import TemplateParser
from app.core.answering.facts import FACTS
from app.core.ifc_facts import Fact, FactSheet, Spot
from app.core.review.ask import FACTS_REASON, Asked, ask
from app.core.review.check import CheckPolicy
from app.core.review.model import ReviewState

SPOTS = (
    Spot(page=1, box=(0.1, 0.1, 0.12, 0.12), reader="vlm"),
    Spot(page=1, box=(0.5, 0.5, 0.52, 0.52), reader="vlm"),
)
SHEET = FactSheet(
    model="d1",
    disciplines=["electrical"],
    facts=[
        Fact(topic="outlet.count", subject=subject, value=2, unit="count",
             discipline="electrical", source="picture:vlm+template", spots=SPOTS)
        for subject in ("all", "Socket 230 V")
    ],
)  # fmt: skip
OUTLETS = "How many outlets are there?"


def asked(
    text: str,
    check: CheckPolicy | None = POLICY,
    facts: Callable[[], FactSheet | None] | None = None,
) -> Asked:
    return ask(
        text, SCAN, parser=TemplateParser(), clock=lambda: 0.0, prior=NoPrior(),
        state=ReviewState(), confidence=Scored(0.9), raster=True, check=check, route="raster",
        facts=facts,
    )  # fmt: skip


def test_a_question_the_takeoff_cannot_answer_is_answered_from_the_fact_sheet() -> None:
    found = asked(OUTLETS, facts=lambda: SHEET)
    assert found.answer.method == FACTS and found.refusal is None
    assert isinstance(found.answer.answer, str) and "Total outlets: 2" in found.answer.answer
    assert [m.box for m in found.marks] == [s.box for s in SPOTS]  # the facts' spots
    assert found.level is not None and found.level.level == "low"
    assert found.answer.sure is None  # never sure


def test_without_the_policy_a_fact_answer_has_no_level() -> None:
    found = asked(OUTLETS, check=None, facts=lambda: SHEET)
    assert found.answer.method == FACTS and found.level is None


def test_the_takeoff_answers_first_and_the_sheet_is_not_built() -> None:
    built: list[int] = []

    def sheet() -> FactSheet:
        built.append(1)
        return SHEET

    found = asked("How many doors are there?", facts=sheet)
    assert found.answer.method != FACTS and found.refusal is None and built == []


def test_without_a_fact_sheet_the_ask_is_as_before() -> None:
    before = asked(OUTLETS)
    assert before.refusal is not None
    assert asked(OUTLETS, facts=None) == before
    assert asked(OUTLETS, facts=lambda: None) == before


def test_a_fact_answer_asks_for_a_double_check_like_every_low_answer() -> None:
    found = asked(OUTLETS, facts=lambda: SHEET)
    assert found.check is not None and found.check.reason == FACTS_REASON
    assert found.check.disputed == ()  # no reader points anywhere
    assert asked(OUTLETS, check=None, facts=lambda: SHEET).check is None  # the policy off

"""CARBON_LEVELS=ladder (brief r8 BQ, Bogdan 19:4x "make them high"): as demote, and a Medium
answer Carbon answers with the same value becomes High, because two readers agree. Carbon alone
never makes an answer High or certified; a Low or High stays; a person's sign-off or settled value
wins; a failed check keeps today's level."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.adapters.answer_prior import NoPrior
from app.adapters.carbon import CarbonChecked
from app.adapters.carbon.contract import READER_SHA
from app.adapters.question_templates import TemplateParser
from app.api import ask as api_ask
from app.composition import build_answering, build_ingest, build_pipeline
from app.core.drawing.model import CarbonCheck, Drawing, Element, Plan
from app.core.review.ask import Asked, ask
from app.core.review.check import CARBON_AGREED, CheckPolicy, Level, carbon_checked
from app.core.review.model import ReviewState, Settled
from tests.test_carbon_levels import MEDIUM, THREE, settings_with
from tests.test_levels import COUNTS, DOORS, POLICY, SCAN, SIGNED, Scored, made

AGREES = {"read": ("door", "room"), "elements": DOORS}  # 2 doors, as the reader
DISAGREES = {"read": ("door", "room"), "elements": THREE}
REFUSES = {"read": ("window", "room")}  # it did not count doors


class Agreeing(Scored):
    def __init__(self, value: float | None, agrees: bool | None) -> None:
        super().__init__(value)
        self.agrees = agrees


def laddered(
    score: float | None = MEDIUM,
    *,
    carbon: dict[str, Any] | None = None,
    ladder: bool = True,
    text: str = "How many doors are there?",
    drawing: Drawing = SCAN,
    policy: CheckPolicy = POLICY,
    state: ReviewState | None = None,
    agrees: bool | None = None,
) -> Asked:
    if carbon is not None:
        drawing = drawing.model_copy(update={"carbon_check": CarbonCheck(**carbon)})
    return ask(
        text, drawing, parser=TemplateParser(), clock=lambda: 0.0, prior=NoPrior(),
        state=state or ReviewState(), confidence=Agreeing(score, agrees), raster=True,
        check=policy, route="raster", carbon_ladder=ladder,
    )  # fmt: skip


def test_a_medium_answer_carbon_counts_the_same_becomes_high_and_asks_nothing() -> None:
    found = laddered(carbon=AGREES)
    assert made(found) == ("high", "carbon")
    assert found.level is not None and found.level.text.startswith(
        "High confidence: checked by Carbon: two readers agree."
    )
    assert f"({CARBON_AGREED.exact} of {CARBON_AGREED.units})" in found.level.text
    assert found.check is None  # High never asks for a double-check
    assert found.answer.sure is False  # Carbon never certifies: the check policy's verdict stays
    assert found.answer.answer == 2


def test_demote_leaves_an_agreed_medium_answer_medium() -> None:
    found = laddered(carbon=AGREES, ladder=False)
    assert made(found) == ("medium", "score") and found.check is not None


def test_a_medium_answer_carbon_counts_differently_becomes_low_as_demote() -> None:
    found = laddered(carbon=DISAGREES)
    assert made(found) == ("low", "carbon") and found.check is not None
    assert found.level == laddered(carbon=DISAGREES, ladder=False).level


@pytest.mark.parametrize("carbon", [REFUSES, None], ids=["refuses", "no-check"])
def test_carbon_refusing_or_not_running_leaves_medium(carbon: dict[str, Any] | None) -> None:
    found = laddered(carbon=carbon)
    assert made(found) == ("medium", "score") and found.check is not None


def test_a_failed_check_keeps_today_s_level_and_says_so() -> None:
    found = laddered(carbon={"failed": "the check failed: ValueError"})
    assert made(found) == ("medium", "score") and found.check is not None
    assert found.level is not None
    assert found.level.text.endswith(
        "Gemini Carbon did not check it: the check failed: ValueError."
    )


@pytest.mark.parametrize(("score", "level", "basis"), [(0.9, "high", "certified"),
                                                       (0.1, "low", "score")])  # fmt: skip
def test_low_stays_low_and_high_stays_high(score: float, level: str, basis: str) -> None:
    for carbon in (AGREES, DISAGREES, REFUSES):
        assert made(laddered(score, carbon=carbon)) == (level, basis)


def test_a_flagged_page_answer_stays_low_whatever_carbon_reads() -> None:
    found = ask(
        "How many doors are there?",
        SCAN.model_copy(update={"carbon_check": CarbonCheck(**AGREES)}),
        parser=TemplateParser(), clock=lambda: 0.0, prior=NoPrior(), state=ReviewState(),
        confidence=Scored(MEDIUM), flags=("a phone photo",), raster=True, check=POLICY,
        route="raster", carbon_ladder=True,
    )  # fmt: skip
    assert made(found) == ("low", "page")


def test_a_person_s_sign_off_or_settled_value_wins() -> None:
    signed = ReviewState(signed={"door": SIGNED})
    settled = ReviewState(settled={"door": Settled(value=3, at="2026-11-14T12:00:00Z")})
    for state in (signed, settled):
        assert laddered(carbon=AGREES, state=state).level is None


def test_carbon_agreeing_does_not_settle_a_disagreement_the_gate_found() -> None:
    """A plan count asks when the answer confidence's own count differs (`agrees` False);
    Carbon reading the same count as the reader does not make that answer High."""
    policy = CheckPolicy(thresholds={"plan": 0.8}, medium={"plan": 0.4}, counts=COUNTS)
    plans = (Plan(id="p1", page=1, box=(0.0, 0.0, 1.0, 1.0)),)
    drawing = SCAN.model_copy(update={"plans": plans})
    carbon = {"read": ("door", "room"), "plans": plans}
    ask_plans = {"text": "How many floor plans are there?", "drawing": drawing, "policy": policy}
    agreed = laddered(carbon=carbon, agrees=True, **ask_plans)
    assert made(agreed) == ("high", "carbon")
    held = laddered(carbon=carbon, agrees=False, **ask_plans)
    assert made(held) == ("medium", "score") and held.check is not None


def test_carbon_checked_moves_only_medium_up_with_ladder() -> None:
    medium = Level(level="medium", basis="score", text="Medium.")
    check = CarbonCheck(read=("door",), elements=(Element(id="e1", class_="door", page=1,
                                                          box=(0.1, 0.1, 0.2, 0.2)),))  # fmt: skip
    assert carbon_checked(medium, check, 2, 2) == medium  # demote
    assert carbon_checked(medium, check, 2, 2, ladder=True).level == "high"
    assert carbon_checked(medium, check, None, 2, ladder=True) == medium
    for other in ("high", "low"):
        level = Level(level=other, basis="score", text="x")
        assert carbon_checked(level, check, 2, 2, ladder=True) == level


# --- wiring -------------------------------------------------------------------------------------


def test_ladder_reads_carbon_as_demote_and_turns_the_ladder_on(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = settings_with(monkeypatch, tmp_path, CARBON_LEVELS="ladder")
    raster = build_pipeline(settings, tmp_path).extractors["raster"]
    assert isinstance(raster._inner, CarbonChecked)  # pyright: ignore[reportAttributeAccessIssue]
    assert build_answering(settings).carbon_ladder is True


@pytest.mark.parametrize("value", ["off", "demote"])
def test_off_and_demote_leave_the_ladder_off(
    value: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = settings_with(monkeypatch, tmp_path, CARBON_LEVELS=value)
    assert build_answering(settings).carbon_ladder is False


@pytest.mark.parametrize("value", ["demote", "ladder"])
def test_demote_and_ladder_share_the_ingest_cache_name(
    value: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Both store the same reading (ladder acts only when answering), so a switch reads nothing
    again (codecheck S2, .agents/qa/r9/review-296.md)."""
    settings = settings_with(monkeypatch, tmp_path, CARBON_LEVELS=value)
    names = build_ingest(settings, tmp_path / "projects", background=False)._names  # pyright: ignore[reportPrivateUsage]
    assert names["carbon_levels"] == f"demote:{READER_SHA[:12]}"


@pytest.mark.parametrize("ladder", [True, False])
def test_the_api_passes_the_ladder_to_ask(monkeypatch: pytest.MonkeyPatch, ladder: bool) -> None:
    """The app's only ladder wiring (api/ask.py asked_on); without it the live app answers as
    demote while CARBON_LEVELS=ladder (codecheck S1, .agents/qa/r9/review-296.md)."""
    seen: dict[str, Any] = {}
    monkeypatch.setattr(api_ask, "ask", lambda *a, **k: seen.update(k))  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]
    monkeypatch.setattr(api_ask, "file_of", lambda ingest, named: None)  # pyright: ignore[reportUnknownLambdaType]
    monkeypatch.setattr(api_ask, "as_uploaded", lambda ingest, info, pid: info)  # pyright: ignore[reportUnknownLambdaType]
    monkeypatch.setattr(api_ask, "confidence_of", lambda *a: None)  # pyright: ignore[reportUnknownLambdaType]
    info = SimpleNamespace(flags=(), route="raster")
    ingest = SimpleNamespace(drawing_info=lambda drawing_id: info)  # pyright: ignore[reportUnknownLambdaType]
    reviews = SimpleNamespace(get=lambda pid, did: None)  # pyright: ignore[reportUnknownLambdaType]
    answering = SimpleNamespace(
        parser=None, clock=None, prior=None, prior_families=None, sure_at=None, check=None,
        disputes=None, scorers=None, carbon_ladder=ladder,
    )  # fmt: skip
    api_ask.asked_on("q", SCAN, "d1", reviews, answering, ingest, "p1")  # type: ignore[arg-type]
    assert seen["carbon_ladder"] is ladder

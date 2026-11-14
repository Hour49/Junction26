"""CHECK_POLICY: an answer the policy doesn't certify keeps its value and asks a person to
double-check it, at the places the readers disagree (app/core/review/check.py)."""

import json
from pathlib import Path

import pytest

from app.adapters.answer_prior import NoPrior
from app.adapters.check_policy import load_check
from app.adapters.question_templates import TemplateParser
from app.core.drawing.model import (
    Conflict,
    Drawing,
    Element,
    MeasuredValue,
    Page,
    Resolution,
    Room,
    Scale,
    Subject,
    Table,
    TableRow,
)
from app.core.errors import InvalidInputError
from app.core.review.ask import Asked, ask
from app.core.review.check import CheckPolicy, Found, Place, certified
from app.core.review.model import ReviewState, Row, Settled, SignOff

SHA = "9c762d68a698dd45a6c1ca4fa7fae39f19199aae470d1b195ed82a873d8c48e9"
PAGE = Page(page=1, width=100, height=100, unit="pt")
BOX_A = (0.1, 0.1, 0.2, 0.2)
BOX_B = (0.3, 0.3, 0.4, 0.4)
BOX_C = (0.6, 0.6, 0.7, 0.7)
DOORS = (
    Element(id="e1", class_="door", page=1, box=BOX_A),
    Element(id="e2", class_="door", page=1, box=BOX_B),
)
ROOMS = (  # boxes of their own: a mark finds its model item by box
    Room(id="r1", type="bedroom", page=1, box=(0.05, 0.5, 0.25, 0.7)),
    Room(id="r2", type="bedroom", page=1, box=(0.3, 0.5, 0.5, 0.7)),
)
SCAN = Drawing(
    file="plan.png", pages=(PAGE,), scale=Scale(status="no_scale"), elements=DOORS, rooms=ROOMS
)
POLICY = CheckPolicy(thresholds={"door": 0.8, "room:bedroom": 0.8}, routes=frozenset({"bim"}))
PHOTO_FLAG = "a phone photo, read without perspective correction"


class Scored:
    """DECISIONS_CONFIDENCE's stand-in: every answer gets the same score."""

    def __init__(self, value: float | None) -> None:
        self.value, self.note = value, "decisions: stand-in"

    def probability(self, path: str, family: str, value: object) -> "Scored":
        return self


def readers_say(drawing: Drawing, row: Row) -> Found:
    """A dispute finder's stand-in: the counted e2 (or r2) nobody else sees, a place nobody
    counted that one reader sees, and a counted item that has no mark (left out)."""
    counted = "e2" if row.key == "door" else "r2"
    seen = "Counted, but 1 of the 2 other readers sees nothing here."
    missed = "Not counted, but 1 of the 2 other readers sees one here."
    return Found(places=(
        Place(item_id=counted, page=1, box=BOX_B, why=seen,
              readers={"answer": "door, score 0.41", "M one view": None, "seg": "nothing"}),
        Place(item_id=None, page=1, box=BOX_C, why=missed,
              readers={"answer": None, "M one view": "door, score 0.77", "seg": None}),
        Place(item_id="e9", page=1, box=BOX_C, why="no such mark", readers={}),
    ))  # fmt: skip


def asked(
    text: str = "How many doors are there?",
    *,
    score: float | None = 0.9,
    check: CheckPolicy | None = POLICY,
    route: str = "raster",
    flags: tuple[str, ...] = (),
    state: ReviewState | None = None,
) -> Asked:
    return ask(
        text, SCAN, parser=TemplateParser(), clock=lambda: 0.0, prior=NoPrior(),
        state=state or ReviewState(), confidence=Scored(score), flags=flags,
        raster=route == "raster", check=check, route=route, disputes=readers_say,
    )  # fmt: skip


def test_a_certified_answer_asks_for_no_check() -> None:
    found = asked(score=0.9)
    assert found.answer.answer == 2 and found.check is None


def test_an_answer_below_its_family_s_threshold_keeps_its_value_and_asks_for_a_check() -> None:
    found = asked(score=0.5)
    assert found.refusal is None and found.answer.answer == 2  # not a refusal: the value stays
    assert found.check is not None
    marks = {mark.ref: mark.id for mark in found.marks}
    counted, missed = found.check.disputed  # e9 has no mark: left out
    assert counted.mark_id == marks["e2"] and counted.mark_id != "e2"  # the review mark's id
    assert missed.mark_id is None and missed.box == BOX_C  # a place a person can add
    assert counted.readers == {
        "answer": "door, score 0.41",
        "M one view": "nothing",
        "seg": "nothing",
    }
    assert found.check.reason == (
        "Please double-check the doors: the readers disagree at 2 places, marked on the drawing."
    )


def test_rooms_point_at_their_room_marks() -> None:
    found = asked("How many bedrooms are there?", score=0.1)
    assert found.check is not None
    marks = {mark.ref: mark.id for mark in found.marks}
    assert [d.mark_id for d in found.check.disputed] == [marks["r2"], None]


@pytest.mark.parametrize(
    ("change", "why"),
    [
        ({"score": None}, "no score: nothing certifies it"),
        ({"text": "How many windows are there?"}, "a family the policy has no threshold for"),
        ({"flags": (PHOTO_FLAG,)}, "a flagged page: the policy was chosen on scans"),
        ({"route": "vector"}, "a route the policy did not certify"),
    ],
)
def test_what_the_policy_does_not_certify_asks_for_a_check(change: dict, why: str) -> None:
    assert asked(**change).check is not None, why


def test_a_certified_route_asks_for_no_check() -> None:
    assert asked(route="bim", score=None).check is None


def test_no_policy_no_refusal_or_a_signed_off_quantity_ask_for_no_check() -> None:
    assert asked(score=0.1, check=None).check is None  # CHECK_POLICY off
    refused = asked("What colour is the roof?", score=0.1)
    assert refused.refusal is not None and refused.check is None
    signed = ReviewState(signed={"door": SignOff(by="Ana", at="2026-11-14T12:00:00Z", value=2)})
    assert asked(score=0.1, state=signed).check is None  # the person's value now, not ours


def test_without_a_dispute_finder_the_request_points_nowhere() -> None:
    found = ask(
        "How many doors are there?", SCAN, parser=TemplateParser(), clock=lambda: 0.0,
        prior=NoPrior(), state=ReviewState(), confidence=Scored(0.1), raster=True,
        check=POLICY, route="raster",
    )  # fmt: skip
    assert found.check is not None and found.check.disputed == ()
    assert found.check.reason == (
        "Please double-check the doors: on drawings like this one we can't be sure enough to "
        "give it without a look."
    )


def test_certified_reads_the_threshold_at_or_above() -> None:
    at = {"route": "raster", "family": "door", "flags": ()}
    assert certified(POLICY, score=0.8, **at) and not certified(POLICY, score=0.79, **at)


def policy_file(tmp_path: Path, **change: object) -> Path:
    doc = {
        "schema": "check_policy_v1", "part": "val", "split_sha256": SHA, "lambda": 10,
        "families": {
            "toilet": {"signal": "g1main", "threshold": 0.31},
            "window": {"signal": "g1main", "threshold": None},
            "sink": {"signal": "lgate2", "threshold": 0.7},
        },
        "routes": {"bim": {"certified": True}, "vector": {"certified": False}},
    }  # fmt: skip
    doc.update(change)
    path = tmp_path / "check.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def test_the_loader_keeps_the_thresholds_on_the_answer_confidence_s_signal(tmp_path: Path) -> None:
    policy = load_check(policy_file(tmp_path), "g1main")
    assert policy == CheckPolicy(thresholds={"toilet": 0.31}, routes=frozenset({"bim"}))
    assert load_check(policy_file(tmp_path), None).thresholds == {}  # no confidence: none


@pytest.mark.parametrize(
    "change",
    [{"schema": "gate_policy_v1"}, {"part": "test"}, {"split_sha256": "x"},
     {"families": {"door": {"signal": "g1main", "threshold": "high"}}},
     {"routes": {"bim": {"certified": "yes"}}}],
)  # fmt: skip
def test_the_loader_refuses_a_file_it_can_t_trust(tmp_path: Path, change: dict) -> None:
    with pytest.raises(InvalidInputError):
        load_check(policy_file(tmp_path, **change), "g1main")


def test_an_edit_does_not_lift_the_request() -> None:
    """A person's edit changes the value but is not a sign-off: the request stays until then."""
    edited = ReviewState(rejected={"door": ("m2",)})
    found = asked(score=0.1, state=edited)
    assert found.check is not None


def test_a_value_read_from_a_schedule_asks_for_a_check_unless_schedules_are_certified() -> None:
    rows = tuple(TableRow(cells=(f"10{at}",), box=(0.1, 0.1 * at, 0.3, 0.1 * at + 0.05))
                 for at in range(1, 4))  # fmt: skip
    table = Table(id="t1", page=1, box=(0.1, 0.1, 0.3, 0.5), title="Door Schedule",
                  columns=("Door Number",), rows=rows)  # fmt: skip
    sheet = SCAN.model_copy(update={"tables": (table,), "file": "x.pdf"})

    def check_of(policy: CheckPolicy) -> object:
        found = ask(
            "How many doors are listed in the door schedule?", sheet, parser=TemplateParser(),
            clock=lambda: 0.0, prior=NoPrior(), state=ReviewState(), check=policy, route="vector",
        )  # fmt: skip
        assert found.answer.method == "schedule" and found.answer.answer == 3
        return found.check

    request = check_of(POLICY)
    assert request is not None and request.disputed == ()  # type: ignore[union-attr]
    assert check_of(POLICY.model_copy(update={"routes": frozenset({"schedule"})})) is None


def test_at_most_five_places_are_listed() -> None:
    many = [
        Place(item_id=None, page=1, box=(0.01 * n, 0.5, 0.01 * n + 0.01, 0.51), why="w", readers={})
        for n in range(8)
    ]
    found = ask(
        "How many doors are there?", SCAN, parser=TemplateParser(), clock=lambda: 0.0,
        prior=NoPrior(), state=ReviewState(), confidence=Scored(0.1), raster=True,
        check=POLICY, route="raster", disputes=lambda drawing, row: Found(places=tuple(many)),
    )  # fmt: skip
    assert found.check is not None and len(found.check.disputed) == 5
    assert found.check.disputed[0].box == many[0].box


def disagreeing(resolution: Resolution | None = None) -> Drawing:
    """SCAN where a second method counts 3 doors against the detector's 2."""
    conflict = Conflict(
        id="c1", quantity="element_count", subject=Subject(kind="class", ref="door"),
        status="conflict", tolerance=0.0, resolution=resolution,
        values=(MeasuredValue(value=2, unit="count", method="detector"),
                MeasuredValue(value=3, unit="count", method="parser")),
    )  # fmt: skip
    return SCAN.model_copy(update={"conflicts": (conflict,)})


def asked_on(drawing: Drawing, *, route: str, state: ReviewState | None = None) -> Asked:
    return ask(
        "How many doors are there?", drawing, parser=TemplateParser(), clock=lambda: 0.0,
        prior=NoPrior(), state=state or ReviewState(), confidence=Scored(0.95),
        raster=route == "raster", check=POLICY, route=route, disputes=readers_say,
    )  # fmt: skip


@pytest.mark.parametrize("route", ["raster", "bim"])
@pytest.mark.parametrize("rule", [None, Resolution(rule="second_count", value=3)])
def test_a_disagreement_is_never_certified_and_the_request_names_it(
    route: str, rule: Resolution | None
) -> None:
    """Review of #129 B1: a high score on a certified route does not hide two methods that
    disagree, whether a rule picked one or nobody did."""
    found = asked_on(disagreeing(rule), route=route)
    assert found.row is not None and found.row.conflict is not None
    assert found.check is not None
    shown = found.row.value
    assert found.check.reason == (
        f"Please double-check the doors: two methods disagree: 2 vs 3; we show {shown}."
    )


def test_a_settled_disagreement_asks_for_no_check() -> None:
    """The person's settle is the one thing that lifts it: the value is theirs."""
    settled = ReviewState(settled={"door": Settled(value=3, at="2026-11-14T12:00:00Z")})
    assert asked_on(disagreeing(), route="raster", state=settled).check is None


def test_an_estimate_is_never_certified() -> None:
    found = asked(score=0.95, flags=(PHOTO_FLAG,))
    assert found.check is not None and "it is an estimate (read from a page flagged" in (
        found.check.reason
    )


def test_an_edited_value_is_not_certified_on_the_pipeline_s_score() -> None:
    """The score rated the pipeline's 2 doors, not the person's 1: sign off to confirm."""
    edited = ReviewState(rejected={"door": ("m1",)})
    found = asked(score=0.95, state=edited)
    assert found.row is not None and found.row.value == 1
    assert found.check is not None
    assert found.check.reason == "Please double-check the door: edited by you: sign off to confirm."


def test_a_mark_the_person_rejected_is_never_pointed_at() -> None:
    rejected = ReviewState(rejected={"door": ("m2",)})
    found = asked(score=0.1, state=rejected)
    assert found.check is not None
    assert [d.mark_id for d in found.check.disputed] == [None]  # e2's m2 is gone, the miss stays

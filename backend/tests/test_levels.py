"""The confidence level (decision 0011): High, Medium or Low on every answer the check policy
rates, with one measured meaning each, and never against the double-check request
(app/core/review/check.py `level_of`, app/adapters/check_policy.py)."""

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
    Plan,
    Room,
    Scale,
    Subject,
    Table,
    TableRow,
)
from app.core.errors import InvalidInputError
from app.core.review.ask import Asked, ask
from app.core.review.check import CheckPolicy, Counts, Level, LevelName, level_of, lowest
from app.core.review.model import ReviewState, Settled, SignOff

SHA = "9c762d68a698dd45a6c1ca4fa7fae39f19199aae470d1b195ed82a873d8c48e9"
PAGE = Page(page=1, width=100, height=100, unit="pt")
DOORS = (
    Element(id="e1", class_="door", page=1, box=(0.1, 0.1, 0.2, 0.2)),
    Element(id="e2", class_="door", page=1, box=(0.3, 0.3, 0.4, 0.4)),
)
ROOMS = (Room(id="r1", type="bedroom", page=1, box=(0.05, 0.5, 0.25, 0.7), label="MH"),)
SCAN = Drawing(
    file="plan.png", pages=(PAGE,), scale=Scale(status="no_scale"), elements=DOORS, rooms=ROOMS
)
COUNTS: dict[LevelName, Counts] = {
    "high": Counts(units=1517, exact=1501),
    "medium": Counts(units=1185, exact=1084),
    "low": Counts(units=680, exact=397),
}
# doors: certified at 0.8, Medium from 0.4; bedrooms: certified at 0.8, no Medium (as windows)
POLICY = CheckPolicy(
    thresholds={"door": 0.8, "room:bedroom": 0.8},
    routes=frozenset({"bim"}),
    medium={"door": 0.4},
    route_levels={"bim": "high", "schedule": "medium", "vector": "low"},
    route_counts={"bim": Counts(units=372, exact=372), "schedule": Counts(units=39, exact=37)},
    counts=COUNTS,
)
PHOTO_FLAG = "a phone photo, read without perspective correction"
SIGNED = SignOff(by="Ana", at="2026-11-14T12:00:00Z", value=2)


class Scored:
    def __init__(self, value: float | None) -> None:
        self.value, self.note, self.agrees = value, "decisions: stand-in", None

    def probability(self, path: str, family: str, value: object) -> "Scored":
        return self


def asked(
    text: str = "How many doors are there?",
    *,
    score: float | None = 0.9,
    check: CheckPolicy | None = POLICY,
    route: str = "raster",
    flags: tuple[str, ...] = (),
    state: ReviewState | None = None,
    drawing: Drawing = SCAN,
) -> Asked:
    return ask(
        text, drawing, parser=TemplateParser(), clock=lambda: 0.0, prior=NoPrior(),
        state=state or ReviewState(), confidence=Scored(score), flags=flags,
        raster=route == "raster", check=check, route=route,
    )  # fmt: skip


def made(found: Asked) -> tuple[str, str] | None:
    return None if found.level is None else (found.level.level, found.level.basis)


def test_a_certified_answer_is_high_and_one_that_asks_is_medium_or_low_by_its_score() -> None:
    assert made(asked(score=0.9)) == ("high", "certified")
    assert made(asked(score=0.8)) == ("high", "certified")  # at the threshold
    assert made(asked(score=0.79)) == ("medium", "score")
    assert made(asked(score=0.4)) == ("medium", "score")  # at the Medium threshold
    assert made(asked(score=0.39)) == ("low", "score")


@pytest.mark.parametrize("score", [None, 0.0, 0.2, 0.39, 0.4, 0.6, 0.79, 0.8, 0.95, 1.0])
@pytest.mark.parametrize("text", ["How many doors are there?", "How many bedrooms are there?"])
@pytest.mark.parametrize("route", ["raster", "bim", "vector"])
@pytest.mark.parametrize("flags", [(), (PHOTO_FLAG,)])
def test_a_level_never_contradicts_the_request(
    score: float | None, text: str, route: str, flags: tuple[str, ...]
) -> None:
    """High exactly when the answer is sure and nothing is asked; Medium and Low always ask."""
    found = asked(text, score=score, route=route, flags=flags)
    assert found.level is not None
    assert (found.level.level == "high") == (found.answer.sure is True) == (found.check is None)


@pytest.mark.parametrize(
    ("change", "level"),
    [
        ({"flags": (PHOTO_FLAG,), "score": 0.95}, ("low", "page")),  # not measured on photos
        ({"text": "How many windows are there?"}, ("low", "unrated")),  # no threshold: not rated
        ({"score": None}, ("low", "unrated")),  # a rated family, no score on this drawing
        ({"text": "How many bedrooms are there?", "score": 0.7}, ("low", "score")),  # no Medium
        ({"route": "bim", "score": None}, ("high", "route")),  # a certified route
        ({"route": "vector", "score": None}, ("low", "route")),  # measured, not good enough
        ({"route": "sketch", "score": None}, ("low", "unrated")),  # a route never measured
    ],
)
def test_what_an_answer_s_level_rests_on(change: dict, level: tuple[str, str]) -> None:
    assert made(asked(**change)) == level


def test_an_answer_held_for_a_check_is_low_whatever_its_score() -> None:
    conflict = Conflict(
        id="c1", quantity="element_count", subject=Subject(kind="class", ref="door"),
        status="conflict", tolerance=0.0, resolution=None,
        values=(MeasuredValue(value=2, unit="count", method="detector"),
                MeasuredValue(value=3, unit="count", method="parser")),
    )  # fmt: skip
    disagreeing = SCAN.model_copy(update={"conflicts": (conflict,)})
    assert made(asked(score=0.95, drawing=disagreeing)) == ("low", "held")
    assert made(asked(score=0.95, drawing=disagreeing, route="bim")) == ("low", "held")
    edited = ReviewState(rejected={"door": ("m1",)})  # the score rated our 2 doors, not their 1
    assert made(asked(score=0.95, state=edited)) == ("low", "held")
    # a bedroom typed from what is drawn in it, no printed label: it keeps its score and is still
    # Low, as the policy's own counts put it (eval's `always_flag`), not Medium by that score
    bedrooms = POLICY.model_copy(update={"medium": {"room:bedroom": 0.4}})
    question = "How many bedrooms are there?"
    assert made(asked(question, score=0.7, check=bedrooms)) == ("medium", "score")  # labelled
    unlabelled = SCAN.model_copy(update={"rooms": (ROOMS[0].model_copy(update={"label": None}),)})
    assert made(asked(question, score=0.7, check=bedrooms, drawing=unlabelled)) == ("low", "held")


def test_nothing_is_certified_on_a_raster_drawing_where_the_detector_found_nothing() -> None:
    """Archive sheet 61261280 (AR, 2026-11-14): no plan and no element found, so every reader
    said 0 toilets, the gate scored that agreement high and the 0 was Sure; two bowls are drawn.
    An element counted with no position of its own (the arbiter's) does not make the page read."""
    unlocated = Element(id="e1", class_="shower", page=1, box=(0.0, 0.0, 1.0, 1.0),
                        attrs={"located": False, "source": "arbiter-t1"})  # fmt: skip
    blank = SCAN.model_copy(update={"elements": (unlocated,)})
    found = asked(score=0.95, drawing=blank)
    assert found.answer.answer == 0 and found.answer.sure is False and found.check is not None
    assert found.level is not None and (found.level.level, found.level.basis) == ("low", "page")
    assert found.level.text.startswith("Low confidence: nothing was found on this page")
    # it does not change a route that read the sheet itself, or a page that was read
    assert made(asked(score=None, drawing=blank, route="bim")) == ("high", "route")
    assert made(asked(score=0.95)) == ("high", "certified")  # located doors
    plan = Plan(id="p1", page=1, box=(0.0, 0.0, 1.0, 1.0))
    planned = blank.model_copy(update={"plans": (plan,)})
    assert made(asked(score=0.95, drawing=planned)) == ("high", "certified")


def test_a_value_a_person_signed_or_settled_a_refusal_and_no_policy_have_no_level() -> None:
    assert asked(score=0.5, state=ReviewState(signed={"door": SIGNED})).level is None
    assert asked(score=0.95, state=ReviewState(signed={"door": SIGNED})).level is None
    settled = ReviewState(settled={"door": Settled(value=3, at="2026-11-14T12:00:00Z")})
    assert asked(score=0.5, state=settled).level is None
    refused = asked("What colour is the roof?")
    assert refused.refusal is not None and refused.level is None
    assert asked(check=None).level is None  # CHECK_POLICY off


def test_a_policy_file_without_levels_gives_no_level() -> None:
    """An older check policy still certifies and asks; it says nothing about levels, so no
    answer is called Low for the lack of them."""
    old = CheckPolicy(thresholds={"door": 0.8}, routes=frozenset({"bim"}))
    assert asked(score=0.9, check=old).level is None and asked(score=0.9, check=old).check is None
    assert asked(score=0.5, check=old).level is None
    assert asked(score=0.5, check=old).check is not None


def test_a_schedule_value_takes_the_schedule_route_s_level() -> None:
    rows = tuple(TableRow(cells=(f"10{at}",), box=(0.1, 0.1 * at, 0.3, 0.1 * at + 0.05))
                 for at in range(1, 4))  # fmt: skip
    table = Table(id="t1", page=1, box=(0.1, 0.1, 0.3, 0.5), title="Door Schedule",
                  columns=("Door Number",), rows=rows)  # fmt: skip
    sheet = SCAN.model_copy(update={"tables": (table,), "file": "x.pdf"})

    def level(policy: CheckPolicy) -> tuple[str, str] | None:
        found = asked("How many doors are listed in the door schedule?", check=policy,
                      route="vector", drawing=sheet)  # fmt: skip
        assert found.answer.method == "schedule"
        return made(found)

    assert level(POLICY) == ("medium", "route")
    assert level(POLICY.model_copy(update={"route_levels": {}})) == ("low", "unrated")
    certified = {"routes": frozenset({"schedule"}), "route_levels": {"schedule": "high"}}
    assert level(POLICY.model_copy(update=certified)) == ("high", "route")


def test_the_words_quote_the_counts_the_level_was_measured_on() -> None:
    at = {"route": "raster", "family": "door", "flags": ()}
    high = level_of(POLICY, sure=True, score=0.9, **at)
    medium = level_of(POLICY, sure=False, score=0.5, **at)
    low = level_of(POLICY, sure=False, score=0.1, **at)
    assert high == Level(
        level="high", basis="certified",
        text="High confidence: on our validation plans, 99% of the answers rated this way were "
        "exact (1501 of 1517).",
    )  # fmt: skip
    assert medium is not None and medium.text == (
        "Medium confidence: on our validation plans, 91% of the answers rated this way were "
        "exact (1084 of 1185). Please double-check it."
    )
    assert low is not None and low.text == (
        "Low confidence: on our validation plans, 58% of the answers rated this way were exact "
        "(397 of 680). Check it before you use it."
    )
    on_route = level_of(POLICY, sure=True, route="bim", family="door", score=None, flags=())
    assert on_route is not None and on_route.text == (
        "High confidence: on our reference drawings of this kind, 372 of 372 answers were exact."
    )
    photo = level_of(POLICY, sure=False, score=0.9, **{**at, "flags": (PHOTO_FLAG,)})
    assert photo is not None and "not measured" in photo.text


def test_the_lowest_level_of_several() -> None:
    assert lowest(["high", "medium", "high"]) == "medium"
    assert lowest(["medium", "low"]) == "low" and lowest(["high"]) == "high"
    assert lowest([]) is None


def policy_file(tmp_path: Path, **change: object) -> Path:
    doc = {
        "schema": "check_policy_v1", "part": "val", "split_sha256": SHA,
        "families": {
            "toilet": {"signal": "g1main", "threshold": 0.31, "medium": 0.12},
            "window": {"signal": "g1main", "threshold": 0.99, "medium": None},
            "door": {"signal": "lgate2-rt", "threshold": 0.9, "medium": 0.8},  # gate not configured
            "sink": {"signal": "g1main", "threshold": None, "medium": 0.2},  # never certified
        },
        "routes": {
            "bim": {"certified": True, "level": "high", "dev": {"units": 372, "exact": 372}},
            "schedule": {"certified": False, "level": "medium", "dev": {"units": 39, "exact": 37}},
            "vector": {"certified": False},
        },
        "levels": {
            "cut": 0.2, "min_units": 30, "min_exact": 0.8,
            "crossfit": {"high": {"units": 1517, "exact": 1501},
                         "medium": {"units": 1185, "exact": 1084},
                         "low": {"units": 680, "exact": 397}},
        },
    }  # fmt: skip
    doc.update(change)
    path = tmp_path / "check.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def test_the_loader_reads_the_levels(tmp_path: Path) -> None:
    policy = load_check(policy_file(tmp_path), "g1main")
    assert policy.thresholds == {"toilet": 0.31, "window": 0.99}
    assert policy.medium == {"toilet": 0.12}  # only where the threshold itself is kept
    assert policy.route_levels == {"bim": "high", "schedule": "medium"}
    assert policy.route_counts == {
        "bim": Counts(units=372, exact=372), "schedule": Counts(units=39, exact=37),
    }  # fmt: skip
    assert policy.counts == COUNTS


def test_a_file_without_the_levels_loads_as_before(tmp_path: Path) -> None:
    families = {"toilet": {"signal": "g1main", "threshold": 0.31}}
    routes = {"bim": {"certified": True}}
    policy = load_check(
        policy_file(tmp_path, families=families, routes=routes, levels=None), "g1main"
    )
    assert policy == CheckPolicy(thresholds={"toilet": 0.31}, routes=frozenset({"bim"}))
    assert policy.counts is None


@pytest.mark.parametrize(
    "change",
    [
        {"families": {"toilet": {"signal": "g1main", "threshold": 0.31, "medium": 0.5}}},  # above
        {"families": {"toilet": {"signal": "g1main", "threshold": 0.31, "medium": "low"}}},
        {"routes": {"bim": {"certified": True, "level": "sure"}}},
        {"routes": {"bim": {"certified": False, "level": "high"}}},  # High must be certified
        {"routes": {"bim": {"certified": True, "level": "medium"}}},  # and certified is High
        {"routes": {"bim": {"certified": True, "dev": {"units": 3, "exact": 4}}}},
        {"levels": {"crossfit": {"high": {"units": 2, "exact": 2}}}},  # a level is missing
        {"levels": {"cut": 0.2}},
    ],
)
def test_the_loader_refuses_levels_it_can_t_trust(tmp_path: Path, change: dict) -> None:
    with pytest.raises(InvalidInputError):
        load_check(policy_file(tmp_path, **change), "g1main")


def test_the_committed_levels_policy_of_c1_t1_loads_with_its_levels() -> None:
    """eval's `check-policy --medium 0.20` file, as committed: the loader reads every field it
    writes, so the demo's answers get a level from it."""
    path = Path(__file__).resolve().parents[2] / (
        "eval/results/check/check-C1-T1-recall96-rt-full-small-medium20.json"
    )
    policy = load_check(path, "g1main", ["lgate2-rt", "lgate-rt-nol1"])
    assert len(policy.thresholds) == 12
    assert set(policy.thresholds) - set(policy.medium) == {"window"}  # too few Medium on val
    assert all(policy.medium[family] <= policy.thresholds[family] for family in policy.medium)
    assert policy.route_levels == {"bim": "high", "vector": "high", "schedule": "medium"}
    assert set(policy.route_counts) == {"bim", "vector", "schedule"}
    assert policy.counts is not None and all(c.units >= 30 for c in policy.counts.values())

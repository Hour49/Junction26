"""D455's double-check policy (stoa_eval/check.py): per family the threshold maximising certified -
lambda x wrong, the pooled floor, the cross-fit, the route verdicts."""

from stoa_eval.check import (
    CheckPolicyFile,
    Point,
    best_threshold,
    crossfit,
    fit,
    route_verdict,
)
from stoa_eval.gate import Unit


def units(family: str, *scored: tuple[float | None, bool], prefix: str = "a") -> list[Unit]:
    return [
        Unit(file=f"{prefix}{n}", family=family, exact=exact, signals={"s": value})
        for n, (value, exact) in enumerate(scored)
    ]


def test_the_threshold_maximises_certified_minus_lambda_times_wrong() -> None:
    # sorted by score: 9 right, then 1 wrong, then 9 right, then 3 wrong
    scored = [(0.99 - 0.01 * n, True) for n in range(9)] + [(0.89, False)]
    scored += [(0.88 - 0.01 * n, True) for n in range(9)] + [(0.1, False)] * 3
    family = units("door", *scored)
    # lambda 10: 9 right alone = 9; down to 0.80 = 18 - 10 = 8: stop at the first nine
    assert best_threshold(family, "s", 10) == 0.91
    # lambda 5: 18 - 5 = 13 > 9: take both runs of right answers
    assert best_threshold(family, "s", 5) == 0.8


def test_nothing_certified_when_no_threshold_pays_and_none_is_never_certified() -> None:
    family = units("window", (0.9, False), (0.8, True), (None, True))
    assert best_threshold(family, "s", 10) is None


def test_the_pooled_floor_closes_the_least_exact_family() -> None:
    good = units("toilet", *[(0.9, True)] * 19, (0.9, False))  # 95% exact
    poor = units("door", *[(0.9, True)] * 9, (0.9, False), prefix="b")  # 90%: pays at lambda 5
    by_family = {"toilet": good, "door": poor}
    signals = {"toilet": ("s", None), "door": ("s", None)}
    assert fit(by_family, signals, 5, 0.0) == {"toilet": 0.9, "door": 0.9}
    # pooled 28/30 = 93.3% < 95%: door (90%) closes, toilet (95%) stays
    assert fit(by_family, signals, 5, 0.95) == {"toilet": 0.9, "door": None}


def test_a_fixed_cut_is_kept_as_given() -> None:
    family = units("window", (0.9, True), (0.7, False))
    assert fit({"window": family}, {"window": ("s", 0.75)}, 10, 0.95) == {"window": 0.75}


def test_the_cross_fit_picks_on_one_half_and_scores_the_other() -> None:
    first = units("door", (0.9, True), (0.8, True), (0.7, False), prefix="a")
    second = units("door", (0.9, True), (0.8, False), (0.7, False), prefix="b")
    held = crossfit(
        {"door": first + second}, {"door": ("s", None)}, 10, 0.0, lambda f: f.startswith("a")
    )
    # picked on a: 0.8, scores b: 2 certified, 1 exact; picked on b: 0.9, scores a: 1, 1
    assert held == {"door": Point(units=6, certified=3, exact=2)}


def test_a_route_is_certified_whole_when_it_reaches_the_floor() -> None:
    assert route_verdict([True] * 282, 10, 0.95).certified
    almost = route_verdict([True] * 18 + [False] * 2, 10, 0.95)  # 90%
    assert not almost.certified and almost.holdout == Point(units=20, certified=20, exact=18)
    assert not route_verdict([], 10, 0.95).certified


def test_the_file_writes_lambda_under_its_name() -> None:
    made = CheckPolicyFile(
        generated="2026-11-14T12:00:00+02:00", split_sha256="0" * 64, arm="x", lambda_=10,
        floor=0.95, families={}, routes={}, pooled_val=Point(units=0, certified=0, exact=0),
        pooled_crossfit=Point(units=0, certified=0, exact=0),
    )  # fmt: skip
    dumped = made.model_dump(by_alias=True)
    assert dumped["lambda"] == 10 and dumped["schema"] == "check_policy_v1"
    assert CheckPolicyFile.model_validate(dumped) == made

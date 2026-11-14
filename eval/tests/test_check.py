"""The double-check policy (stoa_eval/check.py): D455's per family threshold maximising certified -
lambda x wrong, the pooled floor, the cross-fit, the route verdicts; D476's P(wrong) calibration
and the one cut that flags a share of the wrong answers."""

import math

from stoa_eval.check import (
    NONE,
    Calibration,
    CheckPolicyFile,
    Point,
    best_threshold,
    calibrate,
    calibrations,
    crossfit,
    fit,
    flag_always,
    point,
    probabilities,
    recall_cut,
    recall_fit,
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
    assert held == {"door": Point(units=6, certified=3, exact=2, wrong=3, no_value=0)}


def test_a_route_is_certified_whole_when_it_reaches_the_floor() -> None:
    assert route_verdict([True] * 282, 10, 0.95).certified
    almost = route_verdict([True] * 18 + [False] * 2, 10, 0.95)  # 90%
    assert not almost.certified
    assert almost.holdout == Point(units=20, certified=20, exact=18, wrong=2, no_value=0)
    assert not route_verdict([], 10, 0.95).certified


def test_the_file_writes_lambda_under_its_name() -> None:
    made = CheckPolicyFile(
        generated="2026-11-14T12:00:00+02:00", split_sha256="0" * 64, arm="x", lambda_=10,
        floor=0.95, families={}, routes={}, pooled_val=NONE, pooled_crossfit=NONE,
    )  # fmt: skip
    dumped = made.model_dump(by_alias=True)
    assert dumped["lambda"] == 10 and dumped["schema"] == "check_policy_v1"
    assert CheckPolicyFile.model_validate(dumped) == made


def test_the_calibration_gives_low_values_a_high_p_wrong_and_inverts_at_a_cut() -> None:
    scored = [(x / 10, x < 3) for x in range(10)] + [(0.25, False), (0.35, True)]
    model = calibrate(scored)
    assert model is not None and model.b < 0
    assert model.p_wrong(0.0) > 0.5 > model.p_wrong(0.9)
    threshold = model.threshold(0.2)
    assert threshold is not None and math.isclose(model.p_wrong(threshold), 0.2)
    assert calibrate([]) is None


def test_a_signal_that_rises_with_errors_never_certifies() -> None:
    model = Calibration(a=0.0, b=0.5, mu=0.0, sd=1.0)
    assert model.threshold(0.5) is None
    assert Calibration(a=0.0, b=-1.0, mu=0.0, sd=1.0).threshold(0.0) is None


def test_the_cut_flags_the_likeliest_wrong_until_the_share_is_reached() -> None:
    scored = [(0.9, True), (0.8, False), (0.7, True), (0.7, False), (0.2, True), (0.1, False)]
    assert math.isclose(recall_cut(scored, 1), (0.9 + 0.8) / 2)
    # the second wrong one ties with a right one at 0.7: both are flagged
    assert math.isclose(recall_cut(scored, 2), (0.7 + 0.2) / 2)
    assert recall_cut(scored, 4) == 0.0  # only 3 wrong: flag all
    assert math.isclose(recall_cut(scored, 0), (1.0 + 0.9) / 2)  # flag none


def test_the_recall_fit_counts_fixed_cuts_and_missing_values_before_choosing_the_cut() -> None:
    def half(prefix: str) -> list[Unit]:
        scored = [(0.9, True)] * 6 + [(0.2, False), (0.3, False), (0.8, True), (0.1, False)]
        return units("door", *scored, prefix=prefix)

    doors = half("a") + half("b")
    # a window under its fixed cut and a sink with no value: two wrong ones already flagged
    windows = units("window", (0.5, False), (0.9, True), prefix="w")
    sinks = units("sink", (None, False), prefix="s")
    by_family = {"door": doors, "window": windows, "sink": sinks}
    signals = {"door": ("s", None), "window": ("s", 0.75), "sink": ("s", None)}

    def first(file: str) -> bool:
        return file.startswith(("a", "w", "s"))

    # 8 wrong: the window and the sink flagged already, 6 door errors (0.1, 0.2, 0.3 in each half)
    # 0.8 needs 7 of 8: 5 of the doors', and the ties at 0.3 take the sixth
    cut, held = recall_fit(by_family, signals, 0.8, first)
    assert held["window"] == Point(units=2, certified=1, exact=1, wrong=1, no_value=0)
    assert held["sink"] == Point(units=1, certified=0, exact=0, wrong=1, no_value=1)
    assert held["door"] == Point(units=20, certified=14, exact=14, wrong=6, no_value=0)
    # 0.5 needs 4 of 8: the two at 0.1 are enough, the four at 0.2 and 0.3 stay certified
    cut_half, held_half = recall_fit(by_family, signals, 0.5, first)
    assert cut_half > cut
    assert held_half["door"] == Point(units=20, certified=18, exact=14, wrong=6, no_value=0)


def test_a_probability_is_calibrated_on_its_logit_and_its_threshold_is_a_probability() -> None:
    # right answers sit near 1, wrong ones spread low: the logit separates the tail
    scored = [(0.999, False)] * 20 + [(0.99, False)] * 20 + [(0.9, True), (0.5, True), (0.6, False)]
    model = calibrate(scored, logit=True)
    assert model is not None and model.logit and model.b < 0
    threshold = model.threshold(0.05)
    assert threshold is not None and 0 < threshold < 1
    assert math.isclose(model.p_wrong(threshold), 0.05, rel_tol=1e-6)
    # without the logit the same pairs put far more weight on the tail's few values
    raw = calibrate(scored)
    assert raw is not None and not raw.logit


def test_only_a_signal_whose_values_all_lie_in_0_1_is_a_probability() -> None:
    by_family = {
        "door": units("door", (0.2, True), (None, False)),
        "room:wc": [Unit(file="w", family="room:wc", exact=True, signals={"t": -0.5})],
    }
    signals = {"door": ("s", None), "room:wc": ("t", None)}
    assert probabilities(by_family, signals) == {"s"}
    made = calibrations(by_family, signals, probabilities(by_family, signals))
    assert made["door"] is not None and made["door"].logit
    assert made["room:wc"] is not None and not made["room:wc"].logit


def test_an_always_flagged_unit_loses_its_signals_and_is_never_certified() -> None:
    doors = units("door", (0.9, True), (0.9, False))
    kept, flagged = flag_always(doors, {("a1", "door")})
    assert kept == doors[0] and flagged.signals == {"s": None} and not flagged.exact
    assert point([kept, flagged], "s", 0.5) == Point(
        units=2, certified=1, exact=1, wrong=1, no_value=1
    )

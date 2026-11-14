"""The double-check policy (check_policy_v1, the backend's CHECK_POLICY): which answers are
certified as they are; every other one keeps its value and asks a person to double-check it.

Rule D455 (orchestrator for Bogdan, 2026-11-14 11:3x, fixed before any test read): per family, the
threshold on its signal that maximises (answers certified) - lambda x (wrong ones among them),
lambda 10: a wrong answer shown as certain costs ten double-checks. Chosen on all of val (the
shipped thresholds) and cross-fit on the gate halves (pick on one, score on the other: the honest
val estimate). Pooled floor: while the certified answers are under `floor` exact, the family with
the lowest exact share among its certified answers is closed. A unit is one (image, family) answer
(the questions that share it); a refused answer is never certified.

Rule D476 (orchestrator for Bogdan, 2026-11-14 ~12:0x, replaces D455 as the shipping rule): ask
for a check on at least `recall` of the wrong answers, as few right ones as that allows. Per family
the signal is calibrated to P(wrong) by a logistic regression on val, cross-fit on the gate halves;
ONE cut on P(wrong) over all families is chosen on those out-of-fold values so that the flagged
answers hold at least `recall` of val's wrong ones (the likeliest wrong first, whatever the
family). The shipped thresholds are the all-val calibrations at that cut, one value per family. A
fixed cut is kept as given and what it flags counts toward the recall. A signal that is a
probability (every value in [0, 1]) is calibrated on its logit: the tails, where a cut near a few
percent P(wrong) falls, fit far better (C1 val: 46.0% of answers flagged instead of 51.4% at the
same recall; D17).

Routes the raster gate does not see (vector, IFC model, schedules) are certified whole or not from
golden v2's holdout answers: certified when they reach the floor and the same utility is positive.
"""

import math
from collections.abc import Callable, Mapping, Sequence, Set

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from .gate import Unit, cp_lower

SCHEMA = "check_policy_v1"
LAMBDA = 10.0
FLOOR = 0.95
RULE = (
    "D455: per family, the threshold maximising certified - lambda x wrong on val; pooled floor "
    "on the certified share exact"
)
RECALL = 0.96
RECALL_RULE = (
    "D476: per family, the signal calibrated to P(wrong) (logistic, cross-fit on val); one "
    "P(wrong) cut over all families so the flagged answers hold >= recall of val's wrong ones"
)
RIDGE = 0.01  # keeps a half with only right answers finite
EPS = 1e-6  # a probability's logit is taken on [EPS, 1 - EPS]


class Point(BaseModel):
    model_config = ConfigDict(extra="forbid")

    units: int
    certified: int
    exact: int
    wrong: int = Field(description="wrong answers among all the units, certified or not")
    no_value: int = Field(description="units without a value of the signal: never certified")


class Calibration(BaseModel):
    """P(wrong | value) = 1 / (1 + exp(-(a + b (x - mu) / sd))), x the value, or its logit for a
    signal that is a probability."""

    model_config = ConfigDict(extra="forbid")

    a: float
    b: float
    mu: float
    sd: float
    logit: bool = False

    def p_wrong(self, value: float) -> float:
        x = _logit(value) if self.logit else value
        return _sigmoid(self.a + self.b * (x - self.mu) / self.sd)

    def threshold(self, cut: float) -> float | None:
        """The value from which P(wrong) is under `cut`, so the answer is certified; None (never
        certified) when P(wrong) does not fall as the value rises, or no cut is left."""
        if self.b >= 0 or cut <= 0:
            return None
        x = self.mu + self.sd * (_logit(min(cut, 1 - 1e-12)) - self.a) / self.b
        return _sigmoid(x) if self.logit else x


def _sigmoid(z: float) -> float:
    return 1 / (1 + math.exp(-z)) if z >= 0 else math.exp(z) / (1 + math.exp(z))


def _logit(p: float) -> float:
    p = min(max(p, EPS), 1 - EPS)
    return math.log(p / (1 - p))


class CheckFamily(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal: str
    threshold: float | None = Field(description="lowest certified value; null: never certified")
    fixed: bool = Field(description="a cut given, not fitted by the rule")
    val: Point = Field(description="all of val, in-sample")
    crossfit: Point = Field(description="val, picked on one gate half, scored on the other")
    calibration: Calibration | None = Field(
        default=None, description="D476: the all-val P(wrong) the threshold is read from"
    )


class RouteVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    certified: bool
    holdout: Point = Field(description="golden v2 holdout questions answered on the route")
    lower_bound: float | None = Field(description="95% Clopper-Pearson bound on the exact share")


class CheckPolicyFile(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_: str = Field(alias="schema", default=SCHEMA)
    generated: str
    part: str = "val"
    split_sha256: str
    arm: str
    rule: str = RULE
    lambda_: float = Field(
        serialization_alias="lambda", validation_alias=AliasChoices("lambda", "lambda_")
    )
    floor: float
    recall: float | None = Field(default=None, description="D476's target; null: D455's rule")
    always_flag: list[str] = Field(
        default_factory=list, description="rules whose units are flagged whatever their signal"
    )
    cut: float | None = Field(default=None, description="D476: flagged from this P(wrong) on")
    families: dict[str, CheckFamily]
    routes: dict[str, RouteVerdict]
    pooled_val: Point
    pooled_crossfit: Point
    test: dict[str, object] | None = None


def _value(unit: Unit, signal: str) -> float | None:
    value = unit.signals.get(signal)
    return None if value is None else float(value)


def certified_units(units: Sequence[Unit], signal: str, threshold: float | None) -> list[Unit]:
    if threshold is None:
        return []
    return [u for u in units if (v := _value(u, signal)) is not None and v >= threshold]


def point(units: Sequence[Unit], signal: str, threshold: float | None) -> Point:
    sure = certified_units(units, signal, threshold)
    return Point(
        units=len(units),
        certified=len(sure),
        exact=sum(u.exact for u in sure),
        wrong=sum(not u.exact for u in units),
        no_value=sum(_value(u, signal) is None for u in units),
    )


def _added(a: Point, b: Point) -> Point:
    return Point(**{name: getattr(a, name) + getattr(b, name) for name in Point.model_fields})


NONE = Point(units=0, certified=0, exact=0, wrong=0, no_value=0)


def utility(p: Point, lam: float) -> float:
    return p.certified - lam * (p.certified - p.exact)


def best_threshold(units: Sequence[Unit], signal: str, lam: float) -> float | None:
    """The threshold with the highest utility; None (certify nothing, utility 0) unless one is
    above 0. Ties go to the higher threshold (fewer answers for the same utility)."""
    values = sorted({v for u in units if (v := _value(u, signal)) is not None}, reverse=True)
    best, best_utility = None, 0.0
    for threshold in values:
        gain = utility(point(units, signal, threshold), lam)
        if gain > best_utility:
            best, best_utility = threshold, gain
    return best


# family -> (signal, a fixed cut or None to fit one)
Signals = Mapping[str, tuple[str, float | None]]


def fit(
    by_family: Mapping[str, Sequence[Unit]], signals: Signals, lam: float, floor: float
) -> dict[str, float | None]:
    """Each family's threshold by the rule, then the pooled floor."""
    chosen: dict[str, float | None] = {}
    for family, units in by_family.items():
        signal, cut = signals[family]
        chosen[family] = cut if cut is not None else best_threshold(units, signal, lam)
    while True:
        points = {f: point(us, signals[f][0], chosen[f]) for f, us in by_family.items()}
        sure = sum(p.certified for p in points.values())
        if sure == 0 or sum(p.exact for p in points.values()) / sure >= floor:
            return chosen
        open_ = [f for f, p in points.items() if p.certified]
        worst = min(sorted(open_), key=lambda f: points[f].exact / points[f].certified)
        chosen[worst] = None


def crossfit(
    by_family: Mapping[str, Sequence[Unit]],
    signals: Signals,
    lam: float,
    floor: float,
    in_first: Callable[[str], bool],
) -> dict[str, Point]:
    """Thresholds picked on one half (`in_first` says which image is in it), scored on the other,
    both ways, summed per family."""
    halves = [
        {f: [u for u in us if in_first(u.file) == first] for f, us in by_family.items()}
        for first in (True, False)
    ]
    summed: dict[str, Point] = {}
    for pick, score in ((halves[0], halves[1]), (halves[1], halves[0])):
        chosen = fit(pick, signals, lam, floor)
        for family, units in score.items():
            summed[family] = _added(
                summed.get(family, NONE), point(units, signals[family][0], chosen[family])
            )
    return summed


def calibrate(scored: Sequence[tuple[float, bool]], *, logit: bool = False) -> Calibration | None:
    """P(wrong | value) by logistic regression (Newton's method on the standardised value, or its
    logit, with a small ridge); None when there is no value to fit on. `scored`: (value, wrong)
    pairs."""
    if not scored:
        return None
    if logit:
        scored = [(_logit(x), wrong) for x, wrong in scored]
    mu = sum(x for x, _ in scored) / len(scored)
    sd = math.sqrt(sum((x - mu) ** 2 for x, _ in scored) / len(scored)) or 1.0
    a = b = 0.0
    for _ in range(50):
        ga, gb, haa, hab, hbb = RIDGE * a, RIDGE * b, RIDGE, 0.0, RIDGE
        for x, wrong in scored:
            z = (x - mu) / sd
            p = _sigmoid(a + b * z)
            w = p * (1 - p)
            ga, gb = ga + p - wrong, gb + (p - wrong) * z
            haa, hab, hbb = haa + w, hab + w * z, hbb + w * z * z
        det = haa * hbb - hab * hab
        step_a, step_b = (hbb * ga - hab * gb) / det, (haa * gb - hab * ga) / det
        a, b = a - step_a, b - step_b
        if abs(step_a) + abs(step_b) < 1e-10:
            break
    return Calibration(a=a, b=b, mu=mu, sd=sd, logit=logit)


class FlagUnits(BaseModel):
    """A rule that flags some answers whatever their signal (D18: fable-rooms' "drawn as a bedroom,
    no printed label, not counted" places), as the val units it flags."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_: str = Field(alias="schema", default="flag_units_v1")
    name: str
    arm: str
    units: list[tuple[str, str]] = Field(description="(file, family) pairs")


def flag_always(units: Sequence[Unit], flagged: Set[tuple[str, str]]) -> list[Unit]:
    """`units` with the signals dropped where (file, family) is in `flagged`: those are flagged
    whatever their signal and left out of the calibration."""
    return [
        Unit(file=u.file, family=u.family, exact=u.exact, signals=dict.fromkeys(u.signals))
        if (u.file, u.family) in flagged
        else u
        for u in units
    ]


def probabilities(by_family: Mapping[str, Sequence[Unit]], signals: Signals) -> frozenset[str]:
    """The signals whose every value (over all the families gated on them) lies in [0, 1]."""
    values: dict[str, list[float]] = {}
    for family, units in by_family.items():
        signal = signals[family][0]
        values.setdefault(signal, []).extend(
            v for u in units if (v := _value(u, signal)) is not None
        )
    return frozenset(s for s, vs in values.items() if vs and all(0 <= v <= 1 for v in vs))


def calibrations(
    by_family: Mapping[str, Sequence[Unit]], signals: Signals, logit: Set[str] = frozenset()
) -> dict[str, Calibration | None]:
    """Each family's calibration on its signal, on the logit for the signals in `logit` (None for
    a family with a fixed cut)."""
    made: dict[str, Calibration | None] = {}
    for family, units in by_family.items():
        signal, fixed = signals[family]
        scored = [(v, not u.exact) for u in units if (v := _value(u, signal)) is not None]
        made[family] = None if fixed is not None else calibrate(scored, logit=signal in logit)
    return made


def thresholds_at(
    calibrated: Mapping[str, Calibration | None], signals: Signals, cut: float
) -> dict[str, float | None]:
    """Each family's threshold at the P(wrong) cut; a fixed cut as given."""
    chosen: dict[str, float | None] = {}
    for family, model in calibrated.items():
        fixed = signals[family][1]
        chosen[family] = fixed if fixed is not None else model and model.threshold(cut)
    return chosen


def recall_cut(scored: Sequence[tuple[float, bool]], need: int) -> float:
    """A P(wrong) cut that flags (P(wrong) above it) the fewest pairs holding at least `need`
    wrong ones, ties together: halfway between the last flagged P(wrong) and the next, so no pair
    sits on it. `scored`: (P(wrong), wrong) pairs. 0 (flag all) when all of them hold fewer."""
    ordered = sorted(scored, key=lambda pair: -pair[0])
    below = [p for p, _ in ordered[1:]] + [0.0]
    if need <= 0:
        return (1.0 + ordered[0][0]) / 2 if ordered else 1.0
    caught = 0
    for (p, wrong), lower in zip(ordered, below, strict=True):
        caught += wrong
        if caught >= need and lower < p:
            return (p + lower) / 2
    return 0.0


def recall_fit(
    by_family: Mapping[str, Sequence[Unit]],
    signals: Signals,
    recall: float,
    in_first: Callable[[str], bool],
) -> tuple[float, dict[str, Point]]:
    """D476's cut, chosen on the cross-fit P(wrong) (each half calibrated on the other), and the
    cross-fit points at that cut per family. Units a fixed cut or a missing value flags count
    toward the recall before any cut is chosen."""
    halves = [
        {f: [u for u in us if in_first(u.file) == first] for f, us in by_family.items()}
        for first in (True, False)
    ]
    logit = probabilities(by_family, signals)
    folds = [
        (calibrations(fit_on, signals, logit), score)
        for fit_on, score in zip(halves[::-1], halves, strict=True)
    ]
    wrong = sum(not u.exact for us in by_family.values() for u in us)
    caught, scored = 0, list[tuple[float, bool]]()
    for calibrated, score in folds:
        for family, units in score.items():
            signal, fixed = signals[family]
            model = calibrated[family]
            for unit in units:
                value = _value(unit, signal)
                if value is None or (fixed is None and (model is None or model.b >= 0)):
                    caught += not unit.exact
                elif fixed is not None:
                    caught += not unit.exact and value < fixed
                else:
                    assert model is not None
                    scored.append((model.p_wrong(value), not unit.exact))
    cut = recall_cut(scored, math.ceil(recall * wrong - 1e-9) - caught)
    held: dict[str, Point] = {}
    for calibrated, score in folds:
        chosen = thresholds_at(calibrated, signals, cut)
        for family, units in score.items():
            held[family] = _added(
                held.get(family, NONE), point(units, signals[family][0], chosen[family])
            )
    return cut, held


def pooled(points: Mapping[str, Point]) -> Point:
    total = NONE
    for p in points.values():
        total = _added(total, p)
    return total


def route_verdict(exact: Sequence[bool], lam: float, floor: float) -> RouteVerdict:
    """A route certified whole: its holdout answers reach the floor and the rule's utility > 0."""
    p = Point(
        units=len(exact),
        certified=len(exact),
        exact=sum(exact),
        wrong=len(exact) - sum(exact),
        no_value=0,
    )
    ok = bool(exact) and p.exact / p.certified >= floor and utility(p, lam) > 0
    return RouteVerdict(certified=ok, holdout=p, lower_bound=cp_lower(p.exact, p.certified))

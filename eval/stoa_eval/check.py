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
same recall; D17). A family with fewer than `pool_below` wrong answers on val is not fit alone: with
three errors, a half's own fit is nearly flat and flags half the family. D23 fits all such families
together, across their signals; `pool_with="signal"` fits each on every family gated on its own
signal, which keeps one curve per signal (C1-T1 val, cross-fit at 96%: 43.9% flagged, against 58.1%
with D23 and 47.9% fitting each family alone).

Routes the raster gate does not see (vector, IFC model, schedules) are certified whole or not from
golden v2's holdout answers: certified when they reach the floor and the same utility is positive.

Levels (confidence's scheme B, `.agents/exp/confidence-levels.md` section 5): High = certified;
Medium = asks, with the calibrated P(wrong) at or under a second cut (`medium`, a second threshold
per family read from the same all-val calibration); Low = every other answer. A calibration group
whose cross-fit Medium holds fewer than `min_units` answers or is under `min_exact` exact gets no
Medium. A route certified whole is High; another is Medium when its golden v2 dev answers reach
`min_units` at `min_exact`, else Low.
"""

import math
from collections.abc import Callable, Mapping, Sequence, Set
from typing import Literal

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
POOL_BELOW = 10  # D23: a family with fewer wrong answers on val is not calibrated alone
PoolWith = Literal["small", "signal"]  # D23: all such families together; or its signal's families
Level = Literal["high", "medium", "low"]
LEVELS: tuple[Level, ...] = ("high", "medium", "low")
MEDIUM_MIN_UNITS = 30  # a Medium band rests on at least this many cross-fit answers
MEDIUM_MIN_EXACT = 0.80  # and at least this share of them exact


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
    group: str | None = Field(
        default=None, description="D476: the families its calibration is fit on, if not itself"
    )
    medium: float | None = Field(
        default=None, description="levels: lowest Medium value (asks, P(wrong) <= levels.cut)"
    )


class LevelPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    units: int
    exact: int


class RouteVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    certified: bool
    holdout: Point = Field(description="golden v2 holdout questions answered on the route")
    lower_bound: float | None = Field(description="95% Clopper-Pearson bound on the exact share")
    level: Level | None = Field(default=None, description="levels: the route's answers' level")
    dev: LevelPoint | None = Field(
        default=None, description="levels: golden v2 dev questions answered on the route"
    )


class Levels(BaseModel):
    """High = certified; Medium = asks, P(wrong) at or under `cut`; Low = the rest."""

    model_config = ConfigDict(extra="forbid")

    cut: float = Field(description="Medium up to this calibrated P(wrong)")
    min_units: int = Field(description="a calibration group's cross-fit Medium needs this many")
    min_exact: float = Field(description="and this share of them exact, or it has no Medium")
    crossfit: dict[Level, LevelPoint] = Field(
        description="val, each gate half under the other half's fit, pooled"
    )


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
    pool_below: int | None = Field(
        default=None, description="D476: families with fewer wrong answers are not fit alone"
    )
    pool_with: PoolWith | None = Field(
        default=None, description="small: all such families together; signal: its signal's"
    )
    always_flag: list[str] = Field(
        default_factory=list, description="rules whose units are flagged whatever their signal"
    )
    cut: float | None = Field(default=None, description="D476: flagged from this P(wrong) on")
    families: dict[str, CheckFamily]
    routes: dict[str, RouteVerdict]
    pooled_val: Point
    pooled_crossfit: Point
    test: dict[str, object] | None = None
    levels: Levels | None = None


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


def groups_below(
    by_family: Mapping[str, Sequence[Unit]],
    signals: Signals,
    below: int,
    pool_with: PoolWith = "small",
) -> dict[str, tuple[str, ...]]:
    """Family -> the families its calibration is fit on. A family (without a fixed cut) with
    fewer than `below` wrong answers: with `small`, every such family (when there are two or
    more); with `signal`, every family without a fixed cut on its signal. Any other: itself."""
    fitted = [f for f in by_family if signals[f][1] is None]
    small = [f for f in fitted if sum(not u.exact for u in by_family[f]) < below]
    made: dict[str, tuple[str, ...]] = {f: (f,) for f in by_family}
    for family in small:
        if pool_with == "small" and len(small) >= 2:
            made[family] = tuple(sorted(small))
        elif pool_with == "signal":
            made[family] = tuple(sorted(f for f in fitted if signals[f][0] == signals[family][0]))
    return made


def calibrations(
    by_family: Mapping[str, Sequence[Unit]],
    signals: Signals,
    logit: Set[str] = frozenset(),
    groups: Mapping[str, tuple[str, ...]] | None = None,
) -> dict[str, Calibration | None]:
    """Each family's calibration, fit on the values of the families `groups` gives it (default
    itself), each on its own signal, on the logit when all those signals are in `logit` (None
    for a family with a fixed cut). Families fit on the same families share one calibration."""
    fits: dict[tuple[str, ...], Calibration | None] = {}
    made: dict[str, Calibration | None] = dict.fromkeys(by_family)
    for family in by_family:
        if signals[family][1] is not None:
            continue
        on = (groups or {}).get(family, (family,))
        if on not in fits:
            scored = [
                (v, not u.exact)
                for f in on
                for u in by_family[f]
                if (v := _value(u, signals[f][0])) is not None
            ]
            fits[on] = calibrate(scored, logit=all(signals[f][0] in logit for f in on))
        made[family] = fits[on]
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


def _folds(
    by_family: Mapping[str, Sequence[Unit]],
    signals: Signals,
    in_first: Callable[[str], bool],
    groups: Mapping[str, tuple[str, ...]] | None,
) -> list[tuple[dict[str, Calibration | None], dict[str, list[Unit]]]]:
    """Each gate half's units with the calibrations fit on the other half."""
    halves = [
        {f: [u for u in us if in_first(u.file) == first] for f, us in by_family.items()}
        for first in (True, False)
    ]
    logit = probabilities(by_family, signals)
    return [
        (calibrations(fit_on, signals, logit, groups), score)
        for fit_on, score in zip(halves[::-1], halves, strict=True)
    ]


def recall_fit(
    by_family: Mapping[str, Sequence[Unit]],
    signals: Signals,
    recall: float,
    in_first: Callable[[str], bool],
    groups: Mapping[str, tuple[str, ...]] | None = None,
) -> tuple[float, dict[str, Point]]:
    """D476's cut, chosen on the cross-fit P(wrong) (each half calibrated on the other, `groups`
    as in `calibrations`), and the cross-fit points at that cut per family. Units a fixed cut or a
    missing value flags count toward the recall before any cut is chosen."""
    folds = _folds(by_family, signals, in_first, groups)
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


def level(value: float | None, threshold: float | None, medium: float | None) -> Level:
    """High at or above the certified threshold, Medium at or above `medium`, else Low."""
    if value is not None and threshold is not None and value >= threshold:
        return "high"
    if value is not None and medium is not None and value >= medium:
        return "medium"
    return "low"


def medium_fit(
    by_family: Mapping[str, Sequence[Unit]],
    signals: Signals,
    cut: float,
    medium_cut: float,
    in_first: Callable[[str], bool],
    groups: Mapping[str, tuple[str, ...]] | None = None,
    min_units: int = MEDIUM_MIN_UNITS,
    min_exact: float = MEDIUM_MIN_EXACT,
) -> tuple[dict[str, float | None], dict[str, dict[Level, LevelPoint]]]:
    """Each family's Medium threshold, read from its all-val calibration at `medium_cut` as the
    certified one is at `cut`, and the cross-fit level counts per family. A family with a fixed
    cut has no calibration and no Medium; nor has a calibration group whose cross-fit Medium
    holds fewer than `min_units` answers or under `min_exact` exact (its Medium answers count as
    Low)."""
    seen: list[tuple[str, Level, bool]] = []
    for calibrated, score in _folds(by_family, signals, in_first, groups):
        high = thresholds_at(calibrated, signals, cut)
        medium = thresholds_at(calibrated, signals, medium_cut)
        for family, units in score.items():
            signal, fixed = signals[family]
            for unit in units:
                low = None if fixed is not None else medium[family]
                seen.append((family, level(_value(unit, signal), high[family], low), unit.exact))
    in_medium: dict[tuple[str, ...], list[bool]] = {}
    for family, made, exact in seen:
        if made == "medium":
            in_medium.setdefault((groups or {}).get(family, (family,)), []).append(exact)
    kept = {
        on
        for on, exact in in_medium.items()
        if len(exact) >= min_units and sum(exact) / len(exact) >= min_exact
    }
    logit = probabilities(by_family, signals)
    all_val = thresholds_at(calibrations(by_family, signals, logit, groups), signals, medium_cut)
    chosen = {
        f: all_val[f] if signals[f][1] is None and (groups or {}).get(f, (f,)) in kept else None
        for f in by_family
    }
    counts: dict[str, dict[Level, LevelPoint]] = {
        f: {lv: LevelPoint(units=0, exact=0) for lv in LEVELS} for f in by_family
    }
    for family, made, exact in seen:
        if made == "medium" and chosen[family] is None:
            made = "low"
        cell = counts[family][made]
        counts[family][made] = LevelPoint(units=cell.units + 1, exact=cell.exact + exact)
    return chosen, counts


def route_level(
    verdict: RouteVerdict,
    dev: Sequence[bool],
    min_units: int = MEDIUM_MIN_UNITS,
    min_exact: float = MEDIUM_MIN_EXACT,
) -> RouteVerdict:
    """The verdict with its level: High when certified; else Medium when its golden v2 dev
    answers reach `min_units` at `min_exact` exact; else Low."""
    p = LevelPoint(units=len(dev), exact=sum(dev))
    medium = p.units >= min_units and p.exact / p.units >= min_exact
    made: Level = "high" if verdict.certified else "medium" if medium else "low"
    return verdict.model_copy(update={"level": made, "dev": p})

"""The double-check policy (check_policy_v1, the backend's CHECK_POLICY): which answers are
certified as they are; every other one keeps its value and asks a person to double-check it.

Rule D455 (orchestrator for Bogdan, 2026-11-14 11:3x, fixed before any test read): per family, the
threshold on its signal that maximises (answers certified) - lambda x (wrong ones among them),
lambda 10: a wrong answer shown as certain costs ten double-checks. Chosen on all of val (the
shipped thresholds) and cross-fit on the gate halves (pick on one, score on the other: the honest
val estimate). Pooled floor: while the certified answers are under `floor` exact, the family with
the lowest exact share among its certified answers is closed. A unit is one (image, family) answer
(the questions that share it); a refused answer is never certified.

Routes the raster gate does not see (vector, IFC model, schedules) are certified whole or not from
golden v2's holdout answers: certified when they reach the floor and the same utility is positive.
"""

from collections.abc import Callable, Mapping, Sequence

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from .gate import Unit, cp_lower

SCHEMA = "check_policy_v1"
LAMBDA = 10.0
FLOOR = 0.95
RULE = (
    "D455: per family, the threshold maximising certified - lambda x wrong on val; pooled floor "
    "on the certified share exact"
)


class Point(BaseModel):
    model_config = ConfigDict(extra="forbid")

    units: int
    certified: int
    exact: int


class CheckFamily(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal: str
    threshold: float | None = Field(description="lowest certified value; null: never certified")
    fixed: bool = Field(description="a cut given, not fitted by the rule")
    val: Point = Field(description="all of val, in-sample")
    crossfit: Point = Field(description="val, picked on one gate half, scored on the other")


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
    return Point(units=len(units), certified=len(sure), exact=sum(u.exact for u in sure))


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
            p = point(units, signals[family][0], chosen[family])
            was = summed.get(family, Point(units=0, certified=0, exact=0))
            summed[family] = Point(
                units=was.units + p.units,
                certified=was.certified + p.certified,
                exact=was.exact + p.exact,
            )
    return summed


def pooled(points: Mapping[str, Point]) -> Point:
    return Point(
        units=sum(p.units for p in points.values()),
        certified=sum(p.certified for p in points.values()),
        exact=sum(p.exact for p in points.values()),
    )


def route_verdict(exact: Sequence[bool], lam: float, floor: float) -> RouteVerdict:
    """A route certified whole: its holdout answers reach the floor and the rule's utility > 0."""
    p = Point(units=len(exact), certified=len(exact), exact=sum(exact))
    ok = bool(exact) and p.exact / p.certified >= floor and utility(p, lam) > 0
    return RouteVerdict(certified=ok, holdout=p, lower_bound=cp_lower(p.exact, p.certified))

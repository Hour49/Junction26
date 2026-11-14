"""The E5 confidence gate (`stoa_eval gate`): when may an arm's count answer be marked sure?

The unit is an answer: one question family on one image (plan sheet), that is every question of
the family there (English and Finnish ask the same count). It is exact when all of them are.
A signal scores each answer from the arm's extraction of the image; higher means surer.

- `top3`: the mean `attrs.score` of the 3 most confident detections of the family's classes
  (door; shower+bathtub: both; sauna: sauna_stove and room:sauna; room:<type>). None when the
  family has no scored detection.
- `pb_mode`: the probability of the modal count when each detection is real with its calibrated
  probability (a Poisson-binomial count). Calibration maps `attrs.score` to the share of
  detections that match a gold item of their class (IoU >= 0.5, `extraction_scoring.match`), by
  isotonic regression per class (pooled when a class has fewer than MIN_CALIBRATION detections),
  fit on the calibration half of val. Missed objects are not modelled, so no detections give 1.
- `agree`: 1 when a second arm gives the same answer, else 0.

Plans carry no `attrs` in extraction_v1, and a `counts` value has no confidence field, so the
plan family has only `agree`.

Val is cut in two halves by image (seeded). The calibration half fits `pb_mode`'s calibration; the
selection half compares the signals (failure AUROC: the chance a right answer scores above a wrong
one; a risk-coverage table) and picks, per family, the loosest threshold that Learn-then-Test
certifies: thresholds go from strict to loose, each tested with the exact binomial p of "the error
rate among accepted answers is at least 1 - target", and the sequence stops at the first p above
delta / number of families (fixed-sequence testing, Bonferroni over families). Thresholds that
accept fewer answers than could ever pass are skipped; that uses only the signals, not the labels.
The val numbers only pick thresholds. The certificate is test's: it applies the val calibration and
thresholds once and gives a one-sided 95% Clopper-Pearson lower bound with the plan as the unit
(a plan marked sure counts as exact when every sure answer on it is).
"""

import bisect
import math
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .extraction import Element, Extraction, Room
from .extraction_scoring import match
from .split import rank

Signal = Literal["top3", "pb_mode", "agree"]
SIGNALS: tuple[Signal, ...] = ("top3", "pb_mode", "agree")
TOP_K = 3
MIN_CALIBRATION = 30
TARGET = 0.95
DELTA = 0.05
CONFIDENCE = 0.95
GATE_SEED = 20261114
COVERAGES = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
POOLED = "*"  # the calibration of every class together

Item = Element | Room
Steps = list[tuple[float, float]]  # isotonic blocks: (lowest score, probability), increasing


@dataclass(frozen=True)
class Unit:
    """One answer: a family on an image, whether it is exact, and its signals."""

    file: str
    family: str
    exact: bool
    signals: Mapping[str, float | None]


def family_keys(family: str) -> tuple[str, ...]:
    """The count keys (element class or room:<type>) whose detections make up the family."""
    if family == "sauna":
        return ("sauna_stove", "room:sauna")
    if family.startswith("room:"):
        return (family,)
    return tuple(family.split("+"))


def items_of(extraction: Extraction, key: str) -> list[Item]:
    if key.startswith("room:"):
        return [room for room in extraction.rooms if f"room:{room.type}" == key]
    return [element for element in extraction.elements if element.class_ == key]


def score_of(item: Item) -> float | None:
    value = item.attrs.get("score")
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def halves(files: Iterable[str], seed: int = GATE_SEED) -> tuple[list[str], list[str]]:
    """(calibration, selection): the files in seeded order, first half and second half."""
    ordered = sorted(files, key=lambda file: rank(seed, "gate", file))
    middle = len(ordered) // 2
    return sorted(ordered[:middle]), sorted(ordered[middle:])


def isotonic(points: Iterable[tuple[float, int]]) -> Steps:
    """Pool-adjacent-violators on (score, 0/1): increasing (lowest score, probability) blocks."""
    by_score: dict[float, list[int]] = defaultdict(lambda: [0, 0])
    for score, label in points:
        by_score[score][0] += label
        by_score[score][1] += 1
    blocks: list[list[float]] = []  # lowest score, hits, n
    for score in sorted(by_score):
        hits, n = by_score[score]
        blocks.append([score, hits, n])
        while len(blocks) > 1 and blocks[-2][1] / blocks[-2][2] >= blocks[-1][1] / blocks[-1][2]:
            _, hits_last, n_last = blocks.pop()
            blocks[-1][1] += hits_last
            blocks[-1][2] += n_last
    return [(low, hits / n) for low, hits, n in blocks]


def calibrated(steps: Steps, score: float) -> float:
    """The probability of the block the score falls in (below the first block: the first)."""
    lows = [low for low, _ in steps]
    return steps[max(0, bisect.bisect_right(lows, score) - 1)][1]


def calibrate(
    golds: Mapping[str, Extraction], preds: Mapping[str, Extraction], keys: Iterable[str]
) -> dict[str, Steps]:
    """Per key, isotonic steps from score to "matches a gold item"; POOLED over all keys."""
    labelled: dict[str, list[tuple[float, int]]] = defaultdict(list)
    for file, pred in preds.items():
        gold = golds.get(file)
        if gold is None:
            continue
        for key in keys:
            mine = items_of(pred, key)
            hit = {p for _, p in match(items_of(gold, key), mine)}
            for index, item in enumerate(mine):
                if (score := score_of(item)) is not None:
                    labelled[key].append((score, int(index in hit)))
    steps = {
        key: isotonic(points) for key, points in labelled.items() if len(points) >= MIN_CALIBRATION
    }
    pooled = [point for points in labelled.values() for point in points]
    if pooled:
        steps[POOLED] = isotonic(pooled)
    return steps


def modal_probability(probabilities: Sequence[float]) -> float:
    """The largest point probability of a Poisson-binomial count."""
    dist = [1.0]
    for p in probabilities:
        dist = [
            (dist[k] if k < len(dist) else 0.0) * (1 - p) + (dist[k - 1] * p if k else 0.0)
            for k in range(len(dist) + 1)
        ]
    return max(dist)


def signals_of(
    extraction: Extraction | None,
    family: str,
    steps: Mapping[str, Steps],
    agree: bool | None,
) -> dict[str, float | None]:
    """The three signals of one answer; `agree` None means no second arm."""
    found: list[tuple[str, float]] = []
    unscored = 0
    if extraction is not None:
        for key in family_keys(family):
            for item in items_of(extraction, key):
                score = score_of(item)
                if score is None:
                    unscored += 1
                else:
                    found.append((key, score))
    scores = sorted((score for _, score in found), reverse=True)[:TOP_K]
    top = sum(scores) / len(scores) if scores else None
    mode: float | None = None
    if extraction is not None and family != "plan" and not unscored and POOLED in steps:
        mode = modal_probability(
            [calibrated(steps.get(key) or steps[POOLED], score) for key, score in found]
        )
    return {
        "top3": top,
        "pb_mode": mode,
        "agree": None if agree is None else float(agree),
    }


def _order(value: float | None) -> float:
    return -math.inf if value is None else value


def failure_auroc(units: Sequence[Unit], signal: str) -> float | None:
    """P(a right answer's signal > a wrong one's), ties half (Mann-Whitney); None without both,
    or when no answer has a value."""
    if all(u.signals[signal] is None for u in units):
        return None
    values = sorted((_order(u.signals[signal]), u.exact) for u in units)
    right = sum(exact for _, exact in values)
    wrong = len(values) - right
    if not right or not wrong:
        return None
    rank_sum, index = 0.0, 0
    while index < len(values):
        end = index
        while end < len(values) and values[end][0] == values[index][0]:
            end += 1
        mean_rank = (index + 1 + end) / 2
        rank_sum += mean_rank * sum(exact for _, exact in values[index:end])
        index = end
    return (rank_sum - right * (right + 1) / 2) / (right * wrong)


class CoveragePoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: float
    threshold: float | None
    coverage: float = Field(description="share accepted at that threshold, ties included")
    accepted: int
    exact_rate: float | None


def risk_coverage(units: Sequence[Unit], signal: str) -> list[CoveragePoint]:
    """For each target coverage: the threshold of the unit at that rank, and what it accepts."""
    if all(u.signals[signal] is None for u in units):
        return []
    values = sorted((_order(u.signals[signal]) for u in units), reverse=True)
    points: list[CoveragePoint] = []
    for target in COVERAGES:
        if not values:
            break
        threshold = values[max(0, math.ceil(target * len(values)) - 1)]
        accepted = [u for u in units if _order(u.signals[signal]) >= threshold]
        points.append(
            CoveragePoint(
                target=target,
                threshold=None if threshold == -math.inf else threshold,
                coverage=len(accepted) / len(units),
                accepted=len(accepted),
                exact_rate=sum(u.exact for u in accepted) / len(accepted),
            )
        )
    return points


def binom_cdf(k: int, n: int, p: float) -> float:
    """P(Binomial(n, p) <= k)."""
    if k < 0:
        return 0.0
    if k >= n or p <= 0.0:
        return 1.0
    if p >= 1.0:
        return 0.0
    log_p, log_q, total = math.log(p), math.log1p(-p), 0.0
    for i in range(k + 1):
        log_c = math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
        total += math.exp(log_c + i * log_p + (n - i) * log_q)
    return min(1.0, total)


def cp_lower(hits: int, n: int, confidence: float = CONFIDENCE) -> float | None:
    """One-sided Clopper-Pearson lower bound of a success rate."""
    if n == 0:
        return None
    if hits == 0:
        return 0.0
    low, high = 0.0, 1.0
    for _ in range(100):  # P(X >= hits | p) rises with p: find where it is 1 - confidence
        middle = (low + high) / 2
        if 1.0 - binom_cdf(hits - 1, n, middle) < 1.0 - confidence:
            low = middle
        else:
            high = middle
    return low


class LttStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    threshold: float
    accepted: int
    errors: int
    p: float


class FamilyGate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    threshold: float | None = Field(description="accept at or above; null: the gate stays shut")
    answers: int
    accepted: int
    exact: int
    steps: list[LttStep]


def min_accepted(target: float = TARGET, delta: float = DELTA) -> int:
    """The fewest accepted answers that can pass, with no error at all."""
    return math.ceil(math.log(delta) / math.log(target))


def learn_then_test(
    units: Sequence[Unit], signal: str, target: float = TARGET, delta: float = DELTA
) -> FamilyGate:
    """Fixed-sequence LTT from strict to loose; the loosest threshold before the first failure."""
    alpha, floor = 1.0 - target, min_accepted(target, delta)
    scored = [u for u in units if u.signals[signal] is not None]
    chosen: float | None = None
    steps: list[LttStep] = []
    for threshold in sorted({_order(u.signals[signal]) for u in scored}, reverse=True):
        accepted = [u for u in scored if _order(u.signals[signal]) >= threshold]
        if len(accepted) < floor:
            continue
        errors = sum(not u.exact for u in accepted)
        p = binom_cdf(errors, len(accepted), alpha)
        steps.append(LttStep(threshold=threshold, accepted=len(accepted), errors=errors, p=p))
        if p > delta:
            break
        chosen = threshold
    return apply_gate(units, signal, chosen, steps)


def family_gates(
    by_family: Mapping[str, Sequence[Unit]],
    signal: str,
    target: float = TARGET,
    delta: float = DELTA,
) -> dict[str, FamilyGate]:
    """Learn-then-Test per family at delta / families (Bonferroni), so that with probability at
    least 1 - delta every chosen threshold meets the target at once."""
    each = delta / max(1, len(by_family))
    return {
        family: learn_then_test(by_family[family], signal, target, each)
        for family in sorted(by_family)
    }


def apply_gate(
    units: Sequence[Unit], signal: str, threshold: float | None, steps: list[LttStep] | None = None
) -> FamilyGate:
    accepted = [
        u
        for u in units
        if threshold is not None
        and u.signals[signal] is not None
        and _order(u.signals[signal]) >= threshold
    ]
    return FamilyGate(
        threshold=threshold,
        answers=len(units),
        accepted=len(accepted),
        exact=sum(u.exact for u in accepted),
        steps=steps or [],
    )


class Certificate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plans: int = Field(description="plans the gate opens on (at least one answer marked sure)")
    of_plans: int
    exact_plans: int = Field(description="plans whose every sure answer is exact")
    lower_bound: float | None
    opens: float | None = Field(description="plans opened / plans")
    sentence: str


def certificate(
    units: Sequence[Unit], signal: str, thresholds: Mapping[str, float | None], label: str
) -> Certificate:
    """Pooled over families with the plan as the unit."""
    sure: dict[str, list[bool]] = defaultdict(list)
    plans = {u.file for u in units}
    for u in units:
        threshold = thresholds.get(u.family)
        value = u.signals[signal]
        if threshold is not None and value is not None and value >= threshold:
            sure[u.file].append(u.exact)
    exact = sum(all(flags) for flags in sure.values())
    bound = cp_lower(exact, len(sure))
    opens = len(sure) / len(plans) if plans else None
    return Certificate(
        plans=len(sure),
        of_plans=len(plans),
        exact_plans=exact,
        lower_bound=bound,
        opens=opens,
        sentence=sentence(bound, len(sure), opens, label),
    )


def sentence(bound: float | None, plans: int, opens: float | None, label: str) -> str:
    x = "n/a" if bound is None else f"{bound:.1%}"
    y = "n/a" if opens is None else f"{opens:.1%}"
    return (
        f"{label}: of the plans marked sure, at least {x} have every sure answer exact ({plans} "
        f"plans, 95% bound); the gate opens on {y} of plans"
    )


class SignalReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scored: int = Field(description="answers the signal has a value for")
    auroc: float | None = Field(description="failure AUROC, all families pooled")
    auroc_by_family: dict[str, float | None]
    risk_coverage: list[CoveragePoint]


class FamilyResult(FamilyGate):
    lower_bound: float | None = Field(description="one-sided 95% Clopper-Pearson, exact/accepted")
    sentence: str


class GateResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    arm: str
    second: str | None
    part: str
    images: int = Field(description="the images the signals are compared and the gate set on")
    seed: int
    target: float
    delta: float
    family_delta: float | None = Field(default=None, description="delta / families (Bonferroni)")
    signal: Signal
    compared: dict[str, SignalReport]
    calibration: dict[str, Steps]
    families: dict[str, FamilyResult]
    certificate: Certificate


def compare_signals(units: Sequence[Unit]) -> dict[str, SignalReport]:
    families = sorted({u.family for u in units})
    return {
        signal: SignalReport(
            scored=sum(u.signals[signal] is not None for u in units),
            auroc=failure_auroc(units, signal),
            auroc_by_family={
                f: failure_auroc([u for u in units if u.family == f], signal) for f in families
            },
            risk_coverage=risk_coverage(units, signal),
        )
        for signal in SIGNALS
    }


def family_result(gate: FamilyGate, family: str, label: str) -> FamilyResult:
    bound = cp_lower(gate.exact, gate.accepted)
    opens = gate.accepted / gate.answers if gate.answers else None
    return FamilyResult(
        **gate.model_dump(),
        lower_bound=bound,
        sentence=sentence(bound, gate.accepted, opens, f"{label}, {family}"),
    )


def _cell(value: float | None, pct: bool = True) -> str:
    if value is None:
        return "n/a"
    return f"{value:.1%}" if pct else f"{value:.3f}"


def format_gate(result: GateResult) -> str:
    lines = [
        f"## Gate on {result.part}: {result.arm}"
        + (f" (second arm {result.second})" if result.second else ""),
        "",
        f"{result.images} images; target {result.target:.0%} exact among sure answers, delta "
        f"{result.delta} ({result.family_delta:.4f} per family); signal used: **{result.signal}**"
        if result.family_delta is not None
        else f"{result.images} images; signal used: **{result.signal}**",
        "",
        "Only the test bound is a certificate; val numbers pick the thresholds.",
        "",
        "| signal | answers scored | failure AUROC | "
        + " | ".join(f"exact @{point:.0%}" for point in COVERAGES)
        + " |",
        "| --- | --- | --- | " + " | ".join("---" for _ in COVERAGES) + " |",
    ]
    for name, report in result.compared.items():
        by_target = {point.target: point for point in report.risk_coverage}
        cells = [
            f"{_cell(by_target[t].exact_rate)} ({by_target[t].coverage:.0%})"
            if t in by_target
            else "-"
            for t in COVERAGES
        ]
        lines.append(
            f"| {name} | {report.scored} | {_cell(report.auroc, pct=False)} | "
            + " | ".join(cells)
            + " |"
        )
    lines += [
        "",
        "Cells: exact rate among accepted answers (actual coverage, ties included).",
        "",
        "| family | answers | AUROC | threshold | sure | exact | 95% lower bound | opens |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    report = result.compared[result.signal]
    for family, gate in result.families.items():
        lines.append(
            f"| {family} | {gate.answers} | {_cell(report.auroc_by_family.get(family), False)} "
            f"| {_cell(gate.threshold, pct=False)} | {gate.accepted} | {gate.exact} "
            f"| {_cell(gate.lower_bound)} "
            f"| {_cell(gate.accepted / gate.answers if gate.answers else None)} |"
        )
    lines += ["", result.certificate.sentence + "."]
    return "\n".join(lines)

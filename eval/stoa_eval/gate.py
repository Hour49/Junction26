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
  fit on the calibration half of val. Missed objects are not modelled, so an answer where the arm
  found nothing would always score 1; it gets instead the calibration half's exact rate of such
  answers in its family, (exact + 1) / (n + 2) (an empty shower count is right far less often than
  an empty sauna count).
- `agree`: 1 when a second arm gives the same answer, else 0.
- `agree_pb`: agree + pb_mode (0 when pb_mode has none): agreeing answers first, ordered by
  pb_mode within each group. On val (C-yolo26s-v8 with seg/C), agree alone ties 125 sauna answers
  at one value; ordered by pb_mode they pass Learn-then-Test.
- a signal file (`--signal-file`, gate_signal_v1): any other producer's value per answer, for
  example a verifier's probability that the arm's count is right. It names the arm whose answers
  it judges (refused for another arm) or null when the value does not depend on the arm; an answer
  it has no value for is never sure.

Plans carry no `attrs` in extraction_v1, and a `counts` value has no confidence field, so the
plan family has only `agree`.

Val is cut in two halves by image (seeded). The calibration half fits `pb_mode`'s calibration; the
selection half compares the signals (failure AUROC: the chance a right answer scores above a wrong
one; a risk-coverage table) and picks, per family, the loosest threshold that Learn-then-Test
certifies: thresholds go from strict to loose, each tested with the exact binomial p of "the error
rate among accepted answers is at least 1 - target", and the sequence stops at the first p above
delta / number of families (fixed-sequence testing, Bonferroni over families). Thresholds that
accept fewer answers than could ever pass are skipped; that uses only the signals, not the labels.
With `--pool`, a group of families (elements, plans, rooms) gets one threshold instead, with the
plan as the unit (a plan with a sure answer of the group is wrong when any of them is): the
loosest threshold whose val plans meet the target with a one-sided 1 - delta Clopper-Pearson
bound. Every threshold is looked at (no fixed sequence, no split of delta), because the val pick
is a choice, not a guarantee: the guarantee is the test run's single certificate. A family too
small to open alone can open with its group. The val numbers only pick thresholds. The
certificate is test's: it applies the val calibration and thresholds once and gives a one-sided
95% Clopper-Pearson lower bound with the plan as the unit (a plan marked sure counts as exact
when every sure answer on it is).
"""

import bisect
import math
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .extraction import Element, Extraction, Room
from .extraction_scoring import match
from .split import rank

SIGNALS: tuple[str, ...] = ("top3", "pb_mode", "agree", "agree_pb")  # signal files add more
TOP_K = 3
MIN_CALIBRATION = 30
TARGET = 0.95
DELTA = 0.05
CONFIDENCE = 0.95
GATE_SEED = 20261114
COVERAGES = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
POOLED = "*"  # the calibration of every class together
ON_VAL = "chosen on val, not a guarantee"

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


def found_nothing(extraction: Extraction | None, family: str) -> bool:
    """The arm read the image and found no item of the family."""
    return extraction is not None and not any(
        items_of(extraction, key) for key in family_keys(family)
    )


def nothing_found_rates(units: Iterable[Unit], preds: Mapping[str, Extraction]) -> dict[str, float]:
    """Per family, (exact + 1) / (n + 2) over the answers where the arm found nothing of it."""
    counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for u in units:
        if u.family != "plan" and found_nothing(preds.get(u.file), u.family):
            counts[u.family][0] += u.exact
            counts[u.family][1] += 1
    return {family: (hits + 1) / (n + 2) for family, (hits, n) in sorted(counts.items())}


def signals_of(
    extraction: Extraction | None,
    family: str,
    steps: Mapping[str, Steps],
    agree: bool | None,
    empty: Mapping[str, float] | None = None,
) -> dict[str, float | None]:
    """The built-in signals of one answer; `agree` None means no second arm. `empty`: pb_mode of an
    answer where the arm found nothing, per family (nothing_found_rates); without it, 1."""
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
        if not found and empty is not None:
            mode = empty.get(family, 0.5)  # (0 + 1) / (0 + 2): no such answer to learn from
    return {
        "top3": top,
        "pb_mode": mode,
        "agree": None if agree is None else float(agree),
        "agree_pb": None if agree is None else float(agree) + (mode or 0.0),
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


class SignalValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file: str = Field(pattern=r"^data/[^/]+/.+", description="the dataset path, as in questions")
    family: str = Field(description="the gate's family: door, shower+bathtub, plan, room:wc, ...")
    value: float | None = Field(description="higher is surer; null: no value (never sure)")


class SignalFile(BaseModel):
    """gate_signal_v1: one producer's value for each answer (a family on an image)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_: Literal["gate_signal_v1"] = Field(alias="schema")
    name: str = Field(pattern=r"^[a-z][a-z0-9_-]*$", description="the signal's name in reports")
    arm: str | None = Field(
        description="the arm whose answers the values judge, as its folder under data/stoa/exp "
        "(detector/C-yolo26s-v8); null when the value does not depend on the arm"
    )
    values: list[SignalValue]

    def by_answer(self) -> dict[tuple[str, str], float | None]:
        return {(v.file, v.family): v.value for v in self.values}


def load_signal_file(path: Path) -> SignalFile:
    """Reads and checks a signal file: a name no built-in signal has, one value per answer."""
    try:
        made = SignalFile.model_validate_json(path.read_text("utf-8"))
    except ValidationError as error:
        raise ValueError(f"{path}: not a gate_signal_v1 file: {error}") from error
    if made.name in SIGNALS:
        raise ValueError(f"{path}: the name {made.name!r} is a built-in signal")
    seen: set[tuple[str, str]] = set()
    for v in made.values:
        if (v.file, v.family) in seen:
            raise ValueError(f"{path}: two values for {v.family} on {v.file}")
        seen.add((v.file, v.family))
    return made


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


def fixed_sequence(
    thresholds: Iterable[float],
    outcome: Callable[[float], tuple[int, int]],
    target: float = TARGET,
    delta: float = DELTA,
) -> tuple[float | None, list[LttStep]]:
    """Thresholds from strict to loose, each tested on its (accepted, errors); the loosest
    threshold before the first failure (None when the first one tested fails)."""
    alpha, floor = 1.0 - target, min_accepted(target, delta)
    chosen: float | None = None
    steps: list[LttStep] = []
    for threshold in sorted(set(thresholds), reverse=True):
        accepted, errors = outcome(threshold)
        if accepted < floor:
            continue
        p = binom_cdf(errors, accepted, alpha)
        steps.append(LttStep(threshold=threshold, accepted=accepted, errors=errors, p=p))
        if p > delta:
            break
        chosen = threshold
    return chosen, steps


def learn_then_test(
    units: Sequence[Unit], signal: str, target: float = TARGET, delta: float = DELTA
) -> FamilyGate:
    """Fixed-sequence LTT from strict to loose; the loosest threshold before the first failure."""
    scored = [u for u in units if u.signals[signal] is not None]

    def outcome(threshold: float) -> tuple[int, int]:
        accepted = [u for u in scored if _order(u.signals[signal]) >= threshold]
        return len(accepted), sum(not u.exact for u in accepted)

    values = (_order(u.signals[signal]) for u in scored)
    chosen, steps = fixed_sequence(values, outcome, target, delta)
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


def sure_plans(
    units: Iterable[Unit], signal: str, thresholds: Mapping[str, float | None]
) -> dict[str, bool]:
    """Each plan with a sure answer (at or above its family's threshold): is every sure answer on
    it exact?"""
    sure: dict[str, bool] = {}
    for u in units:
        threshold, value = thresholds.get(u.family), u.signals[signal]
        if threshold is not None and value is not None and value >= threshold:
            sure[u.file] = sure.get(u.file, True) and u.exact
    return sure


class GroupGate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    families: list[str]
    threshold: float | None = Field(description="every family of the group: accept at or above")
    plans: int = Field(description="plans with an answer of the group")
    accepted: int = Field(description="plans with a sure answer of the group")
    exact: int = Field(description="of those, plans whose every sure answer of the group is exact")
    steps: list[LttStep]
    alone_threshold: float | None = Field(
        default=None, description="val: the group's own pick, before the all-groups check"
    )
    alone_accepted: int | None = Field(default=None, description="sure plans at alone_threshold")
    alone_exact: int | None = None


class UnionStep(BaseModel):
    """One tightening of the all-groups check: a group moves to its next stricter threshold."""

    model_config = ConfigDict(extra="forbid")

    group: str
    threshold: float | None = Field(description="the group's new threshold; null: shut")
    plans: int = Field(description="sure plans of all groups together after the step")
    wrong: int
    p: float


def group_members(
    families: Iterable[str], groups: Mapping[str, Sequence[str]]
) -> dict[str, list[str]]:
    """The groups with a family here, each with its families here; a family in no group is a
    group of its own, named after it."""
    members: dict[str, list[str]] = {}
    for family in sorted(families):
        name = next((group for group, of in groups.items() if family in of), family)
        members.setdefault(name, []).append(family)
    return members


def apply_group(
    units: Sequence[Unit],
    signal: str,
    families: Sequence[str],
    threshold: float | None,
    steps: list[LttStep] | None = None,
) -> GroupGate:
    sure = sure_plans(units, signal, dict.fromkeys(families, threshold))
    return GroupGate(
        families=sorted(families),
        threshold=threshold,
        plans=len({u.file for u in units}),
        accepted=len(sure),
        exact=sum(sure.values()),
        steps=steps or [],
    )


def group_gate(
    units: Sequence[Unit],
    signal: str,
    families: Sequence[str],
    target: float = TARGET,
    delta: float = DELTA,
) -> GroupGate:
    """The loosest threshold over the group's answers, the plan as the unit, whose one-sided
    1 - delta Clopper-Pearson lower bound of the exact share is at least the target (the same as
    the exact binomial p of "error >= 1 - target" at most delta). Every threshold is tested, so a
    stricter one that fails does not stop a looser one: chosen on val, not a guarantee."""
    alpha, floor = 1.0 - target, min_accepted(target, delta)
    chosen: float | None = None
    steps: list[LttStep] = []
    values = {value for u in units if (value := u.signals[signal]) is not None}
    for threshold in sorted(values, reverse=True):
        sure = sure_plans(units, signal, dict.fromkeys(families, threshold))
        accepted, errors = len(sure), sum(not exact for exact in sure.values())
        if accepted < floor:
            continue
        p = binom_cdf(errors, accepted, alpha)
        steps.append(LttStep(threshold=threshold, accepted=accepted, errors=errors, p=p))
        if p <= delta:
            chosen = threshold  # strict to loose: the last one that meets the target
    return apply_group(units, signal, families, chosen, steps)


def meet_on_union(
    units_of: Mapping[str, Sequence[Unit]],
    members: Mapping[str, Sequence[str]],
    picked: Mapping[str, float | None],
    signal: str,
    target: float = TARGET,
    delta: float = DELTA,
) -> tuple[dict[str, float | None], list[UnionStep]]:
    """The certificate counts a plan wrong when any of its sure answers is, over every group at
    once. While that all-groups bound misses the target (exact binomial p above delta, the same
    as the one-sided 1 - delta Clopper-Pearson bound under it), move one group to its next
    stricter threshold (shut when there is none): the move that removes the most wrong plans per
    sure plan lost (a move that loses none ranks first when it removes one), then fewer plans
    lost, then the group's name. Stops when the bound meets the target or every group is shut."""
    alpha = 1.0 - target
    every = [u for units in units_of.values() for u in units]
    values = {
        name: sorted({v for u in units if (v := u.signals[signal]) is not None})
        for name, units in units_of.items()
    }

    def union(thresholds: Mapping[str, float | None]) -> tuple[int, int]:
        by_family = {f: thresholds[name] for name, of in members.items() for f in of}
        sure = sure_plans(every, signal, by_family)
        return len(sure), sum(not exact for exact in sure.values())

    current = dict(picked)
    plans, wrong = union(current)
    steps: list[UnionStep] = []
    while plans and binom_cdf(wrong, plans, alpha) > delta:
        moves: list[tuple[tuple[float, int, str], dict[str, float | None], int, int]] = []
        for name in sorted(current):
            threshold = current[name]
            if threshold is None:
                continue
            stricter = [v for v in values[name] if v > threshold]
            trial = {**current, name: stricter[0] if stricter else None}
            after, still = union(trial)
            lost, removed = plans - after, wrong - still
            ratio = removed / lost if lost else (math.inf if removed else 0.0)
            moves.append(((-ratio, lost, name), trial, after, still))
        (_, _, name), current, plans, wrong = min(moves, key=lambda move: move[0])
        p = binom_cdf(wrong, plans, alpha) if plans else 1.0
        steps.append(UnionStep(group=name, threshold=current[name], plans=plans, wrong=wrong, p=p))
    return current, steps


def pooled_gates(
    by_family: Mapping[str, Sequence[Unit]],
    groups: Mapping[str, Sequence[str]],
    signal: str,
    target: float = TARGET,
    delta: float = DELTA,
) -> tuple[dict[str, GroupGate], dict[str, FamilyGate], list[UnionStep]]:
    """One threshold per group (group_gate, delta not split: a val choice, not a guarantee),
    then tightened until all groups together meet the target (meet_on_union); each family gets
    its group's threshold."""
    members = group_members(by_family, groups)
    units_of = {name: [u for f in of for u in by_family[f]] for name, of in members.items()}
    alone = {
        name: group_gate(units_of[name], signal, of, target, delta) for name, of in members.items()
    }
    final, union_steps = meet_on_union(
        units_of, members, {name: gate.threshold for name, gate in alone.items()}, signal,
        target, delta,
    )  # fmt: skip
    gates = {
        name: apply_group(units_of[name], signal, of, final[name], alone[name].steps).model_copy(
            update={
                "alone_threshold": alone[name].threshold,
                "alone_accepted": alone[name].accepted,
                "alone_exact": alone[name].exact,
            }
        )
        for name, of in members.items()
    }
    families = {
        family: apply_gate(by_family[family], signal, final[name])
        for name, of in members.items()
        for family in of
    }
    return gates, dict(sorted(families.items())), union_steps


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
    sure = sure_plans(units, signal, thresholds)
    plans = {u.file for u in units}
    exact = sum(sure.values())
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


class GroupResult(GroupGate):
    lower_bound: float | None = Field(description="one-sided 95% Clopper-Pearson, exact/accepted")
    sentence: str


class GateResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    arm: str
    second: str | None
    part: str
    images: int = Field(description="the images the signals are compared and the gate set on")
    seed: int
    split_sha256: str | None = Field(default=None, description="data/stoa/exp/split.json's sha256")
    target: float
    delta: float
    family_delta: float | None = Field(
        default=None, description="delta / families (Bonferroni); null with groups (not split)"
    )
    signal: str
    signal_files: dict[str, str] = Field(
        default_factory=dict[str, str], description="name -> the signal file it was read from"
    )
    compared: dict[str, SignalReport]
    calibration: dict[str, Steps]
    empty_rates: dict[str, float] = Field(
        default_factory=dict[str, float],
        description="pb_mode of an answer where the arm found nothing, per family",
    )
    families: dict[str, FamilyResult]
    groups: dict[str, GroupResult] = Field(
        default_factory=dict[str, GroupResult],
        description="--pool: one threshold per group of families, the plan as the unit",
    )
    union_steps: list[UnionStep] = Field(
        default_factory=list[UnionStep],
        description="--pool on val: the tightenings that made all groups together meet the target",
    )
    certificate: Certificate


class GateVal(BaseModel):
    """A family's val numbers in the gate policy: what the threshold did on val."""

    model_config = ConfigDict(extra="forbid")

    note: Literal["chosen on val, not a guarantee"] = ON_VAL
    answers: int
    sure: int = Field(description="answers at or above the threshold")
    exact: int = Field(description="of those, exact")
    coverage: float | None = Field(description="sure / answers")
    bound: float | None = Field(description="one-sided 95% Clopper-Pearson of exact / sure")


class GateFamily(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal: str = Field(description="the signal the threshold is on: g1main, agree_pb, ...")
    threshold: float = Field(description="an answer whose signal is at or above it is sure")
    group: str | None = Field(description="the --pool group it was chosen with; null: alone")
    val: GateVal


class GatePolicy(BaseModel):
    """gate_policy_v1 (data/stoa/exp/gate.json): per family, when an answer may be marked sure.
    Only families whose gate opens on val and marks at least one val answer sure are listed (a
    family the arm never answered, such as rooms for a detector, has no evidence for its group's
    threshold)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_: Literal["gate_policy_v1"] = Field(alias="schema")
    generated: str
    part: Literal["val"]
    split_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    arm: str = Field(description="the arm whose answers the thresholds were set on")
    second: str | None
    target: float
    source: str = Field(description="the val gate JSON it was made from")
    certified: bool = Field(description="false until the single test run certifies the gate")
    families: dict[str, GateFamily]


def gate_policy(result: GateResult, source: str, generated: str) -> GatePolicy:
    """The product's gate file from a val gate: the families whose gate opens on val answers."""
    if result.part != "val":
        raise ValueError(f"{source}: a gate policy is made from the val gate, not {result.part}")
    if result.split_sha256 is None:
        raise ValueError(f"{source}: no split_sha256 (made before it was recorded): rerun the gate")
    group_of = {f: name for name, gate in result.groups.items() for f in gate.families}
    families = {
        family: GateFamily(
            signal=result.signal,
            threshold=gate.threshold,
            group=group_of.get(family),
            val=GateVal(
                answers=gate.answers,
                sure=gate.accepted,
                exact=gate.exact,
                coverage=gate.accepted / gate.answers if gate.answers else None,
                bound=gate.lower_bound,
            ),
        )
        for family, gate in result.families.items()
        if gate.threshold is not None and gate.accepted > 0
    }
    return GatePolicy(
        schema="gate_policy_v1", generated=generated, part="val",
        split_sha256=result.split_sha256, arm=result.arm, second=result.second,
        target=result.target, source=source, certified=False, families=families,
    )  # fmt: skip


def load_gate_policy(path: Path) -> GatePolicy:
    try:
        return GatePolicy.model_validate_json(path.read_text("utf-8"))
    except ValidationError as error:
        raise ValueError(f"{path}: not a gate_policy_v1 file: {error}") from error


def compare_signals(
    units: Sequence[Unit], names: Sequence[str] = SIGNALS
) -> dict[str, SignalReport]:
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
        for signal in names
    }


def family_result(gate: FamilyGate, family: str, label: str) -> FamilyResult:
    bound = cp_lower(gate.exact, gate.accepted)
    opens = gate.accepted / gate.answers if gate.answers else None
    return FamilyResult(
        **gate.model_dump(),
        lower_bound=bound,
        sentence=sentence(bound, gate.accepted, opens, f"{label}, {family}"),
    )


def group_result(gate: GroupGate, group: str, label: str) -> GroupResult:
    bound = cp_lower(gate.exact, gate.accepted)
    opens = gate.accepted / gate.plans if gate.plans else None
    return GroupResult(
        **gate.model_dump(),
        lower_bound=bound,
        sentence=sentence(bound, gate.accepted, opens, f"{label}, {group}"),
    )


def _cell(value: float | None, pct: bool = True) -> str:
    if value is None:
        return "n/a"
    return f"{value:.1%}" if pct else f"{value:.3f}"


def format_gate(result: GateResult) -> str:
    val = result.part == "val"
    opens = f"opens{' (' + ON_VAL + ')' if val else ''}"
    if result.groups:
        rule = (
            f"per group the loosest threshold whose one-sided {1 - result.delta:.0%} "
            f"Clopper-Pearson bound on the plans meets the target"
        )
    elif result.family_delta is not None:
        rule = f"delta {result.delta} ({result.family_delta:.4f} per family)"
    else:
        rule = ""
    lines = [
        f"## Gate on {result.part}: {result.arm}"
        + (f" (second arm {result.second})" if result.second else ""),
        "",
        f"{result.images} images; target {result.target:.0%} exact among sure answers"
        + (f", {rule}" if rule else "")
        + f"; signal used: **{result.signal}**",
        "",
        f"Every number here is {ON_VAL}; only the test run's certificate (once, at the freeze) "
        "is one."
        if val
        else "Thresholds chosen on val; the certificate below is this test run's.",
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
        "Cells: exact rate among accepted answers (actual coverage, ties included)"
        + (f"; {ON_VAL}." if val else "."),
        "",
        f"| family | answers | AUROC | threshold | sure | exact | 95% lower bound | {opens} |",
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
    if result.groups:
        lines += [
            "",
            "One threshold per group, the plan as the unit: a plan is sure when one of its answers "
            "of the group is, and exact when every sure one is.",
            "",
            "| group | families | threshold | plans | sure plans | exact plans | 95% lower bound "
            f"| {opens} | alone: threshold, sure plans (exact) |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for group, gate in result.groups.items():
            alone = (
                "-"
                if gate.alone_accepted is None
                else f"{_cell(gate.alone_threshold, pct=False)}, {gate.alone_accepted} "
                f"({gate.alone_exact})"
            )
            lines.append(
                f"| {group} | {', '.join(gate.families)} | {_cell(gate.threshold, pct=False)} "
                f"| {gate.plans} | {gate.accepted} | {gate.exact} | {_cell(gate.lower_bound)} "
                f"| {_cell(gate.accepted / gate.plans if gate.plans else None)} | {alone} |"
            )
        if result.union_steps:
            last = result.union_steps[-1]
            moved = sorted({step.group for step in result.union_steps})
            lines += [
                "",
                "All groups together missed the target at the groups' own picks, so groups were "
                "tightened, most wrong plans removed per sure plan lost first: "
                + ", ".join(
                    f"{group} {_cell(result.groups[group].alone_threshold, pct=False)} -> "
                    f"{_cell(result.groups[group].threshold, pct=False)}"
                    for group in moved
                )
                + f" ({len(result.union_steps)} steps; together {last.plans} sure plans, "
                f"{last.wrong} wrong).",
            ]
    lines += ["", result.certificate.sentence + "."]
    return "\n".join(lines)

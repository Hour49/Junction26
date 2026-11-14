"""The local count arbiter T1: per page and count family, the count to answer, chosen among a few
candidates by a logistic model over what the local readers counted. No I/O; the adapter
(app/adapters/count_arbiter/) loads the model and runs the readers.

What it reads, all local and all at runtime (local-dec's T1, prototypes/localdec/arb_train.py):

- the base: the L detector over eight views (`detector-v8:<arm>`): the family's count, the
  scores of its boxes, the number of plans;
- the second count: the same detector on the canvas as is, with its one-view thresholds;
- L1: a page-level count model's P(count = i) per family.
- the prior: the train answers' share of each count per family.

Candidates are the base, the second count, L1's top, base - 1 (not below 0) and base + 1. Each
candidate k gets the features below; P(k is right) = sigmoid(coef . (x - mu) / sd + intercept),
and the pick is the candidate with the highest P (the first of equal ones). The model was fit
on out-of-fold train pages only; on val it scores +0.9 pp [-0.1, +1.8] against C-L-swap.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

# family -> the element classes it counts (a sauna is counted by its stove)
FAMILY_CLASSES: Mapping[str, tuple[str, ...]] = {
    "door": ("door",),
    "window": ("window",),
    "sink": ("sink",),
    "toilet": ("toilet",),
    "shower+bathtub": ("shower", "bathtub"),
    "sauna": ("sauna_stove",),
}
PRIOR_FLOOR = 1e-4  # a count the train answers never had
PROB_FLOOR = 1e-5  # a count L1 gives no probability (or has no head entry for)


@dataclass(frozen=True)
class FamilyModel:
    mu: tuple[float, ...]
    sd: tuple[float, ...]
    coef: tuple[float, ...]
    intercept: float


@dataclass(frozen=True)
class ArbiterModel:
    families: Mapping[str, FamilyModel]
    prior: Mapping[str, Mapping[int, float]]  # family -> count -> share of train answers


@dataclass(frozen=True)
class Reading:
    """What the local readers read of one family on one page."""

    base: int  # the eight-view count (for `plan`: its plans)
    scores: tuple[float, ...]  # the eight-view boxes' scores of the family's classes
    plans: int  # plans in the eight-view read
    second: int  # the one-view count
    probs: Sequence[float]  # L1: P(count = i), i = 0, 1, ...


@dataclass(frozen=True)
class Pick:
    count: int
    p: float  # the model's P that `count` is right: the arbiter's own confidence


def _top(probs: Sequence[float]) -> int:
    return max(range(len(probs)), key=probs.__getitem__)  # the first of equal maxima


def candidates(reading: Reading) -> list[int]:
    base = reading.base
    return sorted({base, reading.second, _top(reading.probs), max(base - 1, 0), base + 1})


def features(k: int, reading: Reading, prior: Mapping[int, float]) -> list[float]:
    """The 19 features of candidate k (the order of the model's coefficients)."""
    b, second, probs = reading.base, reading.second, reading.probs
    scores = sorted(reading.scores, reverse=True)

    def p(count: int) -> float:
        return math.log(max(probs[count] if count < len(probs) else 0.0, PROB_FLOOR))

    x = [
        k, k - b, k == b, b, second == k,
        math.log(prior.get(k, PRIOR_FLOOR)), math.log(prior.get(b, PRIOR_FLOOR)),
        reading.plans, len(scores), scores[-1] if scores else 1.0,
        sum(s < 0.5 for s in scores), sum(s < 0.7 for s in scores),
        second == k, second - k, second == b,
        p(k), p(b), _top(probs) == k, max(probs),
    ]  # fmt: skip
    return [float(v) for v in x]


def pick(model: ArbiterModel, family: str, reading: Reading) -> Pick:
    """The candidate count with the highest P; KeyError for a family the model has no fit for."""
    fit, prior = model.families[family], model.prior[family]
    best: Pick | None = None
    for k in candidates(reading):
        x = features(k, reading, prior)
        z = fit.intercept + sum(
            c * (v - m) / s for c, v, m, s in zip(fit.coef, x, fit.mu, fit.sd, strict=True)
        )
        p = 1.0 / (1.0 + math.exp(-z))
        if best is None or p > best.p:
            best = Pick(k, p)
    assert best is not None  # candidates() is never empty
    return best

"""Local gate scores lgate and lgate2 (local-dec): P(an answer's count is exact) from local readings
only, for the answer's gate in place of Gemini's g1main. No I/O; the model is a JSON the adapter
loads (app/adapters/local_gate.py), fit by prototypes/localdec/lgate_rt.py on the val answers of
one config.

What a score reads, by the model's blocks (`LocalGateModel.blocks`):

- always: the answered count a and the train prior's share of a;
- `l1`: L1's P(count) for the family: log P(a), its top P, whether its top is a;
- `readers`: the six element families only (`plan` and rooms: none): per double-check reader
  in the model's order, whether its count equals a and |count - a| capped at 3, then the share
  of readers that agree. A reader that did not look for the family gives 0, 0 and is left out
  of the share;
- `extras` (lgate2): the counted elements' scores (lowest, mean, how many below 0.5; elements
  without a score are left out) and the number of plans;
- `rooms` (room families): the counted rooms of the family's type, how many of them carry a
  printed label, all rooms on the drawing and the share of them with a label;
- `arbiter_p` (lgate2 on the T1 config): the count arbiter's P of its pick (0 for a family it
  does not pick);
- the family, one-hot over the model's families.

score = sigmoid(coef . (x - mu) / sd + intercept).
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from app.core.drawing.model import Drawing
from app.core.pipeline.count_arbiter import count_arbiter_reading
from app.core.pipeline.disputed_marks import counted_elements, reader_elements

PRIOR_FLOOR = 1e-4
PROB_FLOOR = 1e-5
ROOM = "room:"
CAP = 3  # |reader - answer| is capped here
# the families double-check readers count (they store no plans and no rooms)
READER_FAMILIES = ("door", "window", "sink", "toilet", "shower+bathtub", "sauna")


@dataclass(frozen=True)
class LocalGateModel:
    name: str  # the signal's name (`lgate`, `lgate2`)
    families: tuple[str, ...]  # one-hot order; a family not in it has no score
    readers: tuple[str, ...]  # double-check reader names, in feature order
    blocks: frozenset[str]  # of l1, readers, extras, arbiter_p
    prior: Mapping[str, Mapping[int, float]]
    mu: tuple[float, ...]
    sd: tuple[float, ...]
    coef: tuple[float, ...]
    intercept: float


@dataclass(frozen=True)
class RoomCounts:
    """The counted rooms: of the answered type, and on the whole drawing; `labelled`: with a
    printed label."""

    of_type: int
    labelled: int
    total: int
    total_labelled: int


@dataclass(frozen=True)
class GateReading:
    """What the local readers give about one answered family of one page."""

    answer: int
    probs: Sequence[float] | None = None  # L1's P(count = i); None: L1 did not run
    readers: Mapping[str, int | None] = field(
        default_factory=dict[str, int | None]
    )  # None: did not look
    scores: tuple[float | None, ...] = ()  # the counted elements' scores (None: unscored)
    plans: int = 0
    arbiter_p: float | None = None
    rooms: RoomCounts | None = None  # for a room family


def features(model: LocalGateModel, family: str, reading: GateReading) -> list[float]:
    a = reading.answer
    x: list[float] = [a, math.log(model.prior[family].get(a, PRIOR_FLOOR))]
    if "l1" in model.blocks:
        probs = reading.probs
        if probs is None:
            raise ValueError("this model needs L1's probabilities")
        top = max(range(len(probs)), key=probs.__getitem__)  # the first of equal maxima
        x += [math.log(max(probs[a] if a < len(probs) else 0.0, PROB_FLOOR)), max(probs), top == a]
    if "readers" in model.blocks:
        counts = (
            [reading.readers.get(name) for name in model.readers]
            if family in READER_FAMILIES
            else [None] * len(model.readers)
        )
        seen = [v for v in counts if v is not None]
        x += [v is not None and v == a for v in counts]
        x += [0 if v is None else min(abs(v - a), CAP) for v in counts]
        x += [sum(v == a for v in seen) / len(seen) if seen else 0.0]
    if "extras" in model.blocks:
        scores = [s for s in reading.scores if s is not None]
        x += [
            min(scores) if scores else 1.0,
            sum(scores) / len(scores) if scores else 1.0,
            sum(s < 0.5 for s in scores),
            reading.plans,
        ]
    if "rooms" in model.blocks:
        r = reading.rooms if family.startswith(ROOM) else None
        x += (
            [r.of_type, r.labelled, r.total, r.total_labelled / max(r.total, 1)]
            if r is not None
            else [0, 0, 0, 0.0]
        )
    if "arbiter_p" in model.blocks:
        x += [reading.arbiter_p if reading.arbiter_p is not None else 0.0]
    x += [family == f for f in model.families]
    return [float(v) for v in x]


def score(model: LocalGateModel, family: str, reading: GateReading) -> float | None:
    """P(the answer is exact); None for a family the model was not fit on."""
    if family not in model.families:
        return None
    x = features(model, family, reading)
    if len(x) != len(model.coef):
        raise ValueError(f"{model.name}: {len(x)} features for {len(model.coef)} coefficients")
    z = model.intercept + sum(
        c * (v - m) / s for c, v, m, s in zip(model.coef, x, model.mu, model.sd, strict=True)
    )
    return 1.0 / (1.0 + math.exp(-z))


def reading_of(
    drawing: Drawing,
    family: str,
    answer: int,
    probs: Sequence[float] | None = None,
    arbiter_p: float | None = None,
) -> GateReading:
    """The reading of one answered family from the stored drawing: the double-check readers'
    counts (DOUBLE_CHECK_READERS), the counted elements' scores, the plans and the rooms. L1's
    probabilities and the arbiter's P come from the drawing's `count_arbiter` (stored when the
    arbiter ran) unless the caller passes them."""
    stored = count_arbiter_reading(drawing, family)
    if stored is not None:
        probs = stored.probs if probs is None else probs
        arbiter_p = stored.p if arbiter_p is None else arbiter_p
    readers = (
        {name: len(seen) for name, seen in reader_elements(drawing, family).items()}
        if family in READER_FAMILIES
        else {}
    )
    scores = tuple(
        float(v) if isinstance(v := e.attrs.get("score"), int | float) and not isinstance(v, bool)
        else None
        for e in (counted_elements(drawing, family) if family in READER_FAMILIES else ())
    )  # fmt: skip
    rooms = None
    if family.startswith(ROOM):
        kind = family.removeprefix(ROOM)
        labelled = [bool((room.label or "").strip()) for room in drawing.rooms]
        mine = [room.type == kind for room in drawing.rooms]
        rooms = RoomCounts(
            sum(mine), sum(m and lab for m, lab in zip(mine, labelled, strict=True)),
            len(drawing.rooms), sum(labelled),
        )  # fmt: skip
    return GateReading(answer, probs, readers, scores, len(drawing.plans), arbiter_p, rooms)

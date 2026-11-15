"""The steps a reader reports in `Extracted.steps` (decision 0018): what it found, in counts and
words, the steps of an inner reader moved onto its caller's clock, and one call timed as a step
(`timed`: when it began after `began`, how long it ran, what its model calls cost on its thread and
how many of them got no answer, app/core/cost.py)."""

import time
from collections.abc import Callable, Iterable, Sequence
from typing import NamedTuple

from app.core import cost
from app.core.drawing.model import Element, ReadClass
from app.core.pipeline.model import Extracted, StepTrace
from app.core.wording import count

PLURALS = {"furniture": "furniture"}  # every other class takes an "s"


def found_of(
    elements: Iterable[Element],
    read: Sequence[ReadClass] | None = None,
    *,
    rooms: int | None = None,
    plans: int | None = None,
) -> dict[str, int]:
    """Counts by class of `elements` whose class was looked for (`read`; None: every class), then
    `room` and `plan` when given; a class looked for and not found is not listed."""
    found: dict[str, int] = {}
    for element in elements:
        if read is None or element.class_ in read:
            found[element.class_] = found.get(element.class_, 0) + 1
    if rooms is not None:
        found["room"] = rooms
    if plans is not None:
        found["plan"] = plans
    return found


def found_words(found: dict[str, int]) -> str:
    """ "31 doors, 12 windows, 4 rooms": the counts in words, largest first; "nothing found"."""
    if not found:
        return "nothing found"
    ranked = sorted(found.items(), key=lambda item: (-item[1], item[0]))
    return ", ".join(count(n, kind.replace("_", " "), PLURALS.get(kind)) for kind, n in ranked)


def shifted(steps: Iterable[StepTrace], by_ms: float) -> tuple[StepTrace, ...]:
    """`steps` with `at_ms` moved `by_ms` later: an inner reader's steps on its caller's clock."""
    return tuple(step.model_copy(update={"at_ms": step.at_ms + by_ms}) for step in steps)


class Span(NamedTuple):
    at_ms: float  # when the call began, ms after `began`
    ms: float
    cost_usd: float  # its model calls on this thread
    faults: int  # its model calls that got no answer


def timed[T](call: Callable[[], T], began: float) -> tuple[T, Span]:
    """`call()`'s result and its span; `began` is the caller's `time.perf_counter()` at its own
    start. An error of `call` is raised as it is."""
    paid, failed = cost.mark(), cost.faults()
    started = time.perf_counter()
    found = call()
    ended = time.perf_counter()
    span = Span(
        at_ms=max(0.0, (started - began) * 1000),
        ms=(ended - started) * 1000,
        cost_usd=cost.since(paid),
        faults=cost.faults_since(failed),
    )
    return found, span


def without_steps(found: Extracted) -> Extracted:
    """What was read, without how: two readings of a sheet are the same when this is."""
    return found.model_copy(update={"steps": ()})

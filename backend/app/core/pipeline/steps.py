"""The steps a reader reports in `Extracted.steps` (decision 0018): what it found, in counts and
words, and one call timed as a step (`timed`: when it began, how long it ran, what its model calls
cost on its thread and how many of them got no answer, app/core/cost.py).

Inside `Extracted.steps`, `at_ms` is on one clock for every reader, `now_ms()` (the process's
`time.perf_counter`), so a wrapper passes its inner reader's steps on as they are, whatever
waiting (a queue, a lock) came before them; ingest's `TimedExtractor` makes them relative to the
extract stage."""

import time
from collections.abc import Callable, Iterable, Sequence
from contextvars import ContextVar, Token
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
    """`steps` with `at_ms` moved `by_ms` later (earlier when negative, never below 0)."""
    return tuple(step.model_copy(update={"at_ms": max(0.0, step.at_ms + by_ms)}) for step in steps)


def now_ms() -> float:
    """The steps' clock, in ms."""
    return time.perf_counter() * 1000


class Span(NamedTuple):
    at_ms: float  # when the call began, on `now_ms()`'s clock
    ms: float
    cost_usd: float  # its model calls on this thread
    faults: int  # its model calls that got no answer


def timed[T](call: Callable[[], T]) -> tuple[T, Span]:
    """`call()`'s result and its span. An error of `call` is raised as it is."""
    paid, failed = cost.mark(), cost.faults()
    started = now_ms()
    found = call()
    ended = now_ms()
    span = Span(
        at_ms=started,
        ms=ended - started,
        cost_usd=cost.since(paid),
        faults=cost.faults_since(failed),
    )
    return found, span


def without_steps(found: Extracted) -> Extracted:
    """What was read, without how: two readings of a sheet are the same when this is."""
    return found.model_copy(update={"steps": ()})


# Who hears that a step starts (ingest's live `FileStatus.step`); None: nobody. A reader that runs
# a step on a thread of its own runs it in a copy of its context (`contextvars.copy_context`).
_listener: ContextVar[Callable[[str, str], None] | None] = ContextVar("step_listener", default=None)


def starting(step_id: str, label: str) -> None:
    """Says that the step `step_id` (`label`) starts now, to whoever listens."""
    heard = _listener.get()
    if heard is not None:
        heard(step_id, label)


class listening:  # noqa: N801 (used as a function: `with listening(...)`)
    """`heard(step_id, label)` is called for every step that starts inside the block."""

    def __init__(self, heard: Callable[[str, str], None]) -> None:
        self._heard = heard
        self._token: Token[Callable[[str, str], None] | None] | None = None

    def __enter__(self) -> None:
        self._token = _listener.set(self._heard)

    def __exit__(self, *_: object) -> None:
        if self._token is not None:
            _listener.reset(self._token)


def nested(prefix: str) -> listening:
    """Inside the block, a step that starts is heard as `<prefix>/<its id>`: a step inside the
    step `prefix` (a raster source's own steps)."""
    outer = _listener.get()

    def heard(step_id: str, label: str) -> None:
        if outer is not None:
            outer(f"{prefix}/{step_id}", label)

    return listening(heard)

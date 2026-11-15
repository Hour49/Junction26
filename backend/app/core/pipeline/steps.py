"""The steps a reader reports in `Extracted.steps` (decision 0018): what it found, in counts and
words, and the steps of an inner reader moved onto its caller's clock."""

from collections.abc import Iterable, Sequence

from app.core.drawing.model import Element, ReadClass
from app.core.pipeline.model import StepTrace
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

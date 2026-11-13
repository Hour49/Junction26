"""Stage 8: compare what the extraction measured with an independent second method.

Every quantity both methods measured becomes a `Conflict` entry of the drawing model, `agree` or
`conflict`, with both values kept for a person to settle; nothing is resolved silently.

Hello world: the first side is the element count per class. Room and storey counts, printed
labels against drawn geometry, and resolution rules come with the first real second method.
"""

from collections import Counter
from collections.abc import Iterable

from app.core.drawing.model import (
    ELEMENT_CLASSES,
    Conflict,
    ConflictQuantity,
    MeasuredValue,
    Subject,
)
from app.core.pipeline.model import Extracted, Measurement

COUNTS: frozenset[ConflictQuantity] = frozenset({"room_count", "element_count", "storey_count"})
TOLERANCE = 0.02  # relative, for everything that is not a count (the dataset's 2% rule)


def element_counts(found: Extracted) -> list[Measurement]:
    """What the extraction counted, per element class (0 for a class it lists nothing of)."""
    numbers = Counter(element.class_ for element in found.elements)
    return [
        Measurement(
            quantity="element_count",
            subject=Subject(kind="class", ref=name),
            value=MeasuredValue(value=numbers[name], unit="count", method=found.method),
        )
        for name in ELEMENT_CLASSES
    ]


def second_count(first: Iterable[Measurement], second: Iterable[Measurement]) -> list[Conflict]:
    """One entry per measurement of `second` that `first` also has (same quantity and subject),
    in the order of `second`, with ids c1, c2..."""
    firsts = {(one.quantity, one.subject): one for one in first}
    entries: list[Conflict] = []
    for again in second:
        one = firsts.get((again.quantity, again.subject))
        if one is None:
            continue
        if one.value.method == again.value.method:
            raise ValueError(
                f"{again.quantity} of {again.subject.ref or 'the sheet'}: both values come from "
                f"{again.value.method!r}, so the second is not an independent count"
            )
        tolerance = 0.0 if again.quantity in COUNTS else TOLERANCE
        a, b = one.value.value, again.value.value
        differ = abs(a - b) > tolerance * max(abs(a), abs(b))
        entries.append(
            Conflict(
                id=f"c{len(entries) + 1}",
                quantity=again.quantity,
                subject=again.subject,
                status="conflict" if differ else "agree",
                tolerance=tolerance,
                values=(one.value, again.value),
            )
        )
    return entries

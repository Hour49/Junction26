"""Stage 8: compare what the extraction measured with an independent second method.

Every quantity that two methods measured becomes a `Conflict` entry of the drawing model, `agree`
or `conflict`, with every value kept for a person to see. Where docs/PIPELINE.md section 2 has a
rule for the pair of methods, the entry names the value that rule reports, and the drawing carries
that value. Where it has none, a disagreement stays unresolved: nothing is settled silently.

The extraction's own side is the element count per class and each room's area, which an extractor
measures as the room's outline at the sheet's scale. The second counter (the `SecondCounter` port)
brings the other readings. It may bring two of its own for one quantity: the scale as the sheet
prints it and as its scale bar measures it.
"""

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from typing import NamedTuple

from app.core.drawing.model import (
    ELEMENT_CLASSES,
    Conflict,
    ConflictQuantity,
    MeasuredValue,
    MeasureMethod,
    Resolution,
    Room,
    Subject,
)
from app.core.pipeline.model import Extracted, Measurement

COUNTS: frozenset[ConflictQuantity] = frozenset({"room_count", "element_count", "storey_count"})
TOLERANCE = 0.02  # relative, for everything that is not a count (the dataset's 2% rule)
AGREE = "both methods agree"


class Rule(NamedTuple):
    """Whose value is reported when two methods measured one quantity."""

    prefer: MeasureMethod
    text: str


# docs/PIPELINE.md section 2. A pair of methods that is not here has no rule.
RULES: Mapping[tuple[ConflictQuantity, frozenset[MeasureMethod]], Rule] = {
    ("room_area", frozenset({"printed_label", "polygon_x_scale"})): Rule(
        "printed_label", "the printed label over the outline at the sheet's scale"
    ),
    ("scale", frozenset({"scale_text", "scale_bar"})): Rule(
        "scale_bar", "the measured scale bar over the scale text"
    ),
}


def differ(a: float, b: float, tolerance: float) -> bool:
    """Whether two values of one quantity are further apart than `tolerance`, which is relative
    to the larger of the two."""
    return abs(a - b) > tolerance * max(abs(a), abs(b))


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


def room_areas(found: Extracted) -> list[Measurement]:
    """Each room's area as the extraction measured it: its outline at the sheet's scale."""
    return [
        Measurement(
            quantity="room_area",
            subject=Subject(kind="room", ref=room.id),
            value=MeasuredValue(
                value=room.area_m2,
                unit="m2",
                method="polygon_x_scale",
                page=room.page,
                box=room.box,
            ),
        )
        for room in found.rooms
        if room.area_m2 is not None and room.polygon is not None
    ]


def measured(found: Extracted) -> list[Measurement]:
    """Everything the extraction measured that a second method can be compared with."""
    return [*element_counts(found), *room_areas(found)]


def second_count(first: Iterable[Measurement], second: Iterable[Measurement]) -> list[Conflict]:
    """One entry per quantity and subject that `second` measured and that has values from two or
    more methods: the value of `first` when it has one, then the values of `second`. The entries
    are in the order of `second`, with ids c1, c2..."""
    firsts = {(one.quantity, one.subject): one.value for one in first}
    groups: dict[tuple[ConflictQuantity, Subject], list[MeasuredValue]] = {}
    for again in second:
        key = (again.quantity, again.subject)
        values = groups.setdefault(key, [firsts[key]] if key in firsts else [])
        if any(value.method == again.value.method for value in values):
            raise ValueError(
                f"{again.quantity} of {again.subject.ref or 'the sheet'}: two values come from "
                f"{again.value.method!r}, so the second is not an independent count"
            )
        values.append(again.value)
    entries: list[Conflict] = []
    for (quantity, subject), values in groups.items():
        if len(values) < 2:
            continue
        tolerance = 0.0 if quantity in COUNTS else TOLERANCE
        numbers = [value.value for value in values]
        apart = differ(min(numbers), max(numbers), tolerance)
        entries.append(
            Conflict(
                id=f"c{len(entries) + 1}",
                quantity=quantity,
                subject=subject,
                status="conflict" if apart else "agree",
                tolerance=tolerance,
                values=tuple(values),
                resolution=_resolution(quantity, values, apart),
            )
        )
    return entries


def _resolution(
    quantity: ConflictQuantity, values: Sequence[MeasuredValue], apart: bool
) -> Resolution | None:
    """The value to report: the preferred method's when a rule names one, else the first value
    when they agree, else nothing."""
    rule = RULES.get((quantity, frozenset(value.method for value in values)))
    if rule is None:
        return None if apart else Resolution(rule=AGREE, value=values[0].value)
    preferred = next(value.value for value in values if value.method == rule.prefer)
    return Resolution(rule=rule.text if apart else AGREE, value=preferred)


def resolved_rooms(rooms: Sequence[Room], conflicts: Iterable[Conflict]) -> tuple[Room, ...]:
    """The rooms, each disputed area replaced by the value its conflict resolves to, so the
    drawing never carries an area that its own conflict entry rejects. A room whose values agree
    keeps the measured area."""
    settled = {
        entry.subject.ref: entry.resolution.value
        for entry in conflicts
        if entry.quantity == "room_area"
        and entry.status == "conflict"
        and entry.resolution is not None
    }
    return tuple(
        room.model_copy(update={"area_m2": settled[room.id]}) if room.id in settled else room
        for room in rooms
    )

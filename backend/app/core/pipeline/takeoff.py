"""Stage 10: the takeoff, every quantity the drawing model can answer, with its marks and rule.

Each quantity has a key from `quantity_key`: what is measured (count, area, length, volume), of
what (an element class, `room`, `room:<type>`, `apartment`, `plan`, a combined count of
rules.COMBINED) and the filters that pick the items (a room label, one room's name or number, an
apartment, a storey). A plain count keeps its COUNT_KEYS key ("door", "room:sauna", "plan"). The
question parser builds the same key from a question, so answering stays a lookup.

Everything is computed for the whole sheet and again for each storey the items name. A quantity
the drawing can't give (a room without an area, a wall without its length, a name two rooms
share) has no key, so the answer is a refusal rather than a wrong number.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence

from app.core.drawing.model import (
    COUNT_KEYS,
    PLAN,
    Attr,
    Drawing,
    Element,
    Mark,
    Room,
)
from app.core.pipeline.model import Counted, CountingRule, Measure, Quantity, QuantityUnit
from app.core.pipeline.rules import (
    APARTMENT_AREA,
    AS_GIVEN,
    COMBINED,
    EACH_ONCE,
    ELEMENT_QUANTITY,
    INDOOR_TOTAL,
    MEASURED,
    ROOM_AREA,
    ROOM_LONG_NAME,
    ROOM_NAME,
    ROOM_NUMBER,
    ROOMS_TOTAL,
    apply_rules,
    combine_totals,
)

UNITS: Mapping[Measure, QuantityUnit] = {
    "count": "count",
    "area": "m2",
    "length": "m",
    "volume": "m3",
}


def normalised(value: str) -> str:
    """How a name, label or storey is compared: case and runs of spaces don't matter."""
    return " ".join(value.split()).casefold()


def quantity_key(
    measure: Measure,
    subject: str,
    *,
    label: str | None = None,
    name: str | None = None,
    apartment: str | None = None,
    storey: str | None = None,
    indoor: bool = False,
    model: bool = False,
) -> str:
    """The takeoff key of a quantity. `model`: the whole building model rather than this sheet,
    which a sheet's takeoff never has."""
    parts = [subject if measure == "count" else f"{measure}:{subject}"]
    for field, value in (("label", label), ("name", name), ("apartment", apartment)):
        if value is not None:
            parts.append(f"{field}={normalised(value)}")
    if storey is not None:
        parts.append(f"storey={normalised(storey)}")
    if indoor:
        parts.append("indoor")
    if model:
        parts.append("model")
    return "|".join(parts)


def take_off(drawing: Drawing, counted: Mapping[str, Counted]) -> dict[str, Quantity]:
    """A drawing that only states totals (`counts`) gives those and the combined counts they
    make, without marks; a quantity it does not state is unknown. Otherwise `counted` (stage 9
    on the whole sheet) gives the counts, and the rooms, apartments and element quantities give
    the rest, for the sheet and for each storey."""
    if drawing.counts is not None:
        rules = {rule.key: rule.rule for rule in COMBINED}
        stated = {**drawing.counts, **combine_totals(drawing.counts)}
        return {
            key: Quantity(
                key=key, value=value, unit="count", marks=(), rule=rules.get(key, AS_GIVEN).id
            )
            for key, value in stated.items()
        }
    found: dict[str, Quantity] = {}
    _add_scope(found, counted, drawing.elements, drawing.rooms, storey=None)
    _add_apartments(found, drawing)
    plans = {plan.id: plan.storey for plan in drawing.plans}
    elements_by: dict[str, list[Element]] = defaultdict(list)
    rooms_by: dict[str, list[Room]] = defaultdict(list)
    for element in drawing.elements:
        if (storey := _storey(element.attrs, element.plan, plans)) is not None:
            elements_by[storey].append(element)
    for room in drawing.rooms:
        if (storey := _storey(room.attrs, room.plan, plans)) is not None:
            rooms_by[storey].append(room)
    for storey in sorted({*elements_by, *rooms_by}):
        elements, rooms = elements_by[storey], rooms_by[storey]
        on_storey = apply_rules(_listed(elements, rooms))
        _add_scope(found, on_storey, elements, rooms, storey=storey)
    return found


def known_quantities(drawing: Drawing) -> dict[str, Quantity]:
    """Stages 9 and 10 on a stored drawing model: what answering looks a query up in."""
    return take_off(drawing, apply_rules(drawing.marks_by_quantity()))


def _storey(attrs: Mapping[str, Attr], plan: str | None, plans: Mapping[str, object]) -> str | None:
    """The storey an item is on: its own `storey` attr (an IFC object's containment), else the
    storey of the plan it is drawn in."""
    own = attrs.get("storey")
    if isinstance(own, str | int) and not isinstance(own, bool):
        return str(own)
    on_plan = plans.get(plan) if plan is not None else None
    return None if on_plan is None else str(on_plan)


def _mark(item: Element | Room) -> Mark:
    return Mark(page=item.page, box=item.box)


def _listed(elements: Iterable[Element], rooms: Iterable[Room]) -> dict[str, tuple[Mark, ...]]:
    """Drawing.marks_by_quantity() for some of the drawing's items; plans are per sheet only."""
    marks: dict[str, list[Mark]] = {key: [] for key in COUNT_KEYS if key != PLAN}
    for element in elements:
        marks[element.class_].append(_mark(element))
    for room in rooms:
        marks[f"room:{room.type}"].append(_mark(room))
    return {key: tuple(found) for key, found in marks.items()}


def _put(
    found: dict[str, Quantity],
    key: str,
    measure: Measure,
    value: float,
    marks: Sequence[Mark],
    rule: CountingRule,
) -> None:
    found[key] = Quantity(
        key=key,
        value=value if measure == "count" else round(value, 3),
        unit=UNITS[measure],
        marks=tuple(marks),
        rule=rule.id,
    )


def _area_sum(
    found: dict[str, Quantity], key: str, rooms: Sequence[Room], rule: CountingRule
) -> None:
    """The total net area of `rooms`; no key when there are none or one has no area."""
    areas = [room.area_m2 for room in rooms]
    if rooms and all(area is not None for area in areas):
        total = sum(area for area in areas if area is not None)
        _put(found, key, "area", total, [_mark(room) for room in rooms], rule)


def _room_names(room: Room) -> set[str]:
    attrs = {k: v for k, v in room.attrs.items() if isinstance(v, str) and v}
    number, name, long = attrs.get(ROOM_NUMBER), attrs.get(ROOM_NAME), attrs.get(ROOM_LONG_NAME)
    names = {value for value in (room.label, number, name, long) if value}
    if long and name:
        names.add(f"{long} ({name})")
    if number and name:
        names.add(f"{name} ({number})")
    if number and long:
        names.add(f"{long} ({number})")
    return {normalised(value) for value in names}


def _add_scope(
    found: dict[str, Quantity],
    counted: Mapping[str, Counted],
    elements: Sequence[Element],
    rooms: Sequence[Room],
    storey: str | None,
) -> None:
    """Every quantity of one set of items: the whole sheet (`storey` None) or one storey."""
    for key, chosen in counted.items():
        _put(
            found,
            quantity_key("count", key, storey=storey),
            "count",
            len(chosen.marks),
            chosen.marks,
            chosen.rule,
        )
    _put(
        found,
        quantity_key("count", "room", storey=storey),
        "count",
        len(rooms),
        [_mark(room) for room in rooms],
        EACH_ONCE,
    )
    _area_sum(found, quantity_key("area", "room", storey=storey), rooms, ROOMS_TOTAL)
    indoor = [room for room in rooms if not room.outdoor]
    _area_sum(found, quantity_key("area", "room", storey=storey, indoor=True), indoor, INDOOR_TOTAL)
    labelled: dict[str, list[Room]] = defaultdict(list)
    named: dict[str, list[Room]] = defaultdict(list)
    for room in rooms:
        if room.label:
            labelled[normalised(room.label)].append(room)
        for name in _room_names(room):
            named[name].append(room)
    for label, same in labelled.items():
        key = quantity_key("count", "room", label=label, storey=storey)
        _put(found, key, "count", len(same), [_mark(room) for room in same], EACH_ONCE)
        _area_sum(
            found, quantity_key("area", "room", label=label, storey=storey), same, ROOMS_TOTAL
        )
    for name, same in named.items():
        if len(same) == 1:  # a name two rooms share names neither
            key = quantity_key("area", "room", name=name, storey=storey)
            _area_sum(found, key, same, ROOM_AREA)
    for (cls, measure), attr in MEASURED.items():
        of_class = [element for element in elements if element.class_ == cls]
        values = [element.attrs.get(attr) for element in of_class]
        if of_class and all(isinstance(v, int | float) and v is not True for v in values):
            total = sum(float(v) for v in values if isinstance(v, int | float))
            key = quantity_key(measure, cls, storey=storey)
            _put(found, key, measure, total, [_mark(e) for e in of_class], ELEMENT_QUANTITY)


def _add_apartments(found: dict[str, Quantity], drawing: Drawing) -> None:
    apartments = drawing.apartments
    rooms_of: dict[str, list[Room]] = defaultdict(list)
    for room in drawing.rooms:
        if room.apartment is not None:
            rooms_of[room.apartment].append(room)
    _put(
        found,
        quantity_key("count", "apartment"),
        "count",
        len(apartments),
        [],  # an apartment has no box of its own in the drawing model
        EACH_ONCE,
    )
    for apartment in apartments:
        if apartment.label is None:
            continue
        key = quantity_key("area", "apartment", apartment=apartment.label)
        kept = [r for r in rooms_of[apartment.id] if not r.outdoor and r.type != "shaft"]
        if apartment.area_m2 is not None:
            marks = [_mark(room) for room in kept]
            _put(found, key, "area", apartment.area_m2, marks, APARTMENT_AREA)
        else:
            _area_sum(found, key, kept, APARTMENT_AREA)

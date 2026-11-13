"""Stage 10: the takeoff, every quantity the drawing model can answer, with its marks and rule.

Each quantity has a key from `quantity_key`: what is measured (count, area, length, volume), of
what (an element class, `room`, `room:<type>`, `apartment`, `plan`, a combined count of
rules.COMBINED) and the filters that pick the items (a room label, one room's name or number, an
apartment, a storey). A plain count keeps its COUNT_KEYS key ("door", "room:sauna", "plan"). The
question parser builds the same key from a question, so answering stays a lookup.

Everything is computed for the whole sheet and again for each storey the items name. A quantity
the drawing can't give (a room without an area, a wall without its length, a name two rooms
share) has no key, so the answer is a refusal rather than a wrong number.

A quantity that the drawing's stage-8 entry says two methods measured differently carries both
values (`Quantity.conflict`), and its value is the one the entry's rule picked. Which stage made
the entry does not matter.
"""

import math
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence

from app.core.drawing.model import (
    COUNT_KEYS,
    PLAN,
    Attr,
    Conflict,
    Drawing,
    Element,
    Mark,
    Page,
    Resolution,
    Room,
    Scale,
)
from app.core.pipeline.model import (
    Counted,
    CountingRule,
    Measure,
    Quantity,
    QuantityConflict,
    QuantityUnit,
)
from app.core.pipeline.rules import (
    APARTMENT_AREA,
    AS_GIVEN,
    COMBINED,
    EACH_ONCE,
    ELEMENT_QUANTITY,
    INDOOR_TOTAL,
    LARGEST_ROOM,
    MEASURED,
    ROOM_AREA,
    ROOM_NAMES,
    ROOM_NUMBERS,
    ROOM_SIDE,
    ROOMS_TOTAL,
    SHEET_DWELLING,
    apply_rules,
    combine_totals,
)
from app.core.pipeline.second_count import differ

# An element sum an estimated scale makes an estimate (a volume is the model's, not the sheet's).
SCALED_MEASURES: tuple[Measure, ...] = ("area", "length")
# Two sums of the same rooms: equal up to float rounding. A room set's areas differ by whole rooms,
# not by measurement noise, so the 2% tolerance of two measurements does not apply to them.
SAME = 1e-9
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
    largest: bool = False,
) -> str:
    """The takeoff key of a quantity. `model`: the whole building model rather than this sheet,
    which a sheet's takeoff never has. `largest`: the largest one of the items, not their sum."""
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
    if largest:
        parts.append("largest")
    return "|".join(parts)


def take_off(drawing: Drawing, counted: Mapping[str, Counted]) -> dict[str, Quantity]:
    """A drawing that only states totals (`counts`) gives those and the combined counts they
    make, without marks; a quantity it does not state is unknown. Otherwise `counted` (stage 9
    on the whole sheet) gives the counts, and the rooms, apartments and element quantities give
    the rest, for the sheet and for each storey."""
    if drawing.counts is not None:
        rules = {rule.key: rule.rule for rule in COMBINED}
        stated = {**drawing.counts, **combine_totals(drawing.counts)}
        totals = {
            key: Quantity(
                key=key, value=value, unit="count", marks=(), rule=rules.get(key, AS_GIVEN).id
            )
            for key, value in stated.items()
        }
        return _read_only(_with_conflicts(totals, drawing), drawing.read)
    found: dict[str, Quantity] = {}
    scale = scale_estimate(drawing.scale)
    _add_scope(found, counted, drawing.elements, drawing.rooms, storey=None, scale=scale)
    _add_apartments(found, drawing, scale)
    _add_room_sides(found, drawing, scale)
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
        _add_scope(found, on_storey, elements, rooms, storey=storey, scale=scale)
    return _read_only(_with_conflicts(found, drawing), drawing.read)


def _with_conflicts(found: dict[str, Quantity], drawing: Drawing) -> dict[str, Quantity]:
    """Each quantity a `conflict` entry of the drawing is about, with the entry's values and its
    resolved value. `agree` entries change nothing. A sheet-wide entry (an element class, the
    sheet's rooms) is about the sheet and, when its plans show one storey, that storey. An entry
    is only attached to a quantity whose own value is one of the entry's values, so a key that
    measures something else keeps its value."""
    plans = {plan.id: plan.storey for plan in drawing.plans}
    storeys = {str(storey) for storey in plans.values() if storey is not None}
    storey = next(iter(storeys)) if len(storeys) == 1 else None
    out = dict(found)
    for entry in drawing.conflicts or ():
        if entry.status != "conflict":
            continue
        disputed = QuantityConflict(
            values=entry.values, resolution=entry.resolution, note=entry.note
        )
        for key in _conflict_keys(entry, drawing, storey, plans):
            _attach(out, key, disputed, entry.tolerance)
        if storey is not None:
            for key, derived in _room_set_areas(entry, drawing.rooms, storey, plans):
                _attach(out, key, derived, SAME)
    return out


def _conflict_keys(
    entry: Conflict, drawing: Drawing, storey: str | None, plans: Mapping[str, object]
) -> list[str]:
    """The takeoff keys a conflict entry is about (the sheet's and its one storey's)."""
    scopes = [None, storey] if storey is not None else [None]
    ref = entry.subject.ref
    match entry.quantity, entry.subject.kind:
        case "element_count", "class" if ref is not None:
            return [quantity_key("count", ref, storey=scope) for scope in scopes]
        case "room_count", "sheet":
            return [quantity_key("count", "room", storey=scope) for scope in scopes]
        case "room_area", "room":
            keys: list[str] = []
            for room in (room for room in drawing.rooms if room.id == ref):
                own = _storey(room.attrs, room.plan, plans)
                for name in _room_names(room):
                    keys += [quantity_key("area", "room", name=name, storey=s) for s in {None, own}]
            return keys
        case "apartment_area", "apartment":
            labels = [a.label for a in drawing.apartments if a.id == ref and a.label is not None]
            return [quantity_key("area", "apartment", apartment=label) for label in labels]
        case _:
            return []


def _room_set_areas(
    entry: Conflict, rooms: Sequence[Room], storey: str, plans: Mapping[str, object]
) -> list[tuple[str, QuantityConflict]]:
    """A sheet's room count disputed between the rooms it draws and the rooms of its storey (the
    two values are those two numbers) disputes the storey's area totals the same way: each
    method's value becomes the area of its set of rooms, and the rule that picked a count picks
    that count's area. Any difference counts: it is whole rooms, not measurement noise."""
    if entry.quantity != "room_count" or entry.subject.kind != "sheet" or len(entry.values) != 2:
        return []
    drawn = list(rooms)
    own = [room for room in drawn if _storey(room.attrs, room.plan, plans) == storey]
    sets = {len(drawn): drawn, len(own): own}
    if len(sets) != 2 or {value.value for value in entry.values} != set(sets):
        return []
    how = (
        f"values from the room count's two sets of rooms ({len(drawn)} drawn on the sheet, "
        f"{len(own)} on storey {storey}), each one's net areas summed"
    )
    found: list[tuple[str, QuantityConflict]] = []
    for indoor in (False, True):
        totals: dict[float, float] = {}
        for count, chosen in sets.items():
            areas = [room.area_m2 for room in chosen if not (indoor and room.outdoor)]
            if any(area is None for area in areas):
                return found
            totals[count] = round(sum(area for area in areas if area is not None), 3)
        if not differ(min(totals.values()), max(totals.values()), SAME):
            continue  # the rooms only one set has add no area here
        values = tuple(
            value.model_copy(update={"value": totals[value.value], "unit": "m2"})
            for value in entry.values
        )
        resolution = None
        if entry.resolution is not None and entry.resolution.value in totals:
            picked = totals[entry.resolution.value]
            resolution = Resolution(rule=entry.resolution.rule, value=picked)
        disputed = QuantityConflict(
            values=values, resolution=resolution, note=entry.note, derived=how
        )
        for scope in (None, storey):
            found.append((quantity_key("area", "room", storey=scope, indoor=indoor), disputed))
    return found


def _attach(
    found: dict[str, Quantity], key: str, disputed: QuantityConflict, tolerance: float
) -> None:
    """`disputed` on the quantity at `key`, whose value becomes the resolved one; its marks become
    the resolved value's box when that is not the value the takeoff counted."""
    quantity = found.get(key)
    if quantity is None or quantity.conflict is not None:
        return
    if all(differ(quantity.value, value.value, tolerance) for value in disputed.values):
        return
    update: dict[str, object] = {"conflict": disputed}
    if (resolution := disputed.resolution) is not None and differ(
        quantity.value, resolution.value, tolerance
    ):
        chosen = next((v for v in disputed.values if v.value == resolution.value), None)
        box = (
            ()
            if chosen is None or chosen.page is None or chosen.box is None
            else (Mark(page=chosen.page, box=chosen.box),)
        )
        update["value"] = round(resolution.value) if quantity.unit == "count" else resolution.value
        update["marks"] = box
    found[key] = quantity.model_copy(update=update)


def _read_only(found: dict[str, Quantity], read: Sequence[str] | None) -> dict[str, Quantity]:
    """The quantities whose items were all looked for (`Drawing.read`; None: everything). A
    count of a class the extraction did not read is unknown, not 0, so it has no key. An empty
    `read` means nothing was read at all, so plans and apartments, which need no class, have no
    key either."""
    if read is None:
        return found
    if not read:
        return {}
    looked_for = set(read)
    return {key: quantity for key, quantity in found.items() if _reads(key) <= looked_for}


def _reads(key: str) -> set[str]:
    """What a takeoff key needs read: its element class, "room" for room quantities, every part
    of a combined count; nothing for plans and apartments."""
    subject = key.split("|", 1)[0]
    measure, _, rest = subject.partition(":")
    if measure in UNITS and rest:
        subject = rest
    parts = {rule.key: rule.parts for rule in COMBINED}.get(subject, (subject,))
    needed: set[str] = set()
    for part in parts:
        if part == "room" or part.startswith("room:"):
            needed.add("room")
        elif part not in (PLAN, "apartment"):
            needed.add(part)
    return needed


def rooms_estimate(rooms: Sequence[Room], scale: str | None) -> str | None:
    """What a sum of room areas rests on, when that is an estimate: the rooms whose own area is
    estimated; else the sheet's estimated scale, unless every room's area is printed (exact)."""
    estimated = [room for room in rooms if room.area_status == "estimated"]
    if estimated:
        how = sorted({room.area_source or "an unnamed method" for room in estimated})
        spread = max((room.area_uncertainty or 0.0 for room in estimated), default=0.0)
        worst = f", uncertainty up to {spread:g}" if spread else ""
        return f"{len(estimated)} of {len(rooms)} room areas estimated ({', '.join(how)}{worst})"
    if rooms and all(room.area_status == "exact" for room in rooms):
        return None
    return scale


def scale_estimate(scale: Scale) -> str | None:
    """What an area or length on a sheet with this scale rests on, when that is an estimate."""
    match scale.status:
        case "estimated":
            how = f" ({scale.source})" if scale.source else ""
            spread = f", uncertainty {scale.uncertainty:g}" if scale.uncertainty else ""
            return f"an estimated scale{how}{spread}"
        case "not_to_scale":
            return "a sheet marked not to scale, so its scale is a guess"
        case _:
            return None


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
    estimate: str | None = None,
) -> None:
    found[key] = Quantity(
        key=key,
        value=value if measure == "count" else round(value, 3),
        unit=UNITS[measure],
        marks=tuple(marks),
        rule=rule.id,
        estimate=estimate,
    )


def _area_sum(
    found: dict[str, Quantity],
    key: str,
    rooms: Sequence[Room],
    rule: CountingRule,
    scale: str | None,
) -> None:
    """The total net area of `rooms`; no key when there are none or one has no area. `scale`:
    what the sheet's scale makes an estimate of (scale_estimate)."""
    areas = [room.area_m2 for room in rooms]
    if rooms and all(area is not None for area in areas):
        total = sum(area for area in areas if area is not None)
        marks = [_mark(room) for room in rooms]
        _put(found, key, "area", total, marks, rule, rooms_estimate(rooms, scale))


def _room_names(room: Room) -> set[str]:
    def texts(keys: Iterable[str]) -> set[str]:
        return {value for key in keys if isinstance(value := room.attrs.get(key), str) and value}

    numbers, names = texts(ROOM_NUMBERS), texts(ROOM_NAMES)
    found = {*numbers, *names, *([room.label] if room.label else [])}
    found |= {f"{name} ({number})" for name in names for number in numbers if name != number}
    return {normalised(value) for value in found}


def _add_scope(
    found: dict[str, Quantity],
    counted: Mapping[str, Counted],
    elements: Sequence[Element],
    rooms: Sequence[Room],
    storey: str | None,
    scale: str | None,
) -> None:
    """Every quantity of one set of items: the whole sheet (`storey` None) or one storey.
    `scale`: what the sheet's scale makes an estimate of (scale_estimate)."""
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
    _area_sum(found, quantity_key("area", "room", storey=storey), rooms, ROOMS_TOTAL, scale)
    indoor = [room for room in rooms if not room.outdoor]
    key = quantity_key("area", "room", storey=storey, indoor=True)
    _area_sum(found, key, indoor, INDOOR_TOTAL, scale)
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
        key = quantity_key("area", "room", label=label, storey=storey)
        _area_sum(found, key, same, ROOMS_TOTAL, scale)
        key = quantity_key("area", "room", label=label, storey=storey, largest=True)
        _largest(found, key, same, scale)
    by_type: dict[str, list[Room]] = defaultdict(list)
    for room in rooms:
        by_type[room.type].append(room)
    for kind, same in by_type.items():
        _largest(
            found, quantity_key("area", f"room:{kind}", storey=storey, largest=True), same, scale
        )
    for name, same in named.items():
        if len(same) == 1:  # a name two rooms share names neither
            key = quantity_key("area", "room", name=name, storey=storey)
            _area_sum(found, key, same, ROOM_AREA, scale)
    for (cls, measure), attr in MEASURED.items():
        of_class = [element for element in elements if element.class_ == cls]
        values = [element.attrs.get(attr) for element in of_class]
        if of_class and all(isinstance(v, int | float) and v is not True for v in values):
            total = sum(float(v) for v in values if isinstance(v, int | float))
            key = quantity_key(measure, cls, storey=storey)
            marks = [_mark(e) for e in of_class]
            estimate = scale if measure in SCALED_MEASURES else None
            _put(found, key, measure, total, marks, ELEMENT_QUANTITY, estimate)


def _add_apartments(found: dict[str, Quantity], drawing: Drawing, scale: str | None) -> None:
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
        if apartment.label is not None:
            key = quantity_key("area", "apartment", apartment=apartment.label)
            _apartment_area(found, key, apartment.area_m2, rooms_of[apartment.id], scale)
    key = quantity_key("area", "apartment")  # "the apartment": the sheet's one dwelling
    if len(apartments) == 1:
        only = apartments[0]
        _apartment_area(found, key, only.area_m2, rooms_of[only.id], scale)
    elif not apartments:
        kept = [r for r in drawing.rooms if not r.outdoor and r.type != "shaft"]
        _area_sum(found, key, kept, SHEET_DWELLING, scale)


def _apartment_area(
    found: dict[str, Quantity],
    key: str,
    stated: float | None,
    rooms: Sequence[Room],
    scale: str | None,
) -> None:
    """The stated area, else the apartment's rooms that are neither outdoor nor shafts."""
    kept = [r for r in rooms if not r.outdoor and r.type != "shaft"]
    if stated is not None:
        _put(found, key, "area", stated, [_mark(room) for room in kept], APARTMENT_AREA)
    else:
        _area_sum(found, key, kept, APARTMENT_AREA, scale)


def _largest(
    found: dict[str, Quantity], key: str, rooms: Sequence[Room], scale: str | None
) -> None:
    """The largest of `rooms` by net area; no key when one has no area."""
    if rooms and all(room.area_m2 is not None for room in rooms):
        top = max(rooms, key=lambda room: room.area_m2 or 0.0)
        area = top.area_m2 or 0.0
        _put(found, key, "area", area, [_mark(top)], LARGEST_ROOM, rooms_estimate([top], scale))


def _add_room_sides(found: dict[str, Quantity], drawing: Drawing, scale: str | None) -> None:
    """The longer side of each rectangular room, by its name and, when it is the only room of
    its type, by the type. Needs the sheet's metres per drawing unit."""
    m_per_unit = drawing.scale.m_per_unit
    if m_per_unit is None:
        return
    pages = {page.page: page for page in drawing.pages}
    sides: dict[str, tuple[Room, float]] = {}
    for room in drawing.rooms:
        if room.polygon is not None and (side := _longer_side(room.polygon, pages[room.page])):
            sides[room.id] = (room, side * m_per_unit)
    named: dict[str, list[Room]] = defaultdict(list)
    by_type: dict[str, list[Room]] = defaultdict(list)
    for room in drawing.rooms:
        by_type[room.type].append(room)
        for name in _room_names(room):
            named[name].append(room)
    keys = [(quantity_key("length", "room", name=name), same) for name, same in named.items()]
    keys += [(quantity_key("length", f"room:{kind}"), same) for kind, same in by_type.items()]
    for key, same in keys:
        if len(same) == 1 and (found_side := sides.get(same[0].id)) is not None:
            room, side = found_side
            _put(found, key, "length", side, [_mark(room)], ROOM_SIDE, scale)


def _longer_side(polygon: Sequence[tuple[float, float]], page: Page) -> float | None:
    """The longer side, in drawing units, of an outline with four corners whose opposite sides
    are equal within 2% (a rectangle as drawn); None for any other shape."""
    if len(polygon) != 4:
        return None
    sides = [
        math.hypot((x1 - x0) * page.width, (y1 - y0) * page.height)
        for (x0, y0), (x1, y1) in zip(polygon, [*polygon[1:], polygon[0]], strict=True)
    ]
    if differ(sides[0], sides[2], 0.02) or differ(sides[1], sides[3], 0.02):
        return None
    return max(sides)

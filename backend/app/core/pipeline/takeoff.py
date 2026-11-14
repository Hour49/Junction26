"""Stage 10: the takeoff, every quantity the drawing model can answer, with its marks and rule.

Each quantity has a key from `quantity_key`: what is measured (count, area, length, volume), of
what (an element class, `room`, `room:<type>`, `apartment`, `plan`, a combined count of
rules.COMBINED) and the filters that pick the items (a room label, one room's name or number, an
apartment, a storey). A plain count keeps its COUNT_KEYS key ("door", "room:sauna", "plan"). The
question parser builds the same key from a question, so answering stays a lookup.

Everything is computed for the whole sheet and again for each storey the items name. A quantity
the drawing can't give (a room without an area, a wall without its length, a name two rooms
share) has no key, so the answer is a refusal rather than a wrong number.

A drawing with a building model behind it (`Drawing.model_objects`) also answers what the model
holds, drawn or not: counts in the model, and each storey's wall and slab sums and space areas,
which replace the sheet's own. What the sheet shows (a count "on the plan") stays the sheet's.

A quantity that the drawing's stage-8 entry says two methods measured differently carries both
values (`Quantity.conflict`), and its value is the one the entry's rule picked. Which stage made
the entry does not matter.
"""

import math
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence

from app.core.drawing.model import (
    COUNT_KEYS,
    ELEMENT_CLASSES,
    PLAN,
    Attr,
    Conflict,
    Drawing,
    Element,
    Mark,
    ModelObject,
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
    MODEL_COUNT,
    MODEL_MEASURED,
    MODEL_QUANTITY,
    MODEL_SPACES,
    ROOM_AREA,
    ROOM_NAMES,
    ROOM_NUMBERS,
    ROOM_SIDE,
    ROOMS_TOTAL,
    SHEET_DWELLING,
    apply_rules,
    combine_totals,
)
from app.core.pipeline.second_count import differ, of_its_plans_storey

# An element sum an estimated scale makes an estimate (a volume is the model's, not the sheet's).
SCALED_MEASURES: tuple[Measure, ...] = ("area", "length")
# Two sums of the same rooms: equal up to float rounding. A room set's areas differ by whole rooms,
# not by measurement noise, so the 2% tolerance of two measurements does not apply to them.
SAME = 1e-9
SPACE = "space"  # a building model's room (ModelObject.class_)
# Per count of a room set: each room's area (None: unknown) and whether it is outdoor.
RoomSets = dict[int, list[tuple[float | None, bool]]]
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
    if drawing.pages:
        _add_sheet(found, drawing, counted)
    if drawing.model_objects is not None:
        _add_model(found, drawing)
    return _read_only(_with_conflicts(found, drawing), drawing.read)


def _add_sheet(
    found: dict[str, Quantity], drawing: Drawing, counted: Mapping[str, Counted]
) -> None:
    """What the sheet draws, for the whole sheet and each storey. With a building model, the
    storeys' sums and space areas are the model's (`_add_model`), not the sheet's."""
    scale = scale_estimate(drawing.scale)
    sheet = _without_seen_through(counted, drawing)
    _add_scope(found, sheet, drawing.elements, drawing.rooms, storey=None, scale=scale)
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
        sums = drawing.model_objects is None
        _add_scope(found, on_storey, elements, rooms, storey=storey, scale=scale, sums=sums)


def _without_seen_through(counted: Mapping[str, Counted], drawing: Drawing) -> dict[str, Counted]:
    """The sheet's counts as stage 8 counts the sheet (`second_count.element_counts`): an
    element of another storey than its plan's, seen through the cut, is left out of the counts
    of its class and of the combined counts made of it, with the reason; its own storey's count
    has it. So on a sheet of one storey the sheet's count is that storey's, and a disagreement
    with the model is on both (R2-qa-1-1)."""
    shown = {plan.id: plan.storey for plan in drawing.plans}
    through: dict[str, Counter[Mark]] = defaultdict(Counter)
    why: dict[Mark, str] = {}
    for element in drawing.elements:
        if not of_its_plans_storey(element, shown):
            mark = _mark(element)
            through[element.class_][mark] += 1
            why[mark] = (
                f"on storey {element.attrs['storey']} in the building model, seen through the cut"
            )
    if not through:
        return dict(counted)
    parts = {rule.key: rule.parts for rule in COMBINED}
    out: dict[str, Counted] = {}
    for key, chosen in counted.items():
        left: Counter[Mark] = Counter()
        for part in parts.get(key, (key,)):
            left.update(through.get(part, {}))
        kept: list[Mark] = []
        dropped: list[tuple[Mark, str]] = []
        for mark in chosen.marks:
            if left[mark] > 0:
                left[mark] -= 1
                dropped.append((mark, why[mark]))
            else:
                kept.append(mark)
        out[key] = (
            chosen
            if not dropped
            else chosen.model_copy(
                update={"marks": tuple(kept), "excluded": (*chosen.excluded, *dropped)}
            )
        )
    return out


def _add_model(found: dict[str, Quantity], drawing: Drawing) -> None:
    """What the building model behind the drawing gives (`Drawing.model_objects`), over every
    object whether the sheet draws it or not: counts in the model (all of it and per storey),
    and per storey the sums of MODEL_MEASURED and the spaces' areas, total and by name. A
    drawing without a page (a question on the model file itself) shows nothing, so its plain
    counts, of the whole file and of each storey, are the model's too ("How many windows are
    there?" on a .ifc file). Only drawn objects have a mark."""
    objects = drawing.model_objects or ()
    drawn = {item.id: _mark(item) for item in (*drawing.elements, *drawing.rooms)}
    rooms = {room.id: room for room in drawing.rooms}
    scale = scale_estimate(drawing.scale)

    def marks(items: Iterable[ModelObject]) -> list[Mark]:
        return [drawn[item.element] for item in items if item.element in drawn]

    by_storey: dict[str, list[ModelObject]] = defaultdict(list)
    for item in objects:
        if item.storey is not None:
            by_storey[item.storey].append(item)
    scopes: list[tuple[str | None, Sequence[ModelObject]]] = [(None, objects)]
    scopes += sorted(by_storey.items())
    for storey, items in scopes:
        for cls in (*ELEMENT_CLASSES, SPACE):
            same = [item for item in items if item.class_ == cls]
            subject = "room" if cls == SPACE else cls
            for model in (True, False) if not drawing.pages else (True,):
                key = quantity_key("count", subject, storey=storey, model=model)
                _put(found, key, "count", len(same), marks(same), MODEL_COUNT)
    for storey, items in sorted(by_storey.items()):
        for (cls, measure), quantity in MODEL_MEASURED.items():
            same = [item for item in items if item.class_ == cls]
            values = [item.quantities.get(quantity) for item in same]
            if same and all(value is not None for value in values):
                total = sum(value for value in values if value is not None)
                key = quantity_key(measure, cls, storey=storey)
                _put(found, key, measure, total, marks(same), MODEL_QUANTITY)
        spaces = [item for item in items if item.class_ == SPACE]
        _add_model_spaces(found, storey, spaces, rooms, marks, scale)


def _add_model_spaces(
    found: dict[str, Quantity],
    storey: str,
    spaces: Sequence[ModelObject],
    rooms: Mapping[str, Room],
    marks: Callable[[Iterable[ModelObject]], list[Mark]],
    scale: str | None,
) -> None:
    """A storey's space areas: the total and each space by name. A space's area is the one the
    model states, else that of the room the sheet draws it as (measured at the sheet's scale);
    a space with neither leaves the total unknown."""

    def put(key: str, chosen: Sequence[ModelObject]) -> None:
        found_areas = [_space_area(space, rooms) for space in chosen]
        if chosen and all(value is not None for value, _ in found_areas):
            total = sum(value for value, _ in found_areas if value is not None)
            measured = [room for _, room in found_areas if room is not None]
            estimate = rooms_estimate(measured, scale) if measured else None
            _put(found, key, "area", total, marks(chosen), MODEL_SPACES, estimate)

    put(quantity_key("area", "room", storey=storey), spaces)
    named: dict[str, list[ModelObject]] = defaultdict(list)
    for space in spaces:
        for name in _space_names(space):
            named[name].append(space)
    for name, same in named.items():
        if len(same) == 1:  # a name two spaces share names neither
            put(quantity_key("area", "room", name=name, storey=storey), same)


def _space_area(space: ModelObject, rooms: Mapping[str, Room]) -> tuple[float | None, Room | None]:
    """A model space's net floor area: the one the model states, else that of the room the sheet
    draws it as (returned too, for what its measurement rests on); None when it has neither."""
    if (stated := space.quantities.get("area_m2")) is not None:
        return stated, None
    room = rooms.get(space.element) if space.element is not None else None
    return (None, None) if room is None else (room.area_m2, room)


def _space_names(space: ModelObject) -> set[str]:
    """What a model's space is known by, as `room_names` knows a drawn IFC space: its Name (the
    number), its LongName, and "<LongName> (<Name>)"."""
    number, long_name = space.name or None, space.long_name or None
    found = {value for value in (number, long_name) if value is not None}
    if number is not None and long_name is not None and number != long_name:
        found.add(f"{long_name} ({number})")
    return {normalised(value) for value in found}


def _with_conflicts(found: dict[str, Quantity], drawing: Drawing) -> dict[str, Quantity]:
    """Each quantity a `conflict` entry of the drawing is about, with the entry's values and its
    resolved value. An `agree` entry changes no value: it goes on the quantity as `agree`, so
    both readings show. A sheet-wide entry (an element class, the
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
            for key, derived in _room_set_areas(entry, drawing, storey, plans):
                _attach(out, key, derived, SAME)
    for entry in drawing.conflicts or ():
        if entry.status != "agree":
            continue
        agreed = QuantityConflict(
            values=entry.values, resolution=entry.resolution, note=entry.note, status="agree"
        )
        for key in _conflict_keys(entry, drawing, storey, plans):
            _agree(out, key, agreed, entry.tolerance)
    return out


def _agree(
    found: dict[str, Quantity], key: str, agreed: QuantityConflict, tolerance: float
) -> None:
    """`agreed` on the quantity at `key` when its value is one of the entry's, and no conflict
    is on it already."""
    quantity = found.get(key)
    if quantity is None or quantity.conflict is not None or quantity.agree is not None:
        return
    if all(differ(quantity.value, value.value, tolerance) for value in agreed.values):
        return
    found[key] = quantity.model_copy(update={"agree": agreed})


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
                for name in room_names(room):
                    keys += [quantity_key("area", "room", name=name, storey=s) for s in {None, own}]
            return keys
        case "apartment_area", "apartment":
            labels = [a.label for a in drawing.apartments if a.id == ref and a.label is not None]
            return [quantity_key("area", "apartment", apartment=label) for label in labels]
        case _:
            return []


def _room_set_areas(
    entry: Conflict, drawing: Drawing, storey: str, plans: Mapping[str, object]
) -> list[tuple[str, QuantityConflict]]:
    """A sheet's room count disputed between the rooms it draws and the rooms of its storey (the
    two values are those two numbers) disputes the storey's area totals the same way: each
    method's value becomes the area of its set of rooms, and the rule that picked a count picks
    that count's area. Any difference counts: it is whole rooms, not measurement noise.

    Each total is summed the way its key is: the drawn rooms' own areas, except the storey's
    total when the drawing has a building model (`_add_model_spaces`). Then the storey's set is
    the model's spaces of the storey with the model's areas; the drawn set keeps the areas the
    sheet draws (a room of another storey shows only in part)."""
    if entry.quantity != "room_count" or entry.subject.kind != "sheet" or len(entry.values) != 2:
        return []
    drawn = list(drawing.rooms)
    own = [room for room in drawn if _storey(room.attrs, room.plan, plans) == storey]
    as_drawn: RoomSets = {
        len(drawn): [(room.area_m2, room.outdoor) for room in drawn],
        len(own): [(room.area_m2, room.outdoor) for room in own],
    }
    how = (
        f"values from the room count's two sets of rooms ({len(drawn)} drawn on the sheet, "
        f"{len(own)} on storey {storey}), each one's net areas summed"
    )
    variants: list[tuple[str | None, bool, RoomSets, str]] = [
        (None, False, as_drawn, how),
        (None, True, as_drawn, how),
    ]
    variants.append((storey, True, as_drawn, how))
    if drawing.model_objects is None:
        variants.append((storey, False, as_drawn, how))
    else:
        rooms = {room.id: room for room in drawn}
        of_storey = [
            space
            for space in drawing.model_objects
            if space.class_ == SPACE and normalised(space.storey or "") == normalised(storey)
        ]
        in_model: RoomSets = {
            len(drawn): as_drawn[len(drawn)],
            len(of_storey): [(_space_area(space, rooms)[0], False) for space in of_storey],
        }
        in_model_how = (
            f"values from the room count's two sets of rooms ({len(drawn)} drawn on the sheet, "
            f"their areas as drawn; {len(of_storey)} spaces of storey {storey} in the model, "
            "their areas as the model states them), each set's areas summed"
        )
        variants.append((storey, False, in_model, in_model_how))
    found: list[tuple[str, QuantityConflict]] = []
    for scope, indoor, sets, said in variants:
        if (disputed := _set_areas(entry, sets, indoor, said)) is not None:
            found.append((quantity_key("area", "room", storey=scope, indoor=indoor), disputed))
    return found


def _set_areas(entry: Conflict, sets: RoomSets, indoor: bool, how: str) -> QuantityConflict | None:
    """The room count entry carried over to the total areas of its two room sets; None when the
    sets are not the entry's two counts, an area is unknown or the totals are equal."""
    if len(sets) != 2 or {value.value for value in entry.values} != set(sets):
        return None
    totals: dict[float, float] = {}
    for count, chosen in sets.items():
        areas = [area for area, outdoor in chosen if not (indoor and outdoor)]
        if any(area is None for area in areas):
            return None
        totals[count] = round(sum(area for area in areas if area is not None), 3)
    if not differ(min(totals.values()), max(totals.values()), SAME):
        return None  # the rooms only one set has add no area here
    values = tuple(
        value.model_copy(update={"value": totals[value.value], "unit": "m2"})
        for value in entry.values
    )
    resolution = None
    if entry.resolution is not None and entry.resolution.value in totals:
        picked = totals[entry.resolution.value]
        resolution = Resolution(rule=entry.resolution.rule, value=picked)
    return QuantityConflict(values=values, resolution=resolution, note=entry.note, derived=how)


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
    kept = {key: quantity for key, quantity in found.items() if _reads(key) <= looked_for}
    for key in found.keys() - kept.keys():
        fallback = _read_fallback(key, looked_for)
        if fallback is not None and fallback in found:
            kept[key] = found[fallback].model_copy(update={"key": key, "rule": _rule_of(key)})
    return kept


def _read_fallback(key: str, looked_for: set[str]) -> str | None:
    """A fallback count (rules.COMBINED, `first_listed`) whose first part was not read, while
    its one later part was: that part's own key. Saunas are sauna rooms, else stoves; an
    extraction that reads stoves but not rooms (a detector alone) counts the stoves."""
    subject, _, filters = key.partition("|")
    rule = next((r for r in COMBINED if r.key == subject and r.first_listed), None)
    if rule is None or _reads(rule.parts[0]) <= looked_for:
        return None
    later = [part for part in rule.parts[1:] if _reads(part) <= looked_for]
    if len(later) != 1 or len(rule.parts) != 2:
        return None
    return later[0] + (f"|{filters}" if filters else "")


def _rule_of(key: str) -> str:
    subject = key.partition("|")[0]
    return next(rule.rule.id for rule in COMBINED if rule.key == subject)


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
    """What a sum of room areas rests on, in words a user reads, when that is an estimate: the
    rooms whose own area is estimated, how, and how far off it may be; else the sheet's estimated
    scale (`scale`, from scale_estimate), unless every room's area is printed (exact)."""
    estimated = [room for room in rooms if room.area_status == "estimated"]
    if estimated:
        n, total = len(estimated), len(rooms)
        if n == total == 1:
            subject = "the room's area is"
        elif n == total:
            subject = f"the {n} rooms' areas are"
        else:
            subject = f"{n} of {total} room areas {'is' if n == 1 else 'are'}"
        how = " or ".join(
            sorted({_AREA_HOW.get(room.area_source or "", "estimated") for room in estimated})
        )
        if scale and "geometry_x_estimate" in {room.area_source for room in estimated}:
            how = how.replace(_AREA_HOW["geometry_x_estimate"], scale)
        spread = max((room.area_uncertainty or 0.0 for room in estimated), default=0.0)
        which = "the area" if n == 1 else "each area"
        band = f"; {which} may be off by about ±{_percent(spread)}" if spread else ""
        return f"{subject} {how}{band}"
    if rooms and all(room.area_status == "exact" for room in rooms):
        return None
    return scale


# How an estimated room area was measured, in words (extraction_v1 `area_source`)
_AREA_HOW = {
    "geometry_x_estimate": "measured on an estimated scale",
    "geometry_x_scale": "measured from its outline at the sheet's scale",
}


def _percent(spread: float) -> str:
    return f"{round(100 * spread)}%"


def scale_estimate(scale: Scale) -> str | None:
    """What an area or length on a sheet with this scale rests on, in words a user reads, when
    that is an estimate."""
    match scale.status:
        case "estimated":
            how = f" ({scale.source})" if scale.source else ""
            band = ""
            if scale.uncertainty:
                band = f", which may be off by about ±{_percent(scale.uncertainty)}"
            return f"measured on an estimated scale{how}{band}"
        case "not_to_scale":
            return "measured on a sheet marked not to scale, so its scale is a guess"
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
    excluded: Sequence[tuple[Mark, str]] = (),
) -> None:
    found[key] = Quantity(
        key=key,
        value=value if measure == "count" else round(value, 3),
        unit=UNITS[measure],
        marks=tuple(marks),
        rule=rule.id,
        estimate=estimate,
        excluded=tuple(excluded),
    )


def _area_sum(
    found: dict[str, Quantity],
    key: str,
    rooms: Sequence[Room],
    rule: CountingRule,
    scale: str | None,
    excluded: Sequence[tuple[Mark, str]] = (),
) -> None:
    """The total net area of `rooms`; no key when there are none or one has no area. `scale`:
    what the sheet's scale makes an estimate of (scale_estimate). `excluded`: the rooms the
    rule left out, with the reason."""
    areas = [room.area_m2 for room in rooms]
    if rooms and all(area is not None for area in areas):
        total = sum(area for area in areas if area is not None)
        marks = [_mark(room) for room in rooms]
        estimate = rooms_estimate(rooms, scale)
        _put(found, key, "area", total, marks, rule, estimate, excluded)


def _left_out(rooms: Sequence[Room], shafts: bool) -> list[tuple[Mark, str]]:
    """The rooms an indoor or dwelling total leaves out, with the reason."""
    out = [(_mark(room), "outdoor room") for room in rooms if room.outdoor]
    if shafts:
        out += [(_mark(r), "shaft") for r in rooms if r.type == "shaft" and not r.outdoor]
    return out


def room_names(room: Room) -> set[str]:
    """Every name a room answers to (its numbers, names, printed label), normalised."""

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
    sums: bool = True,
) -> None:
    """Every quantity of one set of items: the whole sheet (`storey` None) or one storey.
    `scale`: what the sheet's scale makes an estimate of (scale_estimate). `sums` False: the
    element sums, the rooms' area total and each named room's area are left to a building
    model (`_add_model`)."""
    for key, chosen in counted.items():
        _put(
            found,
            quantity_key("count", key, storey=storey),
            "count",
            len(chosen.marks),
            chosen.marks,
            chosen.rule,
            excluded=chosen.excluded,
        )
    _put(
        found,
        quantity_key("count", "room", storey=storey),
        "count",
        len(rooms),
        [_mark(room) for room in rooms],
        EACH_ONCE,
    )
    if sums:
        _area_sum(found, quantity_key("area", "room", storey=storey), rooms, ROOMS_TOTAL, scale)
    indoor = [room for room in rooms if not room.outdoor]
    key = quantity_key("area", "room", storey=storey, indoor=True)
    _area_sum(found, key, indoor, INDOOR_TOTAL, scale, _left_out(rooms, shafts=False))
    labelled: dict[str, list[Room]] = defaultdict(list)
    named: dict[str, list[Room]] = defaultdict(list)
    for room in rooms:
        if room.label:
            labelled[normalised(room.label)].append(room)
        for name in room_names(room):
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
        if sums and len(same) == 1:  # a name two rooms share names neither
            key = quantity_key("area", "room", name=name, storey=storey)
            _area_sum(found, key, same, ROOM_AREA, scale)
    for (cls, measure), attr in MEASURED.items():
        of_class = [element for element in elements if element.class_ == cls]
        values = [element.attrs.get(attr) for element in of_class]
        if sums and of_class and all(isinstance(v, int | float) and v is not True for v in values):
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
        left_out = _left_out(drawing.rooms, shafts=True)
        _area_sum(found, key, kept, SHEET_DWELLING, scale, left_out)


def _apartment_area(
    found: dict[str, Quantity],
    key: str,
    stated: float | None,
    rooms: Sequence[Room],
    scale: str | None,
) -> None:
    """The stated area, else the apartment's rooms that are neither outdoor nor shafts."""
    kept = [r for r in rooms if not r.outdoor and r.type != "shaft"]
    left_out = _left_out(rooms, shafts=True)
    if stated is not None:
        marks = [_mark(room) for room in kept]
        _put(found, key, "area", stated, marks, APARTMENT_AREA, excluded=left_out)
    else:
        _area_sum(found, key, kept, APARTMENT_AREA, scale, left_out)


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
        for name in room_names(room):
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

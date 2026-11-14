"""Check a drawing model against a rule pack: pass, fail or cannot tell per room, door or sheet.

Pure: reads the `Drawing` and its takeoff, writes `RuleCheck`s. A missing scale, a class that was
not read, an item with no position, a room with no area, or an estimate whose error reaches
across the limit is "cannot tell", with the reason; it is never a guess. Each item is linked to
its takeoff row (`quantity`) and its mark there (`mark_id`), so a screen can open the row.
"""

import math
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence

from app.core.checks.model import (
    COMPARISON_TEXT,
    CheckMark,
    CheckResult,
    CheckStatus,
    CheckSubject,
    CheckUnit,
    CodeRule,
    Comparison,
    RuleCheck,
    RulePack,
    RuleStatus,
)
from app.core.drawing.model import (
    Box,
    Drawing,
    Element,
    ElementClass,
    Page,
    ReadClass,
    Room,
    RoomType,
    words,
)
from app.core.pipeline.model import Quantity, Route
from app.core.pipeline.rules import ROOM_NUMBERS
from app.core.pipeline.takeoff import known_quantities, normalised, quantity_key, room_names
from app.core.review.review import label
from app.core.wording import count as count_of

# A window or a door meets a room when its box is within this of the room's outline: it sits in a
# wall, whose inner face the outline follows. On the dev split's gold sheets a bedroom's nearest
# window is within 0.05 m or far off: 0.1-2% are between 0.05 and 0.6 m (decision 0009)
MEETS_M = 0.35
# Without a scale, the slack as a share of the page's long side (0.42 m on A3 at 1:100).
MEETS_SHEET = 0.01
# Rooms open to the outside: a door to one may be glazed, so it may light the room it opens from
OUTSIDE: tuple[RoomType, ...] = ("balcony", "outdoor")
# How far a door symbol's box may be off its leaf: the line weight and the frame drawn with it.
DOOR_BOX_TOLERANCE_M = 0.03
# A door's clear opening is narrower than its leaf or its frame's outer width: the frame and the
# leaf's thickness when open take up to about this. The symbol (or a model's width) is therefore an
# upper bound on the clear width: below the limit is a fail, within this above it cannot tell.
DOOR_FRAME_M = 0.10

# The routes that read a drawing's own lines or model; any other (raster, or not known) read it off
# a picture, or may have: its outlines, windows and door boxes never decide a fail (S2, 2026-11-14)
MEASURED: tuple[Route, ...] = ("vector", "bim", "cad")
CHECKED_ON_SHEETS = "The building model is checked on its sheets in this project."

NO_DECIDING = "no rule decides between them"
MODEL_GIVES = "the building model gives"
ROOM_NOUNS: dict[str, str] = {
    "living": "living room",
    "storage": "storage room",
    "wc": "WC",
    "outdoor": "outdoor space",
    "other": "other room",
}

Quantities = Mapping[str, Quantity]
# What an op gives: its results, and with none, why and whether that is cannot tell (what the rule
# needs was not read) or not_applicable (nothing on the drawing the rule applies to).
Outcome = tuple[list[CheckResult], str, RuleStatus]


def check_drawing(
    drawing: Drawing, pack: RulePack, route: Route | None = None, on_sheets: bool = False
) -> tuple[RuleCheck, ...]:
    """`route`: the route that read the drawing (DrawingInfo.route); None: not known, taken as
    read off a picture. `on_sheets`: the drawing is a building model whose sheets are in the same
    project, so its rules are checked there and not on the model (N3, 2026-11-14)."""
    if on_sheets and not drawing.pages:
        return tuple(
            RuleCheck(
                rule_id=rule.id,
                title=rule.title,
                status="not_applicable",
                why=CHECKED_ON_SHEETS,
                clause=rule.clause,
                results=(),
            )
            for rule in pack.rules
        )
    quantities = known_quantities(drawing)
    return tuple(
        check_rule(drawing, rule, quantities, pack.fail_means, route) for rule in pack.rules
    )


def check_rule(
    drawing: Drawing,
    rule: CodeRule,
    quantities: Quantities | None = None,
    fail_means: str | None = None,
    route: Route | None = None,
) -> RuleCheck:
    """`fail_means`: the pack's sentence on what a fail means, put after each fail's why.
    `route` raster or None: the drawing was (or may have been) read off a picture, whose
    outlines, windows and door boxes a reader can get wrong, so they never make a fail on their
    own."""
    ops: dict[str, Callable[[Drawing, CodeRule, Quantities, bool], Outcome]] = {
        "room_area": _room_area,
        "room_windows": _room_windows,
        "door_width": _door_width,
        "takeoff": _takeoff,
    }
    found = known_quantities(drawing) if quantities is None else quantities
    results, why, status = ops[rule.op](drawing, rule, found, route not in MEASURED)
    if fail_means is not None:
        results = [
            result.model_copy(update={"why": f"{result.why} {fail_means}"})
            if result.status == "fail"
            else result
            for result in results
        ]
    if results:
        status = overall(result.status for result in results)
        why = results[0].why if len(results) == 1 else _tally(results)
    return RuleCheck(
        rule_id=rule.id,
        title=rule.title,
        status=status,
        why=why,
        clause=rule.clause,
        results=tuple(results),
    )


def overall(statuses: Iterable[RuleStatus]) -> RuleStatus:
    """Fail when one fails, else cannot tell when one cannot, else pass when one passes; nothing
    but not_applicable (or nothing at all): not_applicable."""
    found = set(statuses)
    for status in ("fail", "cannot_tell", "pass"):
        if status in found:
            return status
    return "not_applicable"


def holds(value: float, comparison: Comparison, limit: float) -> bool:
    match comparison:
        case ">=":
            return value >= limit
        case ">":
            return value > limit
        case "<=":
            return value <= limit
        case "<":
            return value < limit


def _within(low: float, high: float, rule: CodeRule) -> CheckStatus:
    """The status of a value known to lie between `low` and `high`: cannot tell when the two
    ends fall on different sides of the limit."""
    at_low = holds(low, rule.comparison, rule.limit)
    at_high = holds(high, rule.comparison, rule.limit)
    if at_low != at_high:
        return "cannot_tell"
    return "pass" if at_low else "fail"


def _tally(results: Sequence[CheckResult]) -> str:
    counts = Counter(result.status for result in results)
    parts = [
        f"{counts[status]} {text}"
        for status, text in (("fail", "fail"), ("cannot_tell", "cannot tell"), ("pass", "pass"))
        if counts[status]
    ]
    return f"Of {len(results)} checked: {', '.join(parts)}."


def _num(value: float, unit: CheckUnit) -> str:
    if unit == "count":
        return str(round(value))
    digits = 2 if unit in ("m", "m2") else 1
    return f"{value:.{digits}f}".rstrip("0").rstrip(".")


def _limit(rule: CodeRule) -> str:
    unit = "" if rule.unit == "count" else f" {rule.unit}"
    return f"{COMPARISON_TEXT[rule.comparison]} {_num(rule.limit, rule.unit)}{unit}"


def _unread(drawing: Drawing, *classes: ReadClass) -> str | None:
    """Why the items a rule needs are not on the drawing model, or None when they can be."""
    if drawing.counts is not None:
        return "The drawing gives totals only, with no rooms or doors placed on it to check."
    if not drawing.pages:
        return "The drawing is a building model with no sheet to check."
    missing = [cls for cls in classes if drawing.read is not None and cls not in drawing.read]
    if missing:
        names = " or ".join(f"{words(cls)}s" for cls in missing)
        return f"No {names} were read on this drawing, so it cannot be checked."
    return None


def _located(element: Element) -> bool:
    """False for an element a second reader counted with no position of its own: its box is
    its plan's (app/core/review/review.py unlocated_boxes), so it measures nothing."""
    return element.attrs.get("located") is not False


def room_noun(kind: RoomType) -> str:
    """A room type as a sentence names the room: "living" is a "living room"."""
    return ROOM_NOUNS.get(kind, words(kind))


def _rooms(drawing: Drawing, rule: CodeRule, types: Iterable[RoomType] | None = None) -> list[Room]:
    """The rooms a room op checks: of its types (or `types`), indoor, and not labelled as one it
    skips."""
    skipped = {normalised(text) for text in rule.applies_to.skip_labels}
    kinds = set(rule.applies_to.room_types if types is None else types)
    return [
        room
        for room in drawing.rooms
        if room.type in kinds
        and not room.outdoor
        and (room.label is None or normalised(room.label) not in skipped)
    ]


def _none_of(rule: CodeRule) -> str:
    kinds = " or ".join(room_noun(kind) for kind in rule.applies_to.room_types)
    return f"The drawing shows no {kinds}, so there is nothing to check."


def _nothing(drawing: Drawing, rule: CodeRule, why: str) -> tuple[str, RuleStatus]:
    """Why nothing was checked, and its status: not applicable only when no room of the drawing
    could be of a kind the rule names. A room whose kind we could not tell (`other`: its label
    matched no word) may be one, so the rule cannot tell (S1, 2026-11-14)."""
    if "other" in rule.applies_to.room_types:
        return why, "not_applicable"
    unknown = len(_rooms(drawing, rule, ("other",)))
    if not unknown:
        return why, "not_applicable"
    kinds = " or ".join(room_noun(kind) for kind in rule.applies_to.room_types)
    are, they = ("is", "it") if unknown == 1 else ("are", "they")
    return (
        f"No {kinds} was recognised, but {count_of(unknown, 'room')} {are} of a kind we could not "
        f"tell, so {they} cannot be checked.",
        "cannot_tell",
    )


def _printed(room: Room) -> str | None:
    """The room as the sheet writes it: its label, and its number when that is another text
    ("Schlafzimmer 4.02"), so two rooms of one name are told apart."""
    numbers = [value for key in ROOM_NUMBERS if isinstance(value := room.attrs.get(key), str)]
    written = (room.label or "").split()
    extra = [number for number in numbers[:1] if number not in written]  # not said twice
    return " ".join([*written, *extra]) or None


def _room_name(room: Room) -> str:
    """By its printed name, else by its kind alone ("a hall"): the id is ours, not the sheet's,
    and the mark shows which room it is."""
    noun, printed = room_noun(room.type), _printed(room)
    if printed:
        return f'the {noun} "{printed}"'
    return f"{'an' if noun[:1] in 'aeiou' else 'a'} {noun}"


def mark_id(quantity: Quantity | None, page: int, box: Box) -> str | None:
    """The item's MarkView.id in the quantity's takeoff row: m<n> for its n-th mark, x<n> for the
    n-th item its rule left out (app/core/review/review.py mark_views); None: not in the row."""
    if quantity is None:
        return None
    for at, mark in enumerate(quantity.marks, start=1):
        if (mark.page, mark.box) == (page, box):
            return f"m{at}"
    for at, (mark, _) in enumerate(quantity.excluded, start=1):
        if (mark.page, mark.box) == (page, box):
            return f"x{at}"
    return None


def _room_row(room: Room, quantities: Quantities) -> Quantity | None:
    """The room's takeoff row: its own area by one of its names, else its type's count."""
    keys = [quantity_key("area", "room", name=name) for name in sorted(room_names(room))]
    for key in [*keys, f"room:{room.type}"]:
        found = quantities.get(key)
        if mark_id(found, room.page, room.box) is not None:
            return found
    return None


def _room_subject(room: Room, quantities: Quantities) -> tuple[CheckSubject, CheckMark]:
    shown = _printed(room) or room_noun(room.type)  # the id is in `ref`, not shown
    row = _room_row(room, quantities)
    mark = CheckMark(
        page=room.page,
        box=room.box,
        polygon=room.polygon,
        ref=room.id,
        label=shown,
        role="subject",
        quantity=row.key if row else None,
        mark_id=mark_id(row, room.page, room.box),
    )
    return CheckSubject(kind="room", ref=room.id, label=shown), mark


def _element_mark(element: Element, role: str, quantities: Quantities) -> CheckMark:
    row = quantities.get(element.class_)
    found = mark_id(row, element.page, element.box)
    return CheckMark.model_validate(
        {
            "page": element.page,
            "box": element.box,
            "polygon": element.polygon,
            "ref": element.id,
            "label": words(element.class_),
            "role": role,
            "quantity": row.key if row is not None and found is not None else None,
            "mark_id": found,
        }
    )


def _result(
    rule: CodeRule,
    subject: CheckSubject,
    status: CheckStatus,
    value: float | None,
    why: str,
    marks: Sequence[CheckMark],
    quantity: str | None,
) -> CheckResult:
    return CheckResult(
        id=f"{rule.id}:{subject.ref or 'sheet'}",
        rule_id=rule.id,
        status=status,
        subject=subject,
        value=None if value is None else round(value, 3),  # to the mm, the m2/1000
        limit=rule.limit,
        unit=rule.unit,
        comparison=rule.comparison,
        comparison_text=COMPARISON_TEXT[rule.comparison],
        why=why,
        quantity=quantity,
        marks=tuple(marks),
    )


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def _room_area(drawing: Drawing, rule: CodeRule, quantities: Quantities, picture: bool) -> Outcome:
    if (why := _unread(drawing, "room")) is not None:
        return [], why, "cannot_tell"
    results: list[CheckResult] = []
    for room in _rooms(drawing, rule):
        subject, mark = _room_subject(room, quantities)
        name, area, row = _cap(_room_name(room)), room.area_m2, mark.quantity
        if area is None:
            why = f"{name} has no area: none is printed and it could not be measured."
            results.append(_result(rule, subject, "cannot_tell", None, why, [mark], row))
            continue
        shown = _num(area, "m2")
        if room.area_status != "estimated":
            status: CheckStatus = "pass" if holds(area, rule.comparison, rule.limit) else "fail"
            why = f"{name} is {shown} m2; the rule asks {_limit(rule)}."
        elif room.area_uncertainty is None:
            status = "cannot_tell"
            why = (
                f"{name} is about {shown} m2, an estimate with no stated error, "
                f"so it cannot be judged against {_limit(rule)}."
            )
        else:
            spread = room.area_uncertainty
            status = _within(area * (1 - spread), area * (1 + spread), rule)
            band = f"about {shown} m2 (estimated, ±{round(spread * 100)}%)"
            if status == "cannot_tell":
                why = f"{name} is {band}, which reaches across {_limit(rule)}."
            else:
                why = f"{name} is {band}; the rule asks {_limit(rule)}."
        # A fail stands only on a printed area or on a drawn (vector) outline at a real scale:
        # on the dev drawings none of 9 area fails from outlines read off a picture was real
        # (decision 0009)
        derived = room.area_status == "estimated" or (picture and room.area_source != "printed")
        if status == "fail" and derived:
            status = "cannot_tell"
            how = "is an estimate" if room.area_status == "estimated" else "was read off a picture"
            why = (
                f"{name} is about {shown} m2 and the rule asks {_limit(rule)}, but its area {how}, "
                "not printed, so a fail cannot be told."
            )
        results.append(_result(rule, subject, status, area, why, [mark], row))
    return results, *_nothing(drawing, rule, _none_of(rule))


def _room_windows(
    drawing: Drawing, rule: CodeRule, quantities: Quantities, picture: bool
) -> Outcome:
    if (why := _unread(drawing, "room", "window")) is not None:
        return [], why, "cannot_tell"
    pages = {page.page: page for page in drawing.pages}
    windows = [element for element in drawing.elements if element.class_ == "window"]
    # What a building model says of each of its spaces' windows (attrs.windows), by the room
    modelled = {
        item.element: item.attrs["windows"]
        for item in drawing.model_objects or ()
        if item.class_ == "space"
        and item.element is not None
        and isinstance(item.attrs.get("windows"), int)
    }
    results: list[CheckResult] = []
    for room in _rooms(drawing, rule):
        subject, mark = _room_subject(room, quantities)
        found = [w for w in windows if _located(w) and _meets(w, room, pages, drawing)]
        marks = [mark, *(_element_mark(window, "counted", quantities) for window in found)]
        name = _cap(_room_name(room))
        model_count = modelled.get(room.id)
        if isinstance(model_count, int) and not isinstance(model_count, bool):
            count = model_count
            status: CheckStatus = "pass" if holds(count, rule.comparison, rule.limit) else "fail"
            why = (
                f"{name}: the building model gives it {_windows(count)}, {len(found)} drawn on "
                f"this sheet; the rule asks {_limit(rule)}."
            )
            # A door to the outside may be glazed, in a model as on a drawn plan (decision 0009)
            if status == "fail" and (held := _door_out(drawing, room, pages)) is not None:
                status = "cannot_tell"
                why = f"{name}: the building model gives it {_windows(count)}, but {held}."
        else:
            count = len(found)
            status = "pass" if holds(count, rule.comparison, rule.limit) else "fail"
            why = f"{name} has {_windows(count)} on its outline; the rule asks {_limit(rule)}."
            if status == "fail":
                held = _window_hold(drawing, room, windows, pages, picture)
                if held is not None:
                    status = "cannot_tell"
                    why = f"{name} has {_windows(count)} on its outline, but {held}."
        results.append(_result(rule, subject, status, float(count), why, marks, mark.quantity))
    return results, *_nothing(drawing, rule, _none_of(rule))


def _windows(count: int) -> str:
    return "no window" if count == 0 else f"{count} window{'s' if count > 1 else ''}"


def _window_hold(
    drawing: Drawing,
    room: Room,
    windows: Sequence[Element],
    pages: Mapping[int, Page],
    picture: bool,
) -> str | None:
    """Why a room with too few windows on its outline may still have them, or None."""
    if any(window.page == room.page and not _located(window) for window in windows):
        return "some windows on the sheet have no position, so they may be in it"
    if (held := _door_out(drawing, room, pages)) is not None:
        return held
    if picture:
        # On the dev drawings 1 of 10 window fails read off a picture was real (decision 0009)
        return "windows read from a picture can be missed"
    if drawing.model_objects is not None:
        # The model's IfcWindows without a shape are not drawn on its sheets (decision 0009)
        return "a sheet drawn from a building model does not draw all its windows"
    return None


def _door_out(drawing: Drawing, room: Room, pages: Mapping[int, Page]) -> str | None:
    """Why a door of the room may light it (to a balcony or straight outside), or None."""
    outside = [other for other in drawing.rooms if other.type in OUTSIDE or other.outdoor]
    for door in drawing.elements:
        if door.class_ != "door" or not _located(door) or not _meets(door, room, pages, drawing):
            continue
        others = [other for other in drawing.rooms if other is not room]
        if any(_meets(door, other, pages, drawing) for other in outside if other is not room):
            return "a door opens from it to a balcony or the outside, and that door may be glazed"
        if not any(_meets(door, other, pages, drawing) for other in others):
            return "a door opens from it straight to the outside, and that door may be glazed"
    return None


def _slack(page: Page, drawing: Drawing) -> float:
    """MEETS_M in the page's units, at the drawing's scale; without one, MEETS_SHEET of the page."""
    m_per_unit = drawing.scale.m_per_unit
    if m_per_unit is not None and drawing.scale.status in ("scaled", "estimated"):
        return MEETS_M / m_per_unit
    return MEETS_SHEET * max(page.width, page.height)


def _meets(element: Element, room: Room, pages: Mapping[int, Page], drawing: Drawing) -> bool:
    """Whether the element's box is on the room's page and within the slack of its outline (or
    over it): a window in its outer wall, a door in a wall it shares. In the page's units, so a
    page's aspect does not stretch the distance."""
    page = pages.get(room.page)
    if page is None or element.page != room.page:
        return False
    w, h = page.width, page.height
    if room.polygon is not None:
        outline = [(x * w, y * h) for x, y in room.polygon]
    else:
        outline = _corners(room.box, w, h)
    return _gap(_corners(element.box, w, h), outline) <= _slack(page, drawing)


Point = tuple[float, float]


def _corners(box: Box, width: float, height: float) -> list[Point]:
    x0, y0, x1, y1 = box
    return [(x0 * width, y0 * height), (x1 * width, y0 * height), (x1 * width, y1 * height),
            (x0 * width, y1 * height)]  # fmt: skip


def _edges(points: Sequence[Point]) -> list[tuple[Point, Point]]:
    return list(zip(points, [*points[1:], points[0]], strict=True))


def _gap(first: Sequence[Point], second: Sequence[Point]) -> float:
    """The distance between two outlines; 0 when one overlaps or holds the other."""
    if any(_inside(point, second) for point in first) or any(
        _inside(point, first) for point in second
    ):
        return 0.0
    return min(_segment_gap(a, b, c, d) for a, b in _edges(first) for c, d in _edges(second))


def _inside(point: Point, outline: Sequence[Point]) -> bool:
    x, y = point
    inside = False
    for (ax, ay), (bx, by) in _edges(outline):
        if (ay > y) != (by > y) and x < ax + (y - ay) * (bx - ax) / (by - ay):
            inside = not inside
    return inside


def _segment_gap(a: Point, b: Point, c: Point, d: Point) -> float:
    if _crosses(a, b, c, d):
        return 0.0
    return min(
        _to_segment(a, c, d), _to_segment(b, c, d), _to_segment(c, a, b), _to_segment(d, a, b)
    )


def _crosses(a: Point, b: Point, c: Point, d: Point) -> bool:
    def side(p: Point, q: Point, r: Point) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    return side(a, b, c) * side(a, b, d) < 0 and side(c, d, a) * side(c, d, b) < 0


def _to_segment(point: Point, a: Point, b: Point) -> float:
    (x, y), (ax, ay), (bx, by) = point, a, b
    dx, dy = bx - ax, by - ay
    length = dx * dx + dy * dy
    t = 0.0 if length == 0 else max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / length))
    return math.hypot(x - (ax + t * dx), y - (ay + t * dy))


def _door_width(drawing: Drawing, rule: CodeRule, quantities: Quantities, picture: bool) -> Outcome:
    door: ElementClass = "door"
    scoped = bool(rule.applies_to.room_types or rule.applies_to.not_room_types)
    if (why := _unread(drawing, door, *(("room",) if scoped else ()))) is not None:
        return [], why, "cannot_tell"
    pages = {page.page: page for page in drawing.pages}
    model_widths = {
        item.element: item.quantities["width_m"]
        for item in drawing.model_objects or ()
        if item.class_ == door and item.element is not None and "width_m" in item.quantities
    }
    scale = drawing.scale
    results: list[CheckResult] = []
    for item in (element for element in drawing.elements if element.class_ == door):
        if not _door_applies(item, rule, drawing, pages):
            continue
        mark = _element_mark(item, "subject", quantities)
        name = _door_name(item, drawing, pages)
        subject = CheckSubject(kind="element", ref=item.id, label=name)
        name = _cap(name)
        page = pages.get(item.page)
        unknown: str | None = None
        width = spread = 0.0
        how = ""
        if item.id in model_widths:
            width, spread = model_widths[item.id], DOOR_BOX_TOLERANCE_M
            how = MODEL_GIVES
        elif not _located(item):
            unknown = f"{name} was counted with no position of its own, so it has no width."
        elif scale.status == "estimated":
            # The raster route estimates a scale from the doors' own size (raster_scale.py): a
            # door measured at it measures what the estimate assumed
            unknown = f"{name} cannot be measured: the scale was estimated from the doors."
        elif scale.m_per_unit is None or scale.status != "scaled":
            unknown = f"{name} cannot be measured: the drawing has no scale."
        elif page is None:
            unknown = f"{name} is on no page of the drawing."
        else:
            x0, y0, x1, y1 = item.box
            long_side = max((x1 - x0) * page.width, (y1 - y0) * page.height)
            width = long_side * scale.m_per_unit
            spread = DOOR_BOX_TOLERANCE_M + width * (scale.uncertainty or 0.0)
            how = "its symbol measures"
        if unknown is not None:
            results.append(
                _result(rule, subject, "cannot_tell", None, unknown, [mark], mark.quantity)
            )
            continue
        # The clear opening is at most the width measured, and up to DOOR_FRAME_M less.
        status = _within(width - spread - DOOR_FRAME_M, width + spread, rule)
        if picture and how != MODEL_GIVES:
            # A box a detector drew round a door on a picture is not a measurement, either way
            # (orchestrator, 2026-11-14 12:51 for a fail; S3, 2026-11-14 for a pass)
            why = (
                f"{name}: its symbol measures {_num(width, 'm')} m and the rule asks "
                f"{_limit(rule)}, but it was read off a picture, whose door boxes are not "
                "measurements, so it cannot be told."
            )
            results.append(_result(rule, subject, "cannot_tell", width, why, [mark], mark.quantity))
            continue
        shown = _num(width, "m")
        frame = f"{round(DOOR_FRAME_M * 100)} cm (our allowance for the frame, not the law's)"
        if status == "fail":
            why = f"{name}: {how} {shown} m, so its clear opening cannot be {_limit(rule)}."
        elif status == "pass":
            why = (
                f"{name}: {how} {shown} m; less up to {frame}, its clear opening is "
                f"still {_limit(rule)}."
            )
        else:
            why = (
                f"{name}: {how} {shown} m; its clear opening is up to {frame} less, "
                f"so it may or may not be {_limit(rule)}."
            )
        results.append(_result(rule, subject, status, width, why, [mark], mark.quantity))
    why = f"The drawing shows no {_doors_of(rule)}, so there is nothing to check."
    if not rule.applies_to.room_types or _rooms(drawing, rule):
        return results, why, "not_applicable"  # a room it names is there: its doors are not
    return results, *_nothing(drawing, rule, why)


def _door_applies(
    item: Element, rule: CodeRule, drawing: Drawing, pages: Mapping[int, Page]
) -> bool:
    """A door meeting a room of the rule's room types (any door when it names none) and no room
    of its not_room_types: a door to a bedroom, not one to a closet or a sauna."""
    applies = rule.applies_to
    met: set[str] = set()
    for room in drawing.rooms:
        if _meets(item, room, pages, drawing):
            met |= {room.type, "outdoor"} if room.outdoor else {room.type}
    if applies.room_types and not met & set(applies.room_types):
        return False
    return not met & set(applies.not_room_types)


def _door_name(item: Element, drawing: Drawing, pages: Mapping[int, Page]) -> str:
    """A door as the rooms it joins: "the door between the bedroom "4.01" and the hall"."""
    met = [_room_name(room) for room in drawing.rooms if _meets(item, room, pages, drawing)]
    if len(met) == 2:
        return f"the door between {met[0]} and {met[1]}"
    if len(met) == 1:
        return f"the door of {met[0]}"
    if met:  # three or more: a door the outlines put by several rooms
        return f"the door by {', '.join(met[:-1])} and {met[-1]}"
    return "the door at the marked place"


def _doors_of(rule: CodeRule) -> str:
    kinds = " or ".join(room_noun(kind) for kind in rule.applies_to.room_types)
    return f"door to a {kinds}" if kinds else "door"


def _takeoff(drawing: Drawing, rule: CodeRule, quantities: Quantities, picture: bool) -> Outcome:
    key = rule.key or ""
    name = label(key, drawing)
    subject = CheckSubject(kind="sheet", ref=None, label=name)
    quantity = quantities.get(key)
    if quantity is None:
        why = f"The drawing does not give the {name}, so it cannot be checked."
        return [_result(rule, subject, "cannot_tell", None, why, [], None)], "", "cannot_tell"
    placed = {(element.page, element.box) for element in drawing.elements if _located(element)}
    unplaced = {(e.page, e.box) for e in drawing.elements if not _located(e)} - placed
    marks = [
        CheckMark(page=mark.page, box=mark.box, role="counted", quantity=key, mark_id=f"m{at}")
        for at, mark in enumerate(quantity.marks, start=1)
        if (mark.page, mark.box) not in unplaced  # no position of its own: never drawn
    ]
    value = float(quantity.value)
    shown = f"{_num(value, rule.unit)}{'' if rule.unit == 'count' else ' ' + rule.unit}"
    conflict = quantity.conflict
    if conflict is not None and conflict.resolution is None:
        status: CheckStatus = "cannot_tell"
        why = f"Two methods measured the {name} differently and {NO_DECIDING}."
    elif quantity.estimate is not None:
        status = "cannot_tell"
        why = f"The {name} is about {shown}, an estimate: {quantity.estimate}."
    else:
        status = "pass" if holds(value, rule.comparison, rule.limit) else "fail"
        why = f"The {name} is {shown}; the rule asks {_limit(rule)}."
    return [_result(rule, subject, status, value, why, marks, key)], "", "cannot_tell"

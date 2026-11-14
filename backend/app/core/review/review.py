"""The review use cases: the takeoff rows with their marks, a surveyor's edits with the recount, and
sign-off. Edits never change the drawing model; they are kept beside it (`ReviewState`), and every
value shown is the drawing model's value with the edits applied.

A mark's id is its position in the quantity's marks (`m1`, `m2`...), since the drawing model's
marks have no ids of their own; an added mark is `a1`, `a2`...; an item the counting rule left out
(`Quantity.excluded`) is `x1`, `x2`..., shown with its reason, and `restore` counts it in. A mark
is joined to the element or room it marks by page and box, for its label, id and outline. The
recount is the ingest value minus the rejected marks' values plus the added and counted-in ones',
so a count without marks behind it (a model's object count) still recounts. A sum with a mark of
unknown value cannot be recounted, so only `settle` changes it. A settled value holds until the
next mark edit. An edit changes its own quantity only.

Two rules keep a demo honest: a signed-off quantity is not edited until the sign-off is undone,
and a conflict no rule decides is settled by a person before it can be signed off.
"""

from collections.abc import Mapping, Sequence

from app.core.drawing.model import Box, Drawing, Polygon
from app.core.errors import DomainError, InvalidInputError, NotFoundError
from app.core.pipeline.model import Measure, Quantity
from app.core.review.model import (
    Added,
    Edit,
    MarkState,
    MarkView,
    MethodValue,
    ReviewState,
    Row,
    RowStatus,
    RuleText,
    Scope,
    Settled,
    SignOff,
)

MEASURES: tuple[Measure, ...] = ("area", "length", "volume", "text")
# An element or room by where it is: its id, label, outline and (a room) its area.
Item = tuple[str | None, str | None, Polygon | None, float | None]


class NotAllowedError(DomainError):
    """An edit the review's state forbids now (a signed-off quantity, an unsettled conflict)."""


def parse_key(key: str) -> tuple[Measure, str, Scope]:
    """The measure, subject and filters of a takeoff key (takeoff.py quantity_key)."""
    head, *filters = key.split("|")
    measure: Measure = "count"
    for found in MEASURES:
        if head.startswith(f"{found}:"):
            measure = found
    subject = head if measure == "count" else head.split(":", 1)[1]
    values: dict[str, str] = {}
    flags: set[str] = set()
    for part in filters:
        name, equals, value = part.partition("=")
        if equals:
            values[name] = value
        else:
            flags.add(name)
    scope = Scope(
        storey=values.get("storey"),
        label=values.get("label"),
        name=values.get("name"),
        apartment=values.get("apartment"),
        indoor="indoor" in flags,
        model="model" in flags,
        largest="largest" in flags,
    )
    return measure, subject, scope


def label(key: str) -> str:
    """A readable name for a takeoff key: `area:room|indoor` is "area of room (indoor)"."""
    _, *filters = key.split("|")
    measure, subject, _ = parse_key(key)
    name = subject.replace(":", " ")
    text = f"{name} count" if measure == "count" else f"{measure} of {name}"
    if filters:
        text += " (" + ", ".join(part.replace("=", " ") for part in filters) + ")"
    return text


def mark_views(quantity: Quantity, drawing: Drawing, state: ReviewState) -> tuple[MarkView, ...]:
    """The quantity's marks, then the added ones, numbered in that order among those counted."""
    rejected = set(state.rejected.get(quantity.key, ()))
    included = set(state.included.get(quantity.key, ()))
    items = _items(drawing)
    unplaced = unlocated_boxes(drawing)
    views: list[MarkView] = []
    number = 0
    marks = [(f"m{at}", mark, None) for at, mark in enumerate(quantity.marks, start=1)]
    marks += [(f"x{at}", mark, why) for at, (mark, why) in enumerate(quantity.excluded, start=1)]
    for mark_id, mark, reason in marks:
        if (mark.page, mark.box) in unplaced:
            continue  # no position of its own: never drawn (`Row.unlocated` counts it)
        counted = mark_id in included if reason is not None else mark_id not in rejected
        number += counted
        ref, name, polygon, area = items.get((mark.page, mark.box), (None, None, None, None))
        value: float | None = None
        if quantity.unit == "count":
            value = 1.0
        elif quantity.unit == "m2":  # a sum of rooms: each mark is a room's outline
            value = area
        shown: MarkState = "counted" if counted else "excluded" if reason else "rejected"
        views.append(
            MarkView(
                id=mark_id,
                n=number if counted else None,
                page=mark.page,
                box=mark.box,
                polygon=polygon,
                state=shown,
                value=value,
                label=name,
                ref=ref,
                reason=reason,
            )
        )
    for added in state.added.get(quantity.key, ()):
        number += 1
        views.append(
            MarkView(
                id=added.id,
                n=number,
                page=added.page,
                box=added.box,
                polygon=None,
                state="added",
                value=1.0,
                label=None,
                ref=None,
                reason=None,
            )
        )
    return _settled(quantity, tuple(views), state)


def _settled(
    quantity: Quantity, views: tuple[MarkView, ...], state: ReviewState
) -> tuple[MarkView, ...]:
    """A settled sum of one part (one room's area): that part is the settled value, so its mark
    says what the answer says. The parts of a larger sum keep what was measured."""
    settled = state.settled.get(quantity.key)
    counted = [view for view in views if view.state in ("counted", "added")]
    if settled is None or quantity.unit == "count" or len(counted) != 1:
        return views
    return tuple(
        view.model_copy(update={"value": float(settled.value)}) if view is counted[0] else view
        for view in views
    )


def unlocated_boxes(drawing: Drawing) -> dict[tuple[int, Box], str]:
    """The (page, box) of each element a second reader counted with no position of its own
    (`attrs.located` false: decide's count swap gives it the plan's box), with its class. A box a
    located element has too is not in it."""
    located = {(e.page, e.box) for e in drawing.elements if e.attrs.get("located") is not False}
    return {
        (e.page, e.box): e.class_
        for e in drawing.elements
        if e.attrs.get("located") is False and (e.page, e.box) not in located
    }


def unlocated(quantity: Quantity, drawing: Drawing) -> dict[str, int]:
    """How many of the quantity's counted marks have no position of their own, per class."""
    unplaced = unlocated_boxes(drawing)
    found: dict[str, int] = {}
    for mark in quantity.marks:
        if (name := unplaced.get((mark.page, mark.box))) is not None:
            found[name] = found.get(name, 0) + 1
    return found


def current_value(quantity: Quantity, views: Sequence[MarkView], state: ReviewState) -> int | float:
    key = quantity.key
    if key in state.settled:
        return _typed(quantity, state.settled[key].value)
    included = set(state.included.get(key, ()))
    changed = [view for view in views if view.state in ("rejected", "added") or view.id in included]
    if not changed or any(view.value is None for view in changed):
        return quantity.value
    delta = sum((view.value or 0.0) * (-1 if view.state == "rejected" else 1) for view in changed)
    return _typed(quantity, quantity.value + delta)


def row(quantity: Quantity, drawing: Drawing, state: ReviewState, rules: Mapping[str, str]) -> Row:
    views = mark_views(quantity, drawing, state)
    measure, subject, scope = parse_key(quantity.key)
    disputed = quantity.conflict
    measured = disputed or quantity.agree
    first = second = None
    if measured is not None:
        first, second = (MethodValue(method=v.method, value=v.value) for v in measured.values[:2])
    return Row(
        key=quantity.key,
        label=label(quantity.key),
        measure=measure,
        subject=subject,
        scope=scope,
        value=current_value(quantity, views, state),
        unit=quantity.unit,
        original_value=quantity.value,
        status=status(quantity, state),
        needs_person=needs_person(quantity, state),
        rule=RuleText(id=quantity.rule, text=rules.get(quantity.rule, quantity.rule)),
        estimate=quantity.estimate,
        first=first,
        second=second,
        conflict=disputed,
        settled=state.settled.get(quantity.key),
        marks=views,
        signed=state.signed.get(quantity.key),
        unlocated=unlocated(quantity, drawing),
    )


def status(quantity: Quantity, state: ReviewState) -> RowStatus:
    key = quantity.key
    if key in state.signed:
        return "signed"
    if quantity.conflict is not None and key not in state.settled:
        return "conflict"
    if quantity.estimate is not None and key not in state.settled:
        return "estimate"
    if any(
        edits.get(key) for edits in (state.settled, state.rejected, state.added, state.included)
    ):
        return "edited"
    return "single" if quantity.agree is None else "agree"


def needs_person(quantity: Quantity, state: ReviewState) -> bool:
    disputed = quantity.conflict
    return (
        disputed is not None and disputed.resolution is None and quantity.key not in state.settled
    )


def review_queue(rows: Sequence[Row]) -> list[str]:
    """The keys a surveyor should look at: methods disagree, or the value is an estimate."""
    return [found.key for found in rows if found.status in ("conflict", "estimate")]


def quantity_of(quantities: Mapping[str, Quantity], key: str | None) -> Quantity:
    if key is None:
        raise InvalidInputError("this edit needs the quantity it is about")
    found = quantities.get(key)
    if found is None:
        raise NotFoundError(f"the takeoff has no quantity {key!r}")
    return found


def reset(state: ReviewState, key: str | None) -> ReviewState:
    """Every edit, settled value and sign-off of one quantity, or of all (`key` None), undone."""
    if key is None:
        return ReviewState()
    return ReviewState(
        rejected={name: found for name, found in state.rejected.items() if name != key},
        added={name: found for name, found in state.added.items() if name != key},
        settled={name: found for name, found in state.settled.items() if name != key},
        signed={name: found for name, found in state.signed.items() if name != key},
        included={name: found for name, found in state.included.items() if name != key},
    )


def apply(
    state: ReviewState, edit: Edit, quantity: Quantity, drawing: Drawing, at: str
) -> ReviewState:
    """The state after one edit of `quantity`. A mark edit clears a settled value."""
    key = quantity.key
    if edit.action == "reset":
        return reset(state, key)
    if (signed := state.signed.get(key)) is not None:
        raise NotAllowedError(f"{key} is signed off by {signed.by}; undo the sign-off first")
    rejected = dict(state.rejected)
    added = dict(state.added)
    settled = dict(state.settled)
    included = dict(state.included)
    match edit.action:
        case "reject" | "restore":
            mark = _mark_id(edit)
            mine = added.get(key, ())
            if any(found.id == mark for found in mine):
                if edit.action == "reject":
                    added[key] = tuple(found for found in mine if found.id != mark)
            elif _numbered(mark, "x", len(quantity.excluded)):
                kept = [found for found in included.get(key, ()) if found != mark]
                included[key] = (*kept, mark) if edit.action == "restore" else tuple(kept)
            elif not _numbered(mark, "m", len(quantity.marks)):
                raise NotFoundError(f"{key} has no mark {mark!r}")
            else:
                kept = [found for found in rejected.get(key, ()) if found != mark]
                rejected[key] = (*kept, mark) if edit.action == "reject" else tuple(kept)
            settled.pop(key, None)
        case "add":
            if quantity.unit != "count":
                raise InvalidInputError(f"marks are added to counts only, and {key} is a sum")
            if edit.page is None or edit.box is None:
                raise InvalidInputError("add needs the page and box of the mark")
            if edit.page > len(drawing.pages):
                raise InvalidInputError(f"the drawing has no page {edit.page} to add a mark on")
            mine = added.get(key, ())
            number = 1 + max((int(found.id[1:]) for found in mine), default=0)
            added[key] = (*mine, Added(id=f"a{number}", page=edit.page, box=edit.box))
            settled.pop(key, None)
        case "settle":
            if edit.value is None:
                raise InvalidInputError("settle needs the value to keep")
            settled[key] = Settled(value=_typed(quantity, edit.value), at=at)
    return ReviewState(
        rejected={name: marks for name, marks in rejected.items() if marks},
        added={name: marks for name, marks in added.items() if marks},
        settled=settled,
        signed=state.signed,
        included={name: marks for name, marks in included.items() if marks},
    )


def sign(state: ReviewState, quantity: Quantity, drawing: Drawing, by: str, at: str) -> ReviewState:
    """Signs off the quantity's current value; a conflict no rule decides is settled first."""
    if needs_person(quantity, state):
        raise NotAllowedError(
            f"{quantity.key}: the methods disagree and no rule decides; settle it before signing"
        )
    value = current_value(quantity, mark_views(quantity, drawing, state), state)
    signed = {**state.signed, quantity.key: SignOff(by=by, at=at, value=value)}
    return state.model_copy(update={"signed": signed})


def unsign(state: ReviewState, key: str) -> ReviewState:
    signed = {name: found for name, found in state.signed.items() if name != key}
    return state.model_copy(update={"signed": signed})


def _items(drawing: Drawing) -> dict[tuple[int, Box], Item]:
    found: dict[tuple[int, Box], Item] = {}
    for element in drawing.elements:
        found[element.page, element.box] = (element.id, element.class_, element.polygon, None)
    for room in drawing.rooms:
        name = room.label if room.label else room.type
        found[room.page, room.box] = (room.id, name, room.polygon, room.area_m2)
    return found


def _typed(quantity: Quantity, value: float) -> int | float:
    return round(value) if quantity.unit == "count" else round(value, 3)


def _mark_id(edit: Edit) -> str:
    if edit.mark is None:
        raise InvalidInputError(f"{edit.action} needs the id of the mark")
    return edit.mark


def _numbered(mark: str, prefix: str, count: int) -> bool:
    """`mark` is `<prefix><n>` with n in 1..count."""
    return mark.startswith(prefix) and mark[1:].isdigit() and 1 <= int(mark[1:]) <= count

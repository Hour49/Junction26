"""R4-F5: answers read a drawing as drawn; an accepted plan edit is kept with the chat, not
applied to the drawing (app/api/chat.py `decide`). So an answer the edit can change (a room's
area, the number of rooms, walls) on a drawing the chat has an accepted edit on says so, and a
room the edit changed gets its area with the edit, from the proposal's own labels and numbers.
Without this the drawn area reads as if the edit was lost. A door, window or fixture count gets
nothing. Pure."""

from collections.abc import Iterable, Mapping
from typing import Any, cast

from app.core.agent.model import ChatTurn
from app.core.plan_edit.model import Proposal

CHANGED_BY_EDITS = ("room", "wall")  # the subjects of the quantities a plan edit can change


def with_accepted_edits(turn: ChatTurn, proposals: Mapping[str, Proposal]) -> ChatTurn:
    """`turn` with one sentence per accepted plan edit on a drawing whose room or wall
    quantities its answers give, or as it was. Only an answer turn: an edit turn shows its own
    proposal."""
    if turn.kind not in ("answer", "conflict"):
        return turn
    accepted = [
        p
        for p in proposals.values()
        if p.state == "accepted" and p.services_change is None and (p.rooms or p.removed)
    ]
    parts = [part for answer in turn.answers for part in _parts(answer)]
    notes: list[str] = []
    for proposal in accepted:
        mine = [
            part
            for part in parts
            if part.get("drawing_id") == proposal.drawing_id and _changes(part, proposal)
        ]
        if not mine:
            continue
        note = f"As drawn; the plan edit you accepted ({_what(proposal)}) isn't applied to answers"
        changed = _changed_rooms(mine, proposal)
        if changed:
            note += "; with it, " + "; ".join(changed)
        notes.append(note + ".")
    if not notes:
        return turn
    return turn.model_copy(update={"text": f"{turn.text.rstrip()} {' '.join(notes)}"})


def _parts(answer: Any) -> Iterable[dict[str, Any]]:
    """An answer card's per-drawing parts (ask_drawings), each with its drawing id."""
    return _dicts(_dict(answer).get("parts"))


def _changes(part: dict[str, Any], proposal: Proposal) -> bool:
    """Whether the edit can change the part's quantity: a room's area only when the room is one
    the edit changes; the number of rooms and the walls always."""
    quantity = _quantity(part)
    if quantity.get("subject") not in CHANGED_BY_EDITS:
        return False
    if quantity.get("measure") == "area" and quantity.get("subject") == "room":
        return bool(_changed_rooms([part], proposal))
    return True


def _quantity(part: dict[str, Any]) -> dict[str, Any]:
    return _dict(_dict(part.get("answer")).get("quantity"))


def _what(proposal: Proposal) -> str:
    """The edit by what it did, in its own labels: the rooms it changes, else what it removed
    and added."""
    if proposal.rooms:
        return "; ".join(room.label for room in proposal.rooms)
    return "; ".join(item.label for item in (*proposal.removed, *proposal.added))


def _dict(value: Any) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def _dicts(value: Any) -> list[dict[str, Any]]:
    items = cast(list[Any], value) if isinstance(value, list) else []
    return [_dict(item) for item in items if isinstance(item, dict)]


def _changed_rooms(parts: list[dict[str, Any]], proposal: Proposal) -> list[str]:
    """Once per room change the parts' room areas count (by the room ids the proposal names):
    one room, "Bagno 1.01 is part of Bagno 1.01 + Stanza 1.02: 21.02 m²"; a total over all of
    the change's rooms, the total with the edit, "the total is 21.02 m² (Bagno 1.01 + Stanza
    1.02: 21.02 m²)"; a total over only some of them, the changed room once."""
    said: list[str] = []
    for part in parts:
        quantity = _quantity(part)
        if quantity.get("measure") != "area" or quantity.get("subject") != "room":
            continue
        marks = [m for m in _dicts(quantity.get("marks")) if m.get("state", "counted") == "counted"]
        for change in proposal.rooms:
            mine = [m for m in marks if str(m.get("ref") or "") in (*change.was, change.id)]
            if not mine:
                continue
            after = f"{change.label}: {_m2(change.area_after_m2)} m²"
            value = quantity.get("value")
            if len(marks) == 1:
                name = _room_name(mine[0], change.label)
                text = f"{name} is part of {after}" if len(change.was) > 1 else after
            elif isinstance(value, int | float) and {str(m.get("ref")) for m in mine} >= set(
                change.was or (change.id,)
            ):
                drawn = sum(float(m.get("value") or 0.0) for m in mine)
                total = float(value) - drawn + change.area_after_m2
                text = f"the total is {_m2(total)} m² ({after})"
            else:
                text = f"{change.label} is one room of {_m2(change.area_after_m2)} m²"
            if text not in said:
                said.append(text)
    return said


def _m2(value: float) -> str:
    """An area as the answer prints its own (1159.67, 21.02, 9): no thousands separator."""
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _room_name(mark: dict[str, Any], merged: str) -> str:
    """The room as the edit's label names it ("Bagno 1.01"), else the mark's label."""
    label = str(mark.get("label") or "")
    return next((part for part in merged.split(" + ") if label and part.startswith(label)), label)

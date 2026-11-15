"""R4-F5: answers read a drawing as drawn; an accepted plan edit is kept with the chat, not
applied to the drawing (app/api/chat.py `decide`). So an answer on a drawing the chat has an
accepted edit on says so, and a room the edit changed gets its area with the edit, from the
proposal's own numbers. Without this the drawn area reads as if the edit was lost. Pure."""

from collections.abc import Iterable, Mapping
from typing import Any, cast

from app.core.agent.model import ChatTurn
from app.core.plan_edit.model import Proposal


def with_accepted_edits(turn: ChatTurn, proposals: Mapping[str, Proposal]) -> ChatTurn:
    """`turn` with one sentence per accepted plan edit on a drawing its answers read, or as it
    was. Only an answer turn: an edit turn shows its own proposal."""
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
        mine = [part for part in parts if part.get("drawing_id") == proposal.drawing_id]
        if not mine:
            continue
        note = f"As drawn. Your accepted edit {proposal.proposal_id} is not applied to answers"
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


def _dict(value: Any) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def _dicts(value: Any) -> list[dict[str, Any]]:
    items = cast(list[Any], value) if isinstance(value, list) else []
    return [_dict(item) for item in items if isinstance(item, dict)]


def _changed_rooms(parts: list[dict[str, Any]], proposal: Proposal) -> list[str]:
    """For each room area the parts answer that the edit merged or changed (by the room ids the
    proposal names): "Bagno 1.01 is part of Bagno 1.01 + Stanza 1.02: 21.02 m²"."""
    said: list[str] = []
    for part in parts:
        quantity = _dict(_dict(part.get("answer")).get("quantity"))
        if quantity.get("measure") != "area" or quantity.get("subject") != "room":
            continue
        for mark in _dicts(quantity.get("marks")):
            ref = str(mark.get("ref") or "")
            change = next(
                (c for c in proposal.rooms if ref and (ref in c.was or ref == c.id)), None
            )
            if change is None:
                continue
            name = _room_name(mark, change.label)
            text = (
                f"{name} is part of {change.label}: {change.area_after_m2:g} m²"
                if len(change.was) > 1
                else f"{change.label} is {change.area_after_m2:g} m²"
            )
            if text not in said:
                said.append(text)
    return said


def _room_name(mark: dict[str, Any], merged: str) -> str:
    """The room as the edit's label names it ("Bagno 1.01"), else the mark's label."""
    label = str(mark.get("label") or "")
    return next((part for part in merged.split(" + ") if label and part.startswith(label)), label)

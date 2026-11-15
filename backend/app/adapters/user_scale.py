"""USER_SCALE in the agent chat: the scales a chat's user gave, and the drawings they apply to.

A chat's scales live in memory (`UserScales`, on app.state), by chat id then drawing id: never in
the chat store or the drawing store, so a restart forgets them (the user says it again).
`take_scale` reads one message: when it states a scale, it finds the drawing (the selection's,
else the one drawing the room or ratio fits) and keeps the scale for the chat, and gives the
lines the model reads about it. `ScaledIngest` is the ingest the chat's tools read through: a
drawing with a scale from the user comes back re-measured at it
(app/core/pipeline/user_scale.py).
"""

import re
import threading
from collections.abc import Mapping, Sequence
from typing import Any

import pypdfium2

from app.adapters.pdfium_lock import PDFIUM
from app.adapters.printed_scale import stated_dpi
from app.api.views import drawings_of
from app.core.drawing.model import Drawing, Page, Room, Scale
from app.core.errors import DomainError
from app.core.ingest.model import ProjectStatus
from app.core.pipeline.printed import trusted_dpi
from app.core.pipeline.user_scale import (
    POINTS_PER_INCH,
    Given,
    parse_given,
    rooms_named,
    user_scale,
    why_not,
    with_user_scale,
)
from app.core.plan_edit.model import Selection


class UserScales:
    """Every chat's scales from its user, by chat id then drawing id (in memory only)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._chats: dict[str, dict[str, Scale]] = {}

    def of(self, chat_id: str) -> dict[str, Scale]:
        with self._lock:
            return dict(self._chats.get(chat_id, {}))

    def put(self, chat_id: str, drawing_id: str, scale: Scale) -> None:
        with self._lock:
            self._chats.setdefault(chat_id, {})[drawing_id] = scale


class ScaledIngest:
    """`ingest` with the user's scale applied to the drawings in `scales`; the rest as it is."""

    def __init__(self, ingest: Any, scales: Mapping[str, Scale]) -> None:
        self._ingest = ingest
        self._scales = dict(scales)

    def drawing(self, drawing_id: str) -> Drawing:
        found: Drawing = self._ingest.drawing(drawing_id)
        scale = self._scales.get(drawing_id)
        return found if scale is None else with_user_scale(found, scale)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._ingest, name)


def take_scale(
    message: str,
    selection: Sequence[Selection],
    ingest: Any,
    status: ProjectStatus,
    names: Mapping[str, str],
    keep: Any,
) -> str:
    """When `message` states a scale: find its drawing, keep the scale (`keep(drawing_id,
    scale)`), and give the lines the model reads (what was kept, or why not, in words to pass
    on); "" when the message states none. A drawing the message names ("the study on Plan
    image 5 is 4.9 m wide") is the one it is for, and its name is no part of the room's."""
    only, message = _drawing_named(message, names)
    given = parse_given(message)
    if given is None:
        return ""
    found = _target(given, selection, ingest, status, names, only)
    if isinstance(found, str):
        return _line(f"The user stated a scale ({given.text}), but I could not use it: {found}.")
    drawing_id, drawing, room = found
    scale = user_scale(drawing, given, room, _units_per_inch(ingest, drawing_id, drawing.pages))
    name = names.get(drawing_id, drawing_id)
    if isinstance(scale, str):
        return _line(f"The user stated a scale for {name} ({given.text}), not used: {scale}.")
    keep(drawing_id, scale)
    return _line(
        f"The user gave the scale of {name}: {given.text}. Its areas and lengths are now measured "
        "with it; ask_drawings answers them. Say any such number is measured using the scale "
        "the user gave, never that it is sure."
    )


def _target(
    given: Given,
    selection: Sequence[Selection],
    ingest: Any,
    status: ProjectStatus,
    names: Mapping[str, str],
    only: str | None = None,
) -> tuple[str, Drawing, Room | None] | str:
    """The drawing (and room) the scale is for, or why none is: the drawing the message names
    (`only`), else the selection's drawing, else the one drawing that takes a scale and fits
    (the room named, or any for a ratio)."""
    if only is not None:
        drawing = _drawing(ingest, only)
        if drawing is None:
            return f"{names.get(only, only)} was not read"
        if (reason := why_not(drawing)) is not None:
            return f"{names.get(only, only)}: {reason}"
        if given.kind == "ratio":
            return only, drawing, None
        return _named(given, [(only, drawing)], names)
    chosen = [s for s in selection if s.kind == "room"] or list(selection)
    if chosen:
        pick = chosen[0]
        drawing = _drawing(ingest, pick.drawing_id)
        if drawing is None:
            return "the selected drawing was not read"
        if (reason := why_not(drawing)) is not None:
            return f"{names.get(pick.drawing_id, pick.drawing_id)}: {reason}"
        if given.kind == "ratio":
            return pick.drawing_id, drawing, None
        if pick.kind == "room" and pick.ref is not None and _says_this(given.room):
            room = next((r for r in drawing.rooms if r.id == pick.ref), None)
            if room is not None:
                return pick.drawing_id, drawing, room
        return _named(given, [(pick.drawing_id, drawing)], names)
    open_ = []
    for entry in drawings_of(status):
        drawing = _drawing(ingest, entry.drawing_id)
        if drawing is not None and why_not(drawing) is None:
            open_.append((entry.drawing_id, drawing))
    if not open_:
        return "no drawing of this project is without a scale of its own"
    if given.kind == "ratio":
        if len(open_) > 1:
            listed = ", ".join(names.get(d, d) for d, _ in open_)
            return (
                f"several drawings have no scale ({listed}); select the one it is for on the plan"
            )
        drawing_id, drawing = open_[0]
        return drawing_id, drawing, None
    return _named(given, open_, names)


def _named(
    given: Given, drawings: Sequence[tuple[str, Drawing]], names: Mapping[str, str]
) -> tuple[str, Drawing, Room | None] | str:
    room_name = given.room or ""
    if _says_this(room_name):
        return "name the room (as printed, or its type), or select it on the plan"
    found = [
        (d, drawing, room) for d, drawing in drawings for room in rooms_named(drawing, room_name)
    ]
    if not found:
        return f"no room fits '{room_name}' on a drawing without a scale"
    if len(found) > 1:
        labels = ", ".join(
            f"{room.label or room.type} on {names.get(d, d)}" for d, _, room in found[:6]
        )
        return f"{len(found)} rooms fit '{room_name}' ({labels}); select the one you mean"
    return found[0]


def _drawing_named(message: str, names: Mapping[str, str]) -> tuple[str | None, str]:
    """The drawing `message` names by its name in the project ("on Plan image 5"; the longest
    name first, so "Plan image 15" is not "Plan image 1"), and the message without that name
    and the word before it (on, in, of, for); (None, message) when it names none."""
    for drawing_id, name in sorted(names.items(), key=lambda item: -len(item[1])):
        if not name.strip():
            continue
        named = re.compile(
            rf"(?:\s+(?:on|in|of|for)(?:\s+the)?)?\s*(?<!\w){re.escape(name)}(?!\w)", re.IGNORECASE
        )
        if found := named.search(message):
            return drawing_id, f"{message[: found.start()]} {message[found.end() :]}".strip()
    return None, message


def _says_this(name: str | None) -> bool:
    words = (name or "").lower().split()
    return not words or (words[0] in ("this", "that") and len(words) <= 2)


def _drawing(ingest: Any, drawing_id: str) -> Drawing | None:
    try:
        return ingest.drawing(drawing_id)
    except DomainError:
        return None


def _units_per_inch(ingest: Any, drawing_id: str, pages: Sequence[Page]) -> float | None:
    """Page units per inch of paper: 72 on a PDF page in points; on a page in pixels, the scan's
    render resolution (a scanned PDF) or the resolution its image file states, if trusted."""
    if not pages:
        return None
    if all(page.unit == "pt" for page in pages):
        return POINTS_PER_INCH
    try:
        sheet = ingest.sheet(drawing_id)
    except DomainError:
        return None
    if sheet.kind != "pdf":
        return trusted_dpi(stated_dpi(sheet.data))
    with PDFIUM:
        document = pypdfium2.PdfDocument(sheet.data)
        try:
            width_pt = document[0].get_width()
        finally:
            document.close()
    return pages[0].width / (width_pt / POINTS_PER_INCH) if width_pt > 0 else None


def _line(text: str) -> str:
    return f"USER_SCALE: {text}"

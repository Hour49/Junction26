"""USER_SCALE: a scale the user gives in the chat, for a drawing whose scale we could not read.

A scan or an image with no printed scale refuses every area and length (or answers them on the
door estimate). The user may know better: "the scale is 1:100", "the kitchen is 12 m2", "this
room is 4.2 m wide". `parse_given` reads such a sentence, `user_scale` turns it into the
drawing's scale, and `with_user_scale` re-measures the drawing's rooms at it, so every area and
length on that drawing is answered "using the scale you gave". The value is the user's, not a
reading: the scale's status is `estimated` and its `source` says whose it is (`is_user_scale`),
so an answer never shows it as exact (and the chat never as sure, app/core/review/ask.py
`user_scaled`).

- A ratio needs the paper size: a PDF page in points (72 to the inch), or an image whose file
  states a resolution that can be trusted (the caller gives `units_per_inch`). An image without
  one has no paper size, so a ratio is refused there with what the user can say instead.
- A room's area gives the scale by the same outline the other rooms are measured with
  (raster_scale.rooms_with_areas: the polygon, else the box over BOX_RATIO), so the named room
  comes back at exactly the area given and the others in proportion.
- A room's width or length is its box's shorter or longer side.
"""

import math
import re

from app.core.drawing.model import Drawing, Room, Scale
from app.core.model import Frozen
from app.core.pipeline.raster_scale import (  # the one outline formula the rooms are measured by
    BOX_RATIO,
    OUTLINE_SPREAD,
    _shoelace,  # pyright: ignore[reportPrivateUsage]
    rooms_with_areas,
)

USER_SOURCE = "the scale you gave"  # how a user scale's `source` starts
INCH_M = 0.0254
POINTS_PER_INCH = 72.0
# What the user can type, said where an area or length is refused for want of a scale
HINT = (
    'You can give me the scale in the chat: one room\'s area ("the kitchen is 12 m2") or width '
    '("the kitchen is 3.2 m wide"), or on a PDF or scan page its printed ratio ("the scale is '
    "1:100\"), and I'll measure this drawing with it."
)
TAKES = ("no_scale", "estimated")  # the scale statuses a user scale replaces

_NUMBER = r"(?P<value>\d+(?:[.,]\d+)?)"
_ROOM = r"(?P<room>(?:[^\W\d_][\w'-]*\s+){0,4}?[^\W\d_][\w'-]*)"
_IS = r"\s+(?:is|=|has|measures|has an area of)\s+(?:about\s+|around\s+|roughly\s+)?"
# A message is read clause by clause: after . ! ? ; and a space, or a comma and a space ("12,5"
# and "4.2" stay whole); a clause that starts with a question word or ends with "?" asks
CLAUSE = re.compile(r"(?<=[.!?;])\s+|,\s+|\n")
ASKS = re.compile(
    r"^\W*(?:is|are|was|were|does|do|did|what|what's|whats|how|can|could|would|should|which|why|"
    r"where|when|who|isn't)\b",
    re.IGNORECASE,
)
ANY_RATIO = re.compile(r"\b1\s*:\s*(\d{1,5})\b")
RATIO = re.compile(r"\bscale\b[^0-9]{0,30}?\b1\s*:\s*(?P<ratio>\d{1,5})\b", re.IGNORECASE)
RATIO_FIRST = re.compile(r"\b1\s*:\s*(?P<ratio>\d{1,5})\b[^0-9]{0,10}?\bscale\b", re.IGNORECASE)
AREA = re.compile(
    _ROOM + _IS + _NUMBER + r"\s*(?:m2|m²|sqm|sq\.?\s?m\b|square\s+met(?:er|re)s?)",
    re.IGNORECASE,
)
SIDE = re.compile(
    _ROOM + _IS + _NUMBER + r"\s*(?:m|metres|meters)\s+(?P<side>wide|long)\b", re.IGNORECASE
)
# Words that name a room's type, for a room whose printed label is in another language
TYPE_WORDS: dict[str, str] = {
    "kitchen": "kitchen", "bedroom": "bedroom", "bathroom": "bathroom", "bath": "bathroom",
    "living": "living", "lounge": "living", "sauna": "sauna", "balcony": "balcony",
    "hall": "hall", "hallway": "hall", "corridor": "hall", "entrance": "hall",
    "storage": "storage", "closet": "storage", "toilet": "wc", "wc": "wc",
}  # fmt: skip
NOT_A_NAME = frozenset({"the", "this", "that", "room", "our", "my", "and", "think", "say", "know"})
WORD = re.compile(r"[^\W\d_]{2,}|\d+(?:\.\d+)?")


class Given(Frozen):
    """What the user said the scale is: a ratio 1:`value`, or a room's area (m²) or side (m)."""

    kind: str  # "ratio", "area" or "side"
    value: float
    room: str | None = None  # the room as the user named it ("the kitchen"); None: a ratio
    side: str | None = None  # "wide" or "long", for a side
    text: str  # the words the scale is quoted by in answers ("the kitchen is 12 m²")


def parse_given(message: str) -> Given | None:
    """The scale stated in `message`, or None when it states none. Read clause by clause: a
    clause that asks ("Is the scale 1:100?", "what does 1:100 mean?") states nothing, and a
    message naming two different ratios ("1:100 or 1:50") states no ratio."""
    ratios = {int(ratio) for ratio in ANY_RATIO.findall(message)}
    for clause in CLAUSE.split(message):
        if not clause.strip() or ASKS.search(clause) or clause.rstrip().endswith("?"):
            continue
        if (given := _stated(clause, len(ratios) == 1)) is not None:
            return given
    return None


def _stated(clause: str, one_ratio: bool) -> Given | None:
    for pattern in (RATIO, RATIO_FIRST):
        if found := pattern.search(clause):
            ratio = int(found["ratio"])
            if ratio >= 1 and one_ratio:
                return Given(kind="ratio", value=ratio, text=f"1:{ratio}")
            return None
    if found := SIDE.search(clause):
        value = _number(found["value"])
        if value > 0:
            room = found["room"].strip()
            text = f"{room} is {value:g} m {found['side'].lower()}"
            return Given(kind="side", value=value, room=room, side=found["side"].lower(), text=text)
    if found := AREA.search(clause):
        value = _number(found["value"])
        if value > 0:
            room = found["room"].strip()
            return Given(kind="area", value=value, room=room, text=f"{room} is {value:g} m²")
    return None


def room_words(name: str) -> list[str]:
    """The words of a room as the user named it that can match its label or type."""
    return [w for w in WORD.findall(name.lower()) if w not in NOT_A_NAME]


def rooms_named(drawing: Drawing, name: str) -> list[Room]:
    """The drawing's rooms the user's name fits: those whose printed label holds every word of
    it, else those of the one room type a word names (a Finnish "KEITTIÖ" is the kitchen)."""
    words = room_words(name)
    if not words:
        return []
    labelled = [
        room
        for room in drawing.rooms
        if set(words) <= set(WORD.findall((room.label or "").lower()))
    ]
    if labelled:
        return labelled
    types = {TYPE_WORDS[word] for word in words if word in TYPE_WORDS}
    if len(types) != 1:
        return []
    return [room for room in drawing.rooms if room.type in types]


def why_not(drawing: Drawing) -> str | None:
    """Why this drawing takes no scale from the user, or None when it does."""
    if not drawing.pages:
        return "it has no page to measure on (a building model has its own sizes)"
    if drawing.scale.status == "not_to_scale":
        return "the sheet says it is not to scale, so no one scale fits all of it"
    if drawing.scale.status not in TAKES:
        printed = f" ({drawing.scale.text})" if drawing.scale.text else ""
        return f"it prints its own scale{printed}, which I keep"
    return None


def user_scale(
    drawing: Drawing, given: Given, room: Room | None, units_per_inch: float | None
) -> Scale | str:
    """The drawing's scale from what the user gave, or why it gives none. `room`: the room the
    user named (an area or a side). `units_per_inch`: page units per inch of paper (72 on a PDF
    page, a trusted DPI on an image), None when the paper size is unknown."""
    if (reason := why_not(drawing)) is not None:
        return reason
    if given.kind == "ratio":
        if units_per_inch is None:
            return (
                "a ratio needs the paper size, and this image does not state one; give one "
                'room\'s area or width instead ("the kitchen is 12 m2")'
            )
        m_per_unit = given.value * INCH_M / units_per_inch
        return _scale(m_per_unit, given, None)
    if room is None:
        return "name the room on this drawing, or select it on the plan"
    page = next((page for page in drawing.pages if page.page == room.page), None)
    if page is None:
        return "the room is on no page of the drawing"
    x0, y0, x1, y1 = room.box
    if given.kind == "side":
        sides = sorted(((x1 - x0) * page.width, (y1 - y0) * page.height))
        side = sides[0] if given.side == "wide" else sides[1]
        if side <= 0:
            return "the room's outline has no size on the page"
        return _scale(given.value / side, given, None if room.polygon else OUTLINE_SPREAD / 2)
    if room.polygon is not None:
        share = _shoelace(room.polygon)
    else:
        share = (x1 - x0) * (y1 - y0) / BOX_RATIO
    units = share * page.width * page.height
    if units <= 0:
        return "the room's outline has no size on the page"
    spread = None if room.polygon else OUTLINE_SPREAD / 2
    return _scale(math.sqrt(given.value / units), given, spread)


def with_user_scale(drawing: Drawing, scale: Scale) -> Drawing:
    """The drawing at the user's scale: every room area measured from an outline is measured
    again at it (a printed area stays as printed); lengths follow the scale."""
    rooms = [_unmeasured(room) for room in drawing.rooms]
    measured, _ = rooms_with_areas(rooms, scale, drawing.pages)
    return drawing.model_copy(update={"scale": scale, "rooms": tuple(measured)})


def is_user_scale(scale: Scale) -> bool:
    return scale.status == "estimated" and (scale.source or "").startswith(USER_SOURCE)


def _unmeasured(room: Room) -> Room:
    if room.area_m2 is None or room.area_source not in ("geometry_x_scale", "geometry_x_estimate"):
        return room
    update = {"area_m2": None, "area_status": None, "area_source": None, "area_uncertainty": None}
    return room.model_copy(update=update)


def _scale(m_per_unit: float, given: Given, spread: float | None) -> Scale:
    return Scale(
        status="estimated",
        m_per_unit=m_per_unit,
        source=f"{USER_SOURCE}: {given.text}",
        uncertainty=None if spread is None else round(math.expm1(spread), 3),
    )


def _number(text: str) -> float:
    return float(text.replace(",", "."))

"""Printed room words on an image: the Swiss sheet's room names, and the Finnish labels.

A Swiss floor plan uploaded as an image is read by the image route's room reader, whose prompt is
written for Finnish plans: on `site980_bldg2055_floor9178.png` it read the label "Bagno 1.09"
right and typed the room `other` (think-acc, .agents/exp/certified-bathroom.md, 2026-11-14). The
drawn route types the same rooms by the name printed in them, with the table in
app/adapters/vector_pdf/swiss.py, and so does the Swiss gold.

- `swiss_label_rooms` (always on, the room policy every raster reading gets): a room whose label
  names a room in that table takes the table's type; the reader's type is kept in
  `attrs.retyped_from`.
- `room_word`: what a printed label names, for the answer check (CHECK_POLICY): the Swiss table
  first, flagged as a sheet the check policy was not measured on, then the Finnish table of the
  dev gold's labels (room_labels.json, without the OCR's learned entries: the share measured on
  CubiCasa val used this table alone).

The name in an image label is taken as the drawn reader takes it from the PDF's texts: the first
line that is not the room number, the unit label ("Whg. A") or an area. The image reader often
gives the number on the name's line ("Bain 4.03"), so a number is cut off a line first.
"""

import re
from collections.abc import Sequence

from app.adapters.raster_ocr import labels
from app.adapters.vector_pdf.swiss import NUMBER, UNIT_LABEL, room_type
from app.core.drawing.model import Room, RoomType
from app.core.review.check import RoomWord

NO_FILL = -1  # an image room has no fill grey: room_type then goes by the name alone
_NUMBER = re.compile(rf"\s*\b{NUMBER.pattern}$")


def swiss_name(label: str | None) -> str | None:
    """The room name printed in `label`, as the drawn route reads it, or None."""
    for line in (label or "").split("\n"):
        text = _NUMBER.sub("", line.strip()).strip()
        if text and not UNIT_LABEL.match(text) and "m²" not in text:
            return text
    return None


def swiss_type(label: str | None) -> RoomType | None:
    """The type the Swiss table gives the name in `label`; None when it names no room there."""
    name = swiss_name(label)
    if name is None:
        return None
    kind, _ = room_type(name, NO_FILL)
    return None if kind == "other" else kind


def swiss_label_rooms(rooms: Sequence[Room]) -> tuple[Room, ...]:
    """`rooms` with each room the Swiss table types by its label given that type; a retyped room
    keeps the reader's type in `attrs.retyped_from`. Nothing else changes, nor the order."""
    return tuple(_retyped(room, swiss_type(room.label)) for room in rooms)


def room_word(label: str) -> RoomWord | None:
    """What `label` names: a Swiss room (`unmeasured`: the check policy saw no such sheet) or a
    room of the Finnish gold table; None when it names neither."""
    if (kind := swiss_type(label)) is not None:
        return RoomWord(kind=kind, unmeasured=True)
    if (kind := labels.room_type(label, labels.annotated())) is not None:
        return RoomWord(kind=kind, unmeasured=False)
    return None


def _retyped(room: Room, kind: RoomType | None) -> Room:
    if kind is None or kind == room.type:
        return room
    return room.model_copy(
        update={"type": kind, "attrs": {**room.attrs, "retyped_from": room.type}}
    )

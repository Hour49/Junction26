"""Sauna rooms for a room source that has no sauna class of its own.

The room segmentation paints a sauna as an `other` room: CubiCasa5K's drawings give the sauna no
room type of its own, so the network never learned one. The sauna stove is drawn inside it, so
the `other` room that holds a stove is the sauna. The counting rule (one per sauna room, else the
stoves) then counts two stove boxes in one room once.

Measured on CubiCasa val with the all-local readers (stoves and rooms both from the segmentation
network): the sauna answers go from 96.3% to 98.2% exact, +1.8 pp [+0.4, +3.7], and the gap to
the hosted room reader's sauna rooms closes to -0.7 pp [-2.2, +0.7] (docs/EXPERIMENTS.md
section 6). On 226 of the 228 val pages with a detected stove, the best stove sits in a room the
network typed `other`.
"""

from collections.abc import Sequence

from app.core.drawing.model import Box, Room


def sauna_rooms(rooms: Sequence[Room], stoves: Sequence[Box]) -> tuple[Room, ...]:
    """`rooms` with each `other` room that holds a stove's centre retyped `sauna` (the reader's
    type is kept in `attrs.retyped_from`). A stove held by several `other` rooms goes to the
    smallest. Rooms of any other type, and the order, stay as they are."""
    saunas: set[int] = set()
    for stove in stoves:
        x, y = (stove[0] + stove[2]) / 2, (stove[1] + stove[3]) / 2
        holding = [
            (_area(room.box), index)
            for index, room in enumerate(rooms)
            if room.type == "other" and _holds(room, x, y)
        ]
        if holding:
            saunas.add(min(holding)[1])
    return tuple(
        room.model_copy(update={"type": "sauna", "attrs": {**room.attrs, "retyped_from": "other"}})
        if index in saunas
        else room
        for index, room in enumerate(rooms)
    )


def _area(box: Box) -> float:
    return (box[2] - box[0]) * (box[3] - box[1])


def _holds(room: Room, x: float, y: float) -> bool:
    """Whether the point is inside the room's outline (even-odd rule), or its box without one."""
    if room.polygon is None:
        x0, y0, x1, y1 = room.box
        return x0 <= x <= x1 and y0 <= y <= y1
    inside = False
    corners = room.polygon
    for (ax, ay), (bx, by) in zip(corners, (*corners[1:], corners[0]), strict=True):
        if (ay > y) != (by > y) and x < (bx - ax) * (y - ay) / (by - ay) + ax:
            inside = not inside
    return inside

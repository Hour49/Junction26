"""ROOM_POLICY=gold-labels: a room's type follows its printed label, as the dataset's answers do.

A room reader types a room by what it sees: the label when there is one, else the furniture (a
bed makes a bedroom). CubiCasa5K's answers type a room by its printed label alone, so on four
points the two disagree, and this policy takes the label's side. Each room gets the first rule
that fits; `label` is the first line of the room's label, upper-cased:

- a bedroom with no label is `other` (no printed label, no bedroom);
- a bedroom labelled ALK... (alkovi, a sleeping alcove) is a `hall`;
- a bathroom labelled WC is a `wc`;
- a room labelled APUK..., APK or TUPAK... (apukeittiö, tupakeittiö) is a `kitchen`.

Measured on config C's rooms, CubiCasa val: +0.6 pp of all questions [+0.3, +1.0]; the numbers per
rule, also on held-out train pages, are in docs/EXPERIMENTS.md section 5. It is for a reader that
reads the printed labels: one that gives no labels (a segmentation network) would lose every
bedroom to the first rule. The default, `furniture`, applies no policy: the reader's types stand.
"""

import re
from collections.abc import Sequence

from app.core.drawing.model import Room, RoomType

_WC = re.compile(r"WC\b")
_KITCHEN = re.compile(r"APUK|APK\b|TUPAK")


def gold_label_rooms(rooms: Sequence[Room]) -> tuple[Room, ...]:
    """`rooms` with each type the label overrules replaced; a retyped room keeps the reader's
    type in `attrs.retyped_from`. Nothing else about a room changes, nor the order."""
    return tuple(_retyped(room, _by_label(room)) for room in rooms)


def _by_label(room: Room) -> RoomType:
    label = (room.label or "").strip().upper().split("\n")[0].strip()
    if room.type == "bedroom" and not label:
        return "other"
    if room.type == "bedroom" and label.startswith("ALK"):
        return "hall"
    if room.type == "bathroom" and _WC.match(label):
        return "wc"
    if _KITCHEN.match(label):
        return "kitchen"
    return room.type


def _retyped(room: Room, kind: RoomType) -> Room:
    if kind == room.type:
        return room
    return room.model_copy(
        update={"type": kind, "attrs": {**room.attrs, "retyped_from": room.type}}
    )

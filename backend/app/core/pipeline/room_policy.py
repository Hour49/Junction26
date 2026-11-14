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

`generic_word_rooms` is not part of that setting: it is for every reading of an image. The image
route's room reader types a room whose label says only "room" a bedroom: "Rum" on a Swedish plan
(10 rooms on one sheet, answered "10 bedrooms"), "HUONE" and its abbreviation "H" on Finnish ones.
The label does not say which kind of room it is, and CubiCasa5K's answers type every room
labelled "H" `other` (1,034 of 1,034). On CubiCasa val the reader typed 71 such rooms a bedroom,
on 36 pages: the bedrooms read equal the answers' on 1 of those pages before the rule and on 33
after it.
"""

import re
import unicodedata
from collections.abc import Sequence

from app.core.drawing.model import Room, RoomType

_WC = re.compile(r"WC\b")
_KITCHEN = re.compile(r"APUK|APK\b|TUPAK")
# A label that says "room" and nothing else, by its letters: sv rum, fi huone (huon., h), en room.
GENERIC_WORDS = frozenset({"RUM", "HUONE", "HUON", "H", "ROOM"})


def gold_label_rooms(rooms: Sequence[Room]) -> tuple[Room, ...]:
    """`rooms` with each type the label overrules replaced; a retyped room keeps the reader's
    type in `attrs.retyped_from`. Nothing else about a room changes, nor the order."""
    return tuple(_retyped(room, _by_label(room)) for room in rooms)


def generic_word_rooms(rooms: Sequence[Room]) -> tuple[Room, ...]:
    """`rooms` with each bedroom whose label says only "room" typed `other`; a retyped room keeps
    the reader's type in `attrs.retyped_from`. The label's first line is read by its letters
    alone, so "Rum 3" and "HUON." say "room" and "Sovrum" and "Makuuhuone" do not."""
    return tuple(
        _retyped(room, "other") if room.type == "bedroom" and says_only_room(room.label) else room
        for room in rooms
    )


def says_only_room(label: str | None) -> bool:
    """Whether the label's first line is a word for "room" and nothing else."""
    return _letters(label) in GENERIC_WORDS


def _letters(label: str | None) -> str:
    """The letters of the label's first line, upper case, accents dropped."""
    first = unicodedata.normalize("NFKD", (label or "").strip().split("\n")[0])
    return "".join(c for c in first if c.isalpha()).upper()


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

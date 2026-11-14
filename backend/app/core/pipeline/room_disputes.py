"""Rooms to double-check: the places where independent room readers disagree about one room type.

An answer that counts rooms of a type ("how many bathrooms") comes from one reader's rooms. Other
readers saw the same sheet: a second room reader with outlines of its own (the room segmentation)
and the printed labels the text reader found. Where they contradict the counted rooms, a person
should look, and this lists those places:

- a counted room (`mark_id` is the room's id) that a reader contradicts: the second reader types
  the place differently or has no room there, the printed text inside names another type, the
  room's own label is not a label of the type, or it was typed from its furniture alone;
- a place the answer does not count (`mark_id` None) where both other readers see the type, or
  which the label policy retyped (`attrs.retyped_from`): a bedroom drawn with a bed and no
  printed label.

Nothing is fitted: every rule is one reader against another. Measured on CubiCasa val with this
function (993 room answers of config C1, 63 wrong; readers: the segmentation's rooms and the text
reader's labels): a person who settles only the listed places turns 35 of the 63 wrong answers
right, 813 of the 930 right answers list no place, and an answer with places has 1.2 on average,
4 at most. A model that types one room crop at a time was tried as a third reader: 38 of 63 and
793 of 930, not worth a model at runtime.
"""

import re
from collections.abc import Sequence
from typing import NamedTuple

from app.core.drawing.model import Box, Room, RoomType

LIMIT = 5  # places per answer a person can be asked to look at
OVERLAP = 0.3  # two rooms are the same place when this share of the smaller box is shared

# The printed tokens that name a type on Finnish and Swedish plans. A counted room whose label is
# none of them is a dispute between the reader's type and the label it read itself.
LABELS: dict[RoomType, re.Pattern[str]] = {
    "bedroom": re.compile(r"MH|MAK|SOV"),
    "kitchen": re.compile(r"K\b|KK\b|KT\b|KE\b|KEIT|KÖK|TUPAK|APUK|APK\b|AVOK"),
    "bathroom": re.compile(r"KH|KPH|PH\b|PSH|PESU|KYLPY|SH\b|SUIHKU|BAD"),
    "wc": re.compile(r"WC"),
    "balcony": re.compile(r"PARV|LASIT|LAS\b|BALK"),
}
NOUN: dict[RoomType, str] = {"wc": "separate WC"}


class Disputed(NamedTuple):
    """One place to look at. `readers`: what each reader says there, None where it says nothing."""

    mark_id: str | None
    page: int
    box: Box
    why: str
    readers: dict[str, str | None]


def room_disputes(
    kind: RoomType,
    rooms: Sequence[Room],
    *,
    second: Sequence[Room] | None = None,
    printed: Sequence[Room] | None = None,
    answer: int | None = None,
    limit: int = LIMIT,
) -> tuple[Disputed, ...]:
    """The disputed places for the count of `kind` rooms among `rooms`, strongest first, at most
    `limit`. `second` is another room reader's rooms and `printed` the text reader's labels as
    typed boxes (None: that reader did not run, which is not the same as finding nothing).
    `answer` is the count given when it is not the number of `kind` rooms (a prior answers
    "1 kitchen" whatever was read): every counted room is then a place to look at."""
    counted = [room for room in rooms if room.type == kind]
    found: list[tuple[int, Disputed]] = []
    for room in counted:
        ranked = _counted(kind, room, second, printed or (), second is None and printed is None)
        if ranked is None and answer is not None and answer != len(counted):
            ranked = _not_the_answer(kind, room, len(counted), answer)
        if ranked is not None:
            found.append(ranked)
    found.extend(_missed(kind, rooms, counted, second or (), printed or ()))
    found.sort(key=lambda ranked: ranked[0])
    return tuple(disputed for _, disputed in found[:limit])


def _counted(
    kind: RoomType,
    room: Room,
    second: Sequence[Room] | None,
    printed: Sequence[Room],
    alone: bool,
) -> tuple[int, Disputed] | None:
    """`alone`: no other reader ran, so "nobody confirms it" says nothing about the room."""
    noun = NOUN.get(kind, kind)
    label = _first_line(room)
    inside = [text for text in printed if _holds(room.box, text.box)]
    reads_same = any(text.type == kind for text in inside)
    reads_other = sorted({text.type for text in inside if text.type not in (kind, "other")})
    there = _at(room, second or (), kind)
    readers = {
        "reader": room.type,
        "label": label or None,
        "segmentation": there.type if there else None,
        "printed_label": kind if reads_same else (reads_other[0] if reads_other else None),
    }
    second_same = there is not None and there.type == kind

    def listed(rank: int, why: str) -> tuple[int, Disputed]:
        return rank, Disputed(room.id, room.page, room.box, why, readers)

    if second is not None and there is None and not reads_same:
        return listed(
            1,
            f"Counted as a {noun}, but the segmentation reader finds no room at this place: "
            "it may lie outside the flat.",
        )
    if there is not None and not second_same:
        return listed(
            1, f"Counted as a {noun}; the segmentation reader sees a {there.type} room here."
        )
    if reads_other and not reads_same:
        return listed(
            1,
            f"Counted as a {noun}, but the printed text read inside it names a {reads_other[0]}.",
        )
    if label and not LABELS[kind].match(label):
        return listed(
            2,
            f'Counted as a {noun}, but its printed label "{label}" is not a usual {noun} label.',
        )
    if not label and not (second_same or reads_same) and not alone:
        return listed(
            3,
            f"Counted as a {noun} from what is drawn in it; no printed label was read and no "
            "other reader confirms it.",
        )
    if not label:
        return listed(
            4,
            f"Counted as a {noun} from what is drawn in it; no printed label was read in the room.",
        )
    if not (second_same or reads_same) and not alone:
        return listed(
            5,
            f"Counted as a {noun} by one reader only; the segmentation and the text reader do "
            "not confirm it.",
        )
    return None


def _not_the_answer(kind: RoomType, room: Room, read: int, answer: int) -> tuple[int, Disputed]:
    noun = NOUN.get(kind, kind)
    readers = {
        "reader": room.type,
        "label": _first_line(room) or None,
        "segmentation": None,
        "printed_label": None,
    }
    why = f"{read} {noun} rooms were read on this page; the answer says {answer}."
    return 1, Disputed(room.id, room.page, room.box, why, readers)


def _missed(
    kind: RoomType,
    rooms: Sequence[Room],
    counted: Sequence[Room],
    second: Sequence[Room],
    printed: Sequence[Room],
) -> list[tuple[int, Disputed]]:
    """Places off the counted rooms where both other readers see the type, or the policy retyped."""
    noun = NOUN.get(kind, kind)
    off = [
        ("segmentation", room)
        for room in second
        if room.type == kind and not any(_same_place(room.box, other.box) for other in counted)
    ]
    off += [
        ("printed_label", text)
        for text in printed
        if text.type == kind and not any(_holds(other.box, text.box) for other in counted)
    ]
    groups: list[list[tuple[str, Room]]] = []
    for name, room in off:
        for group in groups:
            if any(_same_place(room.box, other.box) for _, other in group):
                group.append((name, room))
                break
        else:
            groups.append([(name, room)])
    found: list[tuple[int, Disputed]] = []
    seen: list[Box] = []
    for group in groups:
        names = {name for name, _ in group}
        if len(names) < 2:
            continue
        place = max(group, key=lambda pair: (pair[0] != "printed_label", _area(pair[1].box)))[1]
        under = _under(place, rooms)
        here = ""
        if under is not None:
            label = _first_line(under)
            here = f" The answer has a {under.type} room here" + (
                f' (label "{label}").' if label else "."
            )
        readers = {
            "reader": under.type if under else None,
            "label": (_first_line(under) or None) if under else None,
            "segmentation": kind,
            "printed_label": kind,
        }
        found.append(
            (
                1,
                Disputed(
                    None,
                    place.page,
                    place.box,
                    "Not counted: a printed label and the segmentation reader see "
                    f"a {noun} here.{here}",
                    readers,
                ),
            )
        )
        seen.append(place.box)
    for room in rooms:
        if room.attrs.get("retyped_from") != kind or room.type == kind:
            continue
        if any(_same_place(room.box, box) for box in seen):
            continue
        readers = {
            "reader": room.type,
            "label": _first_line(room) or None,
            "segmentation": None,
            "printed_label": None,
        }
        found.append(
            (
                4,
                Disputed(
                    None,
                    room.page,
                    room.box,
                    f"Not counted: this room looks like a {noun} from what is drawn in it, but no "
                    "printed label was read in it.",
                    readers,
                ),
            )
        )
    return found


def _under(place: Room, rooms: Sequence[Room]) -> Room | None:
    """The answer's room at an uncounted place, None when it has none there."""
    here = [room for room in rooms if _same_place(place.box, room.box)]
    return max(here, key=lambda room: _iou(place.box, room.box), default=None)


def _first_line(room: Room) -> str:
    return (room.label or "").strip().upper().split("\n")[0].strip()


def _area(box: Box) -> float:
    return (box[2] - box[0]) * (box[3] - box[1])


def _same_place(a: Box, b: Box) -> bool:
    width = min(a[2], b[2]) - max(a[0], b[0])
    height = min(a[3], b[3]) - max(a[1], b[1])
    smaller = min(_area(a), _area(b))
    return width > 0 and height > 0 and smaller > 0 and width * height / smaller >= OVERLAP


def _holds(box: Box, text: Box, pad: float = 0.005) -> bool:
    x, y = (text[0] + text[2]) / 2, (text[1] + text[3]) / 2
    return box[0] - pad <= x <= box[2] + pad and box[1] - pad <= y <= box[3] + pad


def _at(room: Room, others: Sequence[Room], kind: RoomType) -> Room | None:
    """What a reader has at `room`'s place: its `kind` room there when it has one (an open kitchen
    lies inside the living room's box, and the kitchen is the one that answers), else the room
    whose box matches best, None when no room of the reader shares the place."""
    here = [other for other in others if _same_place(room.box, other.box)]
    same = [other for other in here if other.type == kind]
    return max(same or here, key=lambda other: _iou(room.box, other.box), default=None)


def _iou(a: Box, b: Box) -> float:
    width = min(a[2], b[2]) - max(a[0], b[0])
    height = min(a[3], b[3]) - max(a[1], b[1])
    shared = max(width, 0.0) * max(height, 0.0)
    union = _area(a) + _area(b) - shared
    return shared / union if union > 0 else 0.0

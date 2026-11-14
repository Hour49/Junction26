"""Where a double-check request points (CHECK_POLICY's `Disputes` port): the dispute finders,
each for the kind of count it knows, on what the drawing keeps.

- a count of an element class, or a combined count of several (`shower+bathtub`): the counted
  elements against what each DOUBLE_CHECK_READERS reader saw (core/pipeline/disputed_marks.py,
  k = 1); nothing when no reader ran;
- windows: core/pipeline/window_panes.py, one place per window (the panes that may be one window
  are one place, pointing at the first of them), against the same readers, and its sentence with
  both counts (whole windows, panes); the detector's views one by one are not kept with the
  drawing, so they are not a reader here;
- a count of a room type: core/pipeline/room_disputes.py on the drawing's rooms; the second room
  reader and the printed labels as typed boxes are not kept with the drawing, so only the label
  rules run. For bedrooms, every counted bedroom with no printed label is listed first.

Only a count of the whole sheet (no storey, label or other filter) gets places: a filtered count's
marks are a part of the sheet the finders do not know.
"""

from collections.abc import Mapping, Sequence
from typing import cast, get_args

from app.core.drawing.model import ELEMENT_CLASSES, Drawing, Element, RoomType, words
from app.core.pipeline.disputed_marks import counted_elements, disputed_marks, reader_elements
from app.core.pipeline.room_disputes import room_disputes
from app.core.pipeline.rules import COMBINED
from app.core.pipeline.window_panes import request, window_panes
from app.core.review.check import LIMIT, UNLABELLED, Found, Place, unlabelled_bedrooms
from app.core.review.model import Row, Scope


def find_disputes(drawing: Drawing, row: Row) -> Found:
    """The places for `row`'s answer, strongest first, all of them (the request keeps five)."""
    if row.measure != "count" or row.scope != Scope():
        return Found()
    family = row.subject
    if family.startswith("room:"):
        kind = family.split(":", 1)[1]
        if kind not in get_args(RoomType):
            return Found()
        return Found(places=tuple(_rooms(drawing, row, cast(RoomType, kind))))
    readers = reader_elements(drawing, family)
    if family == "window":
        return _windows(drawing, row, readers)
    if not readers:
        return Found()
    parts = next((c.parts for c in COMBINED if c.key == family), (family,))
    noun = " or ".join(words(part) for part in parts if part in ELEMENT_CLASSES)
    marks = disputed_marks(counted_elements(drawing, family), readers, noun=noun, k=1, limit=None)
    return Found(
        places=tuple(
            Place(item_id=m.mark_id, page=m.page, box=m.box, why=m.why, readers=m.readers)
            for m in marks
        )
    )


def _windows(drawing: Drawing, row: Row, readers: Mapping[str, Sequence[Element]]) -> Found:
    """window_panes' places that point at a mark the person still has (or at no mark), and its
    sentence counting exactly the places the request lists."""
    counted = counted_elements(drawing, "window")
    found = window_panes(counted, (), readers, drawing.pages, limit=None)
    kept = {mark.ref for mark in row.marks if mark.state != "rejected" and mark.ref}
    shown = [p for p in found.places if p.mark_id is None or p.mark_id in kept]
    sentence = request(found.model_copy(update={"places": tuple(shown[:LIMIT])}))
    return Found(
        places=tuple(
            Place(item_id=p.mark_id, page=p.page, box=p.box, why=p.why, readers=p.readers)
            for p in shown
        ),
        reason=sentence,
    )


def _rooms(drawing: Drawing, row: Row, kind: RoomType) -> list[Place]:
    first = [
        Place(item_id=room.id, page=room.page, box=room.box, why=UNLABELLED,
              readers={"reader": "bedroom", "label": None})
        for room in unlabelled_bedrooms(row, drawing)
    ]  # fmt: skip
    listed = {place.item_id for place in first}
    answer = round(row.original_value)
    found = room_disputes(kind, drawing.rooms, answer=answer, limit=len(drawing.rooms) + 1)
    return first + [
        Place(item_id=d.mark_id, page=d.page, box=d.box, why=d.why, readers=d.readers)
        for d in found
        if d.mark_id is None or d.mark_id not in listed
    ]

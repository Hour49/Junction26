"""Rooms of the drawn flat only: a rooms reader's rooms whose centre is off region's predicted
mask (neighbouring flats, legends, title blocks) are left out (prototypes/ocr arm G4-regpred).

On val, G4's rooms kept on region's U-Net mask (R1-unet34) beat G4: +0.53 pp [+0.12, +0.98] of
all questions, bedrooms +4.1 pp, no family worse (.agents/exp/ocr.md). The rule is region's own
(`steps.keep_in_region`: a centre on a mask pixel of probability >= 0.5 is kept; a mask covering
no more than 2% of the page is a failed prediction and keeps every room), so rooms and elements
are cut by one region.

- `RegionRooms(inner, files, region)` wraps any rooms `Extractor` (the Gemini reader). Rooms the
  inner reader did not read stay unread; nothing else of its extraction changes.
- `SegmenterRegion(facts, session)` predicts the mask with region's model (`predict_mask`;
  data/models/region/<model>/, `load_region`); tests use a stand-in.
"""

import io
from typing import Protocol

import numpy as np
from PIL import Image

from app.adapters.raster_detector import Session, post
from app.adapters.raster_region import MIN_SHARE, RegionFacts, predict_mask, steps
from app.adapters.raster_region.steps import Det, Frame
from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from app.core.pipeline.ports import DrawingFiles, Extractor

NOT_A_ROOM = "\0plan"  # keep_in_region always keeps its plan class; no room is named this


class PageRegion(Protocol):
    def mask(self, page: Image.Image) -> tuple[np.ndarray, Frame]:
        """The drawn flat of an RGB page (`post.open_rgb`) as a boolean mask on its own square
        canvas, and how the page sits on that canvas."""
        ...


class SegmenterRegion:
    """Region's U-Net (`predict_mask`), facts and session from `load_region(folder)`."""

    def __init__(self, facts: RegionFacts, session: Session) -> None:
        self._facts = facts
        self._session = session

    def mask(self, page: Image.Image) -> tuple[np.ndarray, Frame]:
        return predict_mask(page, self._facts, self._session)


class RegionRooms:
    def __init__(self, inner: Extractor, files: DrawingFiles, region: PageRegion) -> None:
        self._inner = inner
        self._files = files
        self._region = region

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        found = self._inner.extract(source, sheet)
        if not found.rooms or (found.read is not None and "room" not in found.read):
            return found  # no rooms read: nothing to cut
        with Image.open(io.BytesIO(self._files.read(source.path))) as image:
            page = post.open_rgb(image)
        mask, mask_frame = self._region.mask(page)
        w, h = page.size
        on_page = Frame(side=max(w, h), width=w, height=h, new_width=w, new_height=h, dx=0, dy=0)
        dets = [
            Det(room.id, 1.0, (room.box[0] * w, room.box[1] * h, room.box[2] * w, room.box[3] * h))
            for room in found.rooms
        ]
        kept = {d.name for d in steps.keep_in_region(dets, on_page, mask, mask_frame,
                                                     NOT_A_ROOM, MIN_SHARE)}  # fmt: skip
        rooms = tuple(room for room in found.rooms if room.id in kept)
        note = f"region rooms: {len(rooms)} of {len(found.rooms)} rooms on the drawn flat"
        return found.model_copy(update={"rooms": rooms, "notes": (*found.notes, note)})

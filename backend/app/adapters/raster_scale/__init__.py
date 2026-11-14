"""`RASTER_SCALE=priors`: the raster route's reading gets an estimated scale and room areas.

`PriorScale(inner)` wraps the raster `Extractor` (the composite). A sheet the inner reader gives
`no_scale` gets the scale app/core/pipeline/raster_scale.py estimates from the doors the inner
reader detected (else the page size), status `estimated`, and every room without an area gets its
outline's area at that scale, `area_status` estimated. A sheet whose doors were not read keeps
`no_scale`, with a note saying why: area and length questions are then refused, never answered
from the page size behind the user's back. A scale the inner reader found is kept as it is.
"""

from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from app.core.pipeline.ports import Extractor
from app.core.pipeline.raster_scale import door_sides, estimate_scale, rooms_with_areas


class PriorScale:
    def __init__(self, inner: Extractor) -> None:
        self._inner = inner

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        found = self._inner.extract(source, sheet)
        if found.scale.status != "no_scale" or not sheet.pages:
            return found
        if found.read is not None and "door" not in found.read:
            note = "scale estimate: not made, the doors were not read"
            return found.model_copy(update={"notes": (*found.notes, note)})
        scale = estimate_scale(door_sides(found.elements, sheet.pages), sheet.pages[0])
        return found.model_copy(
            update={
                "scale": scale,
                "rooms": tuple(rooms_with_areas(found.rooms, scale, sheet.pages)),
                "notes": (*found.notes, f"scale estimate: {scale.source}"),
            }
        )

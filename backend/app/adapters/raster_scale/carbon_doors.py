"""`SCALE_CARBON_DOORS=on`: a raster sheet without a scale because the detector found no door gets
the door estimate from the Carbon reader's door boxes instead.

`CarbonDoorScale(inner)` wraps the reader that adds Carbon's elements (CarbonThings, which wraps
PriorScale, so PriorScale saw the detector's doors only). A sheet PriorScale left `no_scale` with
NO_DOOR gets app/core/pipeline/raster_scale.py `carbon_door_scale` over Carbon's door boxes, its
source saying the doors are Carbon's, and every room without an area its outline's area at it.
No Carbon door: the sheet stays as PriorScale left it (refused, with its note). Every other sheet
is passed through unchanged.
"""

from app.adapters.carbon.contract import SOURCE as CARBON
from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from app.core.pipeline.ports import Extractor
from app.core.pipeline.raster_scale import carbon_door_scale, door_sides, rooms_with_areas

NO_DOOR = "scale estimate: not made, no door was detected"  # PriorScale's note, word for word


class CarbonDoorScale:
    def __init__(self, inner: Extractor) -> None:
        self._inner = inner

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        found = self._inner.extract(source, sheet)
        if found.scale.status != "no_scale" or NO_DOOR not in found.notes or not sheet.pages:
            return found
        doors = [e for e in found.elements if e.attrs.get("reader") == CARBON]
        scale = carbon_door_scale(door_sides(doors, sheet.pages))
        if scale is None:
            return found
        return found.model_copy(
            update={
                "scale": scale,
                "rooms": tuple(rooms_with_areas(found.rooms, scale, sheet.pages)),
                "notes": (
                    *(note for note in found.notes if note != NO_DOOR),
                    f"scale estimate: {scale.source}",
                ),
            }
        )

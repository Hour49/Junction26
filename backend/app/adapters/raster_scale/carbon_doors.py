"""`SCALE_CARBON_DOORS=on`: a raster sheet without a scale because the detector found no door gets
the door estimate from the Carbon reader's door boxes instead.

`CarbonDoorScale(inner)` wraps the reader that adds Carbon's elements (CarbonThings, which wraps
PriorScale, so PriorScale saw the detector's doors only). A sheet PriorScale left `no_scale` with
NO_DOOR gets app/core/pipeline/raster_scale.py `carbon_door_scale` over Carbon's own door boxes,
its source saying the doors are Carbon's, and every room without an area its outline's area at it.
NO_DOOR also covers a detector that listed only doors under MIN_DOOR_SCORE; CarbonThings snaps a
Carbon door onto such a door's box, so a snapped door (`box_from` detector) is left out: the median
is over one kind of box, the kind CARBON_DOOR_M is for, and the source says "the detector found no
door it is sure of", true in both cases.
No Carbon door: the sheet stays as PriorScale left it (refused, with its note). Every other sheet
is passed through unchanged.
"""

from app.adapters.carbon.contract import SOURCE as CARBON
from app.core.drawing.model import Element
from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from app.core.pipeline.ports import Extractor
from app.core.pipeline.raster_scale import (
    carbon_door_scale,
    door_sides,
    label_area_checks,
    rooms_with_areas,
)

NO_DOOR = "scale estimate: not made, no door was detected"  # PriorScale's note, word for word


def snapped(door: Element) -> bool:
    """Whether CarbonThings put this Carbon door on a detector door's box (the opening, about a
    fifth of Carbon's box with its swing): such a box is not Carbon's and is not counted."""
    return door.attrs.get("box_from") == "detector"


class CarbonDoorScale:
    def __init__(self, inner: Extractor) -> None:
        self._inner = inner

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        found = self._inner.extract(source, sheet)
        if found.scale.status != "no_scale" or NO_DOOR not in found.notes or not sheet.pages:
            return found
        doors = [e for e in found.elements if e.attrs.get("reader") == CARBON and not snapped(e)]
        scale = carbon_door_scale(door_sides(doors, sheet.pages))
        if scale is None:
            return found
        rooms, refused = rooms_with_areas(found.rooms, scale, sheet.pages)
        checks, said = label_area_checks(found.rooms, scale, sheet.pages)  # as PriorScale
        return found.model_copy(
            update={
                "scale": scale,
                "rooms": tuple(rooms),
                "printed": (*found.printed, *checks),
                "notes": (
                    *(note for note in found.notes if note != NO_DOOR),
                    f"scale estimate: {scale.source}",
                    *refused,
                    *said,
                ),
            }
        )

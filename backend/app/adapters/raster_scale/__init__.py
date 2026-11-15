"""`RASTER_SCALE=priors`: the raster route's reading gets an estimated scale and room areas.

`PriorScale(inner)` wraps the raster `Extractor` (the composite). A sheet the inner reader gives
`no_scale` gets the scale app/core/pipeline/raster_scale.py estimates from the doors the inner
reader detected, status `estimated`, and every room without an area gets its outline's area at
that scale, `area_status` estimated. A sheet whose doors were not read, or where no door was
detected, keeps `no_scale` with a note saying why: area and length questions are then refused.
A scale the inner reader found is kept as it is. An area printed in a room's label that is far
from the room's outline at the estimated scale becomes a conflict (`label_area_checks`).
The estimate is a `prior_scale` step after the inner reader's steps (decision 0018): the scale it
found, or why none; `skipped` when it is not made (a scale was read, no page, doors not read). The
step is reporting only: what the sheet is read as is the same with or without it.
`carbon` (DOOR_PRIOR_BOXES=on): when every door counted is a box that Carbon reader drew itself
(none snapped onto a detector door, #310), the estimate takes Carbon's door width,
CARBON_DOOR_M, fitted on its boxes, not DOOR_M, fitted on the detector's (door_prior.py).
"""

from app.core.pipeline.door_prior import read_only_by
from app.core.pipeline.model import DrawingFile, Extracted, Sheet, StepTrace
from app.core.pipeline.ports import Extractor
from app.core.pipeline.raster_scale import (
    carbon_door_scale,
    door_sides,
    estimate_scale,
    label_area_checks,
    rooms_with_areas,
)
from app.core.pipeline.steps import now_ms
from app.core.wording import SCALE_WORDS

STEP_ID = "prior_scale"  # stable (docs/API.md); the ingest screen's "scale from door sizes"
LABEL = "Scale from door sizes"


# DOOR_PRIOR_BOXES=on: why a composite's own Carbon doors take Carbon's width (door_prior.py)
CARBON_READ = "no detector read the doors"


class PriorScale:
    def __init__(self, inner: Extractor, carbon: str | None = None) -> None:
        self._inner = inner
        self._carbon = carbon  # DOOR_PRIOR_BOXES=on: the Carbon reader's tag; None: DOOR_M always

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        found = self._inner.extract(source, sheet)
        if found.scale.status != "no_scale":
            said = f"not needed: {SCALE_WORDS[found.scale.status]}"
            return _with_step(found, _skipped(said))
        if not sheet.pages:
            return _with_step(found, _skipped("not made: the sheet has no page to measure"))
        if found.read is not None and "door" not in found.read:
            note = "scale estimate: not made, the doors were not read"
            found = found.model_copy(update={"notes": (*found.notes, note)})
            return _with_step(found, _skipped("not made: the doors were not read"))
        started = now_ms()
        sides = door_sides(found.elements, sheet.pages)
        carbon = self._carbon is not None and read_only_by(
            self._carbon, found.elements, sheet.pages
        )
        scale = carbon_door_scale(sides, CARBON_READ) if carbon else estimate_scale(sides)
        if scale is None:
            note = "scale estimate: not made, no door was detected"
            found = found.model_copy(update={"notes": (*found.notes, note)})
            return _with_step(found, _step("no scale: no door was detected", started))
        rooms, refused = rooms_with_areas(found.rooms, scale, sheet.pages)
        checks, said = label_area_checks(found.rooms, scale, sheet.pages)
        estimated = found.model_copy(
            update={
                "scale": scale,
                "rooms": tuple(rooms),
                "printed": (*found.printed, *checks),
                "notes": (*found.notes, f"scale estimate: {scale.source}", *refused, *said),
            }
        )
        return _with_step(estimated, _step(f"scale estimated: {scale.source}", started))


def _step(did: str, started: float) -> StepTrace:
    """The estimate as a step, from `started` (on `now_ms()`'s clock) to now."""
    ms = now_ms() - started
    return StepTrace(id=STEP_ID, label=LABEL, did=did, at_ms=started, ms=ms)


def _skipped(did: str) -> StepTrace:
    return StepTrace(id=STEP_ID, label=LABEL, did=did, at_ms=now_ms(), state="skipped")


def _with_step(found: Extracted, step: StepTrace) -> Extracted:
    return found.model_copy(update={"steps": (*found.steps, step)})

"""Decision 0018: the door-size scale estimate (RASTER_SCALE=priors) is a `prior_scale` step after
the inner reader's steps, and only a step: what the sheet is read as is the same as before it.
Synthetic."""

import pytest
from test_raster_composite import FILE, SHEET, Fake, element

from app.adapters.raster_scale import PriorScale
from app.core.drawing.model import Room, Scale
from app.core.pipeline.model import DrawingFile, Extracted, Sheet, StepTrace
from app.core.pipeline.ports import Extractor
from app.core.pipeline.raster_scale import (
    door_sides,
    estimate_scale,
    label_area_checks,
    rooms_with_areas,
)
from app.core.pipeline.steps import without_steps

DOOR = element("door", (0.1, 0.1, 0.3, 0.2))  # 8 px on the 40 x 30 sheet
LIVING = Room(id="r1", type="living", page=1, box=(0.0, 0.0, 0.5, 0.5))
PRINTED = Room(  # a label area far from its outline at the estimate: a conflict
    id="r2", type="bedroom", page=1, box=(0.5, 0.5, 1.0, 1.0), area_m2=90.0, area_source="printed"
)
INNER = StepTrace(id="detector", label="Symbol detector", ms=1)


def before(inner: Extractor, source: DrawingFile, sheet: Sheet) -> Extracted:
    """PriorScale.extract as it was before the step (origin/main 733ea951), word for word."""
    found = inner.extract(source, sheet)
    if found.scale.status != "no_scale" or not sheet.pages:
        return found
    if found.read is not None and "door" not in found.read:
        note = "scale estimate: not made, the doors were not read"
        return found.model_copy(update={"notes": (*found.notes, note)})
    scale = estimate_scale(door_sides(found.elements, sheet.pages))
    if scale is None:
        note = "scale estimate: not made, no door was detected"
        return found.model_copy(update={"notes": (*found.notes, note)})
    rooms, refused = rooms_with_areas(found.rooms, scale, sheet.pages)
    checks, said = label_area_checks(found.rooms, scale, sheet.pages)
    return found.model_copy(
        update={
            "scale": scale,
            "rooms": tuple(rooms),
            "printed": (*found.printed, *checks),
            "notes": (*found.notes, f"scale estimate: {scale.source}", *refused, *said),
        }
    )


def fake(**kwargs: object) -> Fake:
    made = Fake(**kwargs)  # type: ignore[arg-type]
    made.found = made.found.model_copy(update={"steps": (INNER,)})
    return made


def scaled() -> Fake:
    made = fake(elements=[DOOR])
    made.found = made.found.model_copy(
        update={"scale": Scale(status="scaled", m_per_unit=0.02, evidence=("scale_text",))}
    )
    return made


CASES = {
    "estimated": (lambda: fake(elements=[DOOR], rooms=[LIVING, PRINTED]), SHEET),
    "doors not read": (lambda: fake(rooms=[LIVING], read=["room"]), SHEET),
    "no door": (lambda: fake(rooms=[LIVING]), SHEET),
    "scale read": (scaled, SHEET),
    "no page": (lambda: fake(elements=[DOOR]), SHEET.model_copy(update={"pages": ()})),
}


@pytest.mark.parametrize("case", CASES)
def test_the_reading_is_the_same_with_or_without_the_step(case: str) -> None:
    make, sheet = CASES[case]
    got = PriorScale(make()).extract(FILE, sheet)
    assert without_steps(got) == without_steps(before(make(), FILE, sheet))
    assert got.steps[:-1] == (INNER,)  # the inner reader's steps first, as they are
    assert got.steps[-1].id == "prior_scale"


def test_the_estimate_says_the_scale_it_found() -> None:
    step = PriorScale(fake(elements=[DOOR], rooms=[LIVING])).extract(FILE, SHEET).steps[-1]
    assert (step.label, step.state) == ("Scale from door sizes", "done")
    assert step.did.startswith("scale estimated: a door is about 0.794 m wide; median of 1")
    assert step.at_ms > 0 and step.ms >= 0


@pytest.mark.parametrize(
    ("case", "state", "did"),
    [
        ("no door", "done", "no scale: no door was detected"),
        ("doors not read", "skipped", "not made: the doors were not read"),
        ("scale read", "skipped", "not needed: scale read from the sheet"),
        ("no page", "skipped", "not made: the sheet has no page to measure"),
    ],
)
def test_without_an_estimate_the_step_says_why(case: str, state: str, did: str) -> None:
    make, sheet = CASES[case]
    step = PriorScale(make()).extract(FILE, sheet).steps[-1]
    assert (step.state, step.did, step.ms) == (state, did, step.ms if state == "done" else 0)

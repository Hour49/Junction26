"""K5 (docs/KNOWN.md): an estimated raster scale whose detected doors disagree prints a band as
wide as their spread, or no estimate at all beyond REFUSE, instead of the prior's narrow band.
Synthetic door widths; the sheet of test_raster_composite."""

import math

import pytest
from test_raster_composite import FILE, SHEET, Fake, element
from test_raster_scale import PAGE

from app.adapters.raster_scale import PriorScale
from app.core.drawing.model import Room
from app.core.pipeline.raster_scale import (
    DISAGREE,
    REFUSE,
    SPREAD_FEW,
    SPREAD_MANY,
    door_spread,
    estimate_scale,
    rooms_with_areas,
)


def test_k5_doors_that_agree_keep_the_priors_band() -> None:
    assert door_spread([80.0, 90.0, 100.0]) < DISAGREE  # leaves vary about 10%: one kind of door
    assert door_spread([90.0]) == 0.0
    few, many = estimate_scale([80.0, 90.0, 100.0]), estimate_scale([90.0] * 13)
    assert few is not None and few.uncertainty == SPREAD_FEW
    assert many is not None and many.uncertainty == SPREAD_MANY
    assert "disagree" not in (many.source or "")


def test_k5_a_few_double_doors_move_neither_the_scale_nor_its_band() -> None:
    sides = [80.0, 82.0, 85.0, 88.0, 90.0, 150.0, 160.0, 170.0]  # 3 of 8 boxes span two leaves
    scale = estimate_scale(sides)
    assert scale is not None and scale.uncertainty == SPREAD_MANY


def test_k5_doors_that_disagree_widen_the_band_to_their_spread() -> None:
    sides = [60.0, 90.0, 120.0, 180.0, 90.0]
    spread = door_spread(sides)
    assert DISAGREE < spread <= REFUSE
    scale = estimate_scale(sides)
    assert scale is not None and scale.uncertainty == pytest.approx(math.expm1(spread), abs=1e-3)
    assert (scale.uncertainty or 0) > SPREAD_MANY and "widths disagree (±53%)" in (
        scale.source or ""
    )
    living = Room(id="r1", type="living", page=1, box=(0.0, 0.0, 0.5, 0.5))
    (room,) = rooms_with_areas([living], scale, [PAGE])
    narrow = rooms_with_areas([living], scale.model_copy(update={"uncertainty": SPREAD_MANY}),
                              [PAGE])[0]  # fmt: skip
    assert (room.area_uncertainty or 0) > (narrow.area_uncertainty or 0) > 0


def test_k5_doors_too_unlike_to_give_a_scale_refuse_with_the_reason() -> None:
    assert door_spread([90.0, 180.0]) > REFUSE
    assert estimate_scale([90.0, 180.0]) is None
    small, large = element("door", (0.1, 0.1, 0.3, 0.2)), element("door", (0.5, 0.5, 0.9, 0.6))
    living = Room(id="r1", type="living", page=1, box=(0.0, 0.0, 0.5, 0.5))
    found = PriorScale(Fake(elements=[small, large], rooms=[living])).extract(FILE, SHEET)
    assert found.scale.status == "no_scale" and found.rooms[0].area_m2 is None
    assert (
        found.notes[-1] == "scale estimate: not made, the 2 detected doors disagree (widths ±67%)"
    )

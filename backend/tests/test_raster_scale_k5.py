"""K5 (docs/KNOWN.md): the door scale's band is the 68% scale error of the page's door count group
and door-spread bucket (raster_scale.door_band), fitted by scripts/k5_band.py --fit; no spread
refuses a scale. Synthetic door widths and pages."""

import math
import statistics

import pytest
from test_raster_composite import FILE, SHEET, Fake, element

from app.adapters.raster_scale import PriorScale
from app.core.drawing.model import Page, Room
from app.core.pipeline import raster_scale as rs
from app.core.pipeline.raster_scale import SPREAD_FEW, SPREAD_MANY, door_spread, estimate_scale
from scripts import k5_band

AGREE = [88.0, 90.0, 92.0, 89.0, 91.0]  # one kind of door
DISAGREE = [60.0, 90.0, 120.0, 180.0, 90.0]  # spread about 0.44


def test_k5_doors_that_agree_keep_the_priors_band() -> None:
    assert door_spread([90.0]) == 0.0 and door_spread(AGREE) < rs.SPREAD_EDGES[0]
    few, many = estimate_scale([80.0, 90.0, 100.0]), estimate_scale(AGREE)
    assert few is not None and few.uncertainty == SPREAD_FEW
    assert many is not None and many.uncertainty == SPREAD_MANY
    assert "disagree" not in (many.source or "")


def test_k5_doors_that_disagree_still_give_a_scale_never_a_refusal() -> None:
    assert door_spread([90.0, 180.0]) > 0.5
    small, large = element("door", (0.1, 0.1, 0.3, 0.2)), element("door", (0.5, 0.5, 0.9, 0.6))
    living = Room(id="r1", type="living", page=1, box=(0.0, 0.0, 0.5, 0.5))
    found = PriorScale(Fake(elements=[small, large], rooms=[living])).extract(FILE, SHEET)
    assert found.scale.status == "estimated" and found.rooms[0].area_m2 is not None


def test_k5_the_band_is_the_page_s_spread_bucket_s(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rs, "BANDS_MANY", (0.06, 0.09, 0.25))
    assert rs.door_band(AGREE) == 0.06
    assert rs.door_band(DISAGREE) == 0.25
    scale = estimate_scale(DISAGREE)
    assert scale is not None and scale.uncertainty == 0.25
    assert "widths disagree" in (scale.source or "")
    assert rs.door_band([80.0, 90.0, 100.0]) == SPREAD_FEW  # 1-4 doors: BANDS_FEW


PAGE = Page(page=1, width=1000, height=1000, unit="px")
SQUARE = ((0.1, 0.1), (0.3, 0.1), (0.3, 0.3), (0.1, 0.3))  # 200 x 200 px


def sheet(sides: list[float], error: float) -> k5_band.Sheet:
    """A page whose door scale is off the gold by `error` (log): its one room's true area."""
    m = rs.DOOR_M / statistics.median(sides)
    room = Room(id="r1", type="living", page=1, box=(0.1, 0.1, 0.3, 0.3), polygon=SQUARE)
    return k5_band.Sheet("f", sides, (PAGE,), [room], [200 * 200 * m * m * math.exp(2 * error)])


def test_k5_fit_gives_a_spread_bucket_its_own_band_only_when_it_differs() -> None:
    errors = [0.01 * (i % 10) for i in range(40)]  # agreeing doors: 68% within 0.07
    wide = [0.05 * (i % 10) for i in range(40)]  # disagreeing doors: 68% within 0.35
    sheets = [sheet(AGREE, e) for e in errors] + [sheet(DISAGREE, e) for e in wide]
    assert sheets[3].error() == pytest.approx(0.03)
    a, b = sheets[::2], sheets[1::2]
    bands = k5_band.fit(a, b, rs.SPREAD_EDGES)
    few_main = SPREAD_FEW  # no page with 1-4 doors: main's band in every bucket
    assert bands["few"] == [few_main] * 3
    low, middle, high = bands["many"]
    assert low == pytest.approx(math.expm1(0.06), abs=0.02)
    assert high == pytest.approx(math.expm1(0.30), abs=0.06)
    assert low < middle < high  # the empty middle bucket takes the group's band


def test_k5_quantile_is_nearest_rank() -> None:
    assert k5_band.quantile([0.1 * i for i in range(1, 11)]) == pytest.approx(0.7)

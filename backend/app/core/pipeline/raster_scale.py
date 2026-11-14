"""An estimated scale for a raster plan that prints none, and the room areas it gives.

Ported from the areas track (prototypes/areas/scale_arms.py arm A-det; .agents/exp/areas.md).
Nothing printed is read here: the value rests on the detected doors, so the status is always
`estimated`, with the method in `source` and the 68% relative uncertainty.

- Door prior: a door leaf is DOOR_M metres; the scale is DOOR_M over the median long side (px) of
  the detected door boxes. DOOR_M is fitted on val (376 CubiCasa dev sheets, region:C-yolo26s-1536's
  ONNX doors at score >= 0.5): median 5.6% off the gold scale.
- The printed uncertainty depends on how many doors the median rests on: SPREAD_FEW below
  FEW_DOORS, else SPREAD_MANY, each the 68% quantile of the scale error, fitted on one half of val
  and checked on the other, both ways, then averaged (prototypes/areas/calibrate.py). One
  uncertainty for every sheet covered sheets with 1-4 doors only 41% of the time (held out).
- No door detected: no estimate. The page-size prior (a door is about 5% of the page's long side)
  is 37-72% off on 68% of such val sheets; an area off by that much is not an answer.
- A room's area is its outline's pixel area times the scale squared. A box (the raster room
  readers give boxes) is BOX_RATIO larger than the room's outline on val (Gemini G4-regpred boxes
  matched to gold rooms), so a box's area is divided by it; OUTLINE_SPREAD is that ratio's 68%
  log spread, combined with the scale's (twice, for an area) into `area_uncertainty`.
"""

import math
import statistics
from collections.abc import Sequence

from app.core.drawing.model import Element, Page, Room, Scale

DOOR_M = 0.794  # m, val (C-yolo26s-1536 ONNX doors, score >= 0.5)
MIN_DOOR_SCORE = 0.5  # the doors the prior was fitted on
FEW_DOORS = 5  # fewer detected doors than this print SPREAD_FEW
SPREAD_FEW = 0.158  # 68% relative scale error with 1-4 doors, val two-way
SPREAD_MANY = 0.0795  # with 5 or more doors
BOX_RATIO = 1.104  # a room's box area over its outline area, val median
OUTLINE_SPREAD = 0.157  # 68% |log| of that ratio around its median, val


def door_sides(elements: Sequence[Element], pages: Sequence[Page]) -> list[float]:
    """The long side, in page units, of each detected door the prior counts: a door box with a
    score of at least MIN_DOOR_SCORE (or none), not one added without a location of its own."""
    by_page = {page.page: page for page in pages}
    sides: list[float] = []
    for element in elements:
        score = element.attrs.get("score")
        if element.class_ != "door" or element.attrs.get("located") is False:
            continue
        if isinstance(score, int | float) and score < MIN_DOOR_SCORE:
            continue
        page = by_page.get(element.page)
        if page is None:
            continue
        x0, y0, x1, y1 = element.box
        sides.append(max((x1 - x0) * page.width, (y1 - y0) * page.height))
    return [side for side in sides if side > 0]


def estimate_scale(sides: Sequence[float]) -> Scale | None:
    """The scale from the door prior over `sides`; None without a door."""
    if not sides:
        return None
    return Scale(
        status="estimated",
        m_per_unit=DOOR_M / statistics.median(sides),
        source=f"door-leaf prior: a door is {DOOR_M} m, median of {len(sides)} detected doors",
        uncertainty=SPREAD_FEW if len(sides) < FEW_DOORS else SPREAD_MANY,
    )


def rooms_with_areas(rooms: Sequence[Room], scale: Scale, pages: Sequence[Page]) -> list[Room]:
    """Each room without an area gets its outline's area at `scale`, as an estimate. A room that
    has an area keeps it."""
    if scale.m_per_unit is None:
        return list(rooms)
    by_page = {page.page: page for page in pages}
    spread = math.hypot(2 * math.log1p(scale.uncertainty or 0.0), OUTLINE_SPREAD)
    out: list[Room] = []
    for room in rooms:
        page = by_page.get(room.page)
        if room.area_m2 is not None or page is None:
            out.append(room)
            continue
        if room.polygon is not None:
            share = _shoelace(room.polygon)
        else:
            x0, y0, x1, y1 = room.box
            share = (x1 - x0) * (y1 - y0) / BOX_RATIO
        area = share * page.width * page.height * scale.m_per_unit**2
        out.append(
            room.model_copy(
                update={
                    "area_m2": round(area, 2),
                    "area_status": "estimated",
                    "area_source": "geometry_x_estimate",
                    "area_uncertainty": round(math.expm1(spread), 3),
                }
            )
        )
    return out


def _shoelace(polygon: Sequence[tuple[float, float]]) -> float:
    pairs = zip(polygon, [*polygon[1:], polygon[0]], strict=True)
    return abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in pairs)) / 2

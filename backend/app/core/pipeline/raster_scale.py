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
- The doors' own spread (K5): when the detected door widths disagree, some boxes may not be door
  leaves (a double door, a wardrobe, a window). The band is the 68% scale error of the page's door
  count group and spread bucket (`door_spread`, the robust log spread of the widths, cut at
  SPREAD_EDGES): BANDS_FEW / BANDS_MANY, fitted with `scripts/k5_band.py --fit` (closest to 68%
  coverage, as narrow as that allows; half A checked on half B, both ways, averaged). No spread
  refuses a scale: an estimate main had inside its band stays an answer.
- No door detected: no estimate. The page-size prior (a door is about 5% of the page's long side)
  is 37-72% off on 68% of such val sheets; an area off by that much is not an answer.
- A room's area is its outline's pixel area times the scale squared. A box (the raster room
  readers give boxes) is BOX_RATIO larger than the room's outline on val (Gemini G4-regpred boxes
  matched to gold rooms), so a box's area is divided by it; OUTLINE_SPREAD is that ratio's 68%
  log spread, combined with the scale's (twice, for an area) into `area_uncertainty`.
"""

import bisect
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
SPREAD_EDGES = (0.10, 0.20)  # door width log spread buckets: < 0.10, 0.10-0.20, >= 0.20 (K5)
# The 68% relative scale error per spread bucket, with 1-4 doors and with 5 or more (K5).
# Bogdan's integ `k5_band.py --fit` (board #14, comment 6883082176): main's bands hold everywhere
# except 5+ doors with spread >= 0.20 (16 / 14 pages on halves A / B), where main's ±8% held only
# 44% / 50%; fitted ±14.2% / ±14.3%, checked on the other half 64% / 69%. Post-hoc choice: the
# pre-stated 15-page minimum said keep main's band there; widened anyway because both halves
# agree and the wider band moves toward the measured error (conservative). Others stay main's.
BANDS_FEW = (SPREAD_FEW, SPREAD_FEW, SPREAD_FEW)
BANDS_MANY = (SPREAD_MANY, SPREAD_MANY, 0.142)


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


def door_spread(sides: Sequence[float]) -> float:
    """The robust log spread of the door widths (a standard deviation's worth); 0 under two."""
    if len(sides) < 2:
        return 0.0
    middle = statistics.median(sides)
    return 1.4826 * statistics.median(abs(math.log(side / middle)) for side in sides)


def door_band(sides: Sequence[float]) -> float:
    """The 68% relative scale error of a page whose detected doors are `sides` (K5): its door
    count group's band in its spread bucket."""
    bands = BANDS_FEW if len(sides) < FEW_DOORS else BANDS_MANY
    return bands[bisect.bisect_right(SPREAD_EDGES, door_spread(sides))]


def estimate_scale(sides: Sequence[float]) -> Scale | None:
    """The scale from the door prior over `sides`; None without a door."""
    if not sides:
        return None
    band = door_band(sides)
    source = f"a door is about {DOOR_M} m wide; median of {len(sides)} detected doors"
    if band > (BANDS_FEW if len(sides) < FEW_DOORS else BANDS_MANY)[0]:  # K5: a wider bucket
        source += f", whose widths disagree (±{math.expm1(door_spread(sides)):.0%})"
    return Scale(
        status="estimated", m_per_unit=DOOR_M / statistics.median(sides), source=source,
        uncertainty=band,
    )  # fmt: skip


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
                    "area_source": (
                        "geometry_x_scale" if scale.status == "scaled" else "geometry_x_estimate"
                    ),
                    "area_uncertainty": round(math.expm1(spread), 3),
                }
            )
        )
    return out


def _shoelace(polygon: Sequence[tuple[float, float]]) -> float:
    pairs = zip(polygon, [*polygon[1:], polygon[0]], strict=True)
    return abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in pairs)) / 2

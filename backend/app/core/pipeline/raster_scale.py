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
- A box that cannot be the room gets no area (`refused_boxes`): a room reader sometimes boxes the
  room's printed label, not the room ("LOBBY 0.18 m²" on a 7.4 m² floor). A box narrower than a
  door (MIN_SIDE_M at the sheet's scale) is a label; so is every box on a page whose room boxes
  (MIN_COVER_ROOMS or more) cover under MIN_COVER of the box around them all, as scattered labels
  do. The room stays, its area unknown, the reason in a note; never a smaller number. The
  thresholds are harmless guards, not fitted values: on golden v2 they refuse 5 of 873 box rooms,
  0 of them right (eu-big's fit, #14 c6883029882); untested on scans (golden v2 has no scanned PDF
  with gold room areas). scripts/fit_label_boxes.py sweeps them per half on cached replies.
"""

import itertools
import math
import statistics
from collections.abc import Sequence

from app.core.drawing.model import Box, Element, Page, Room, Scale

DOOR_M = 0.794  # m, val (C-yolo26s-1536 ONNX doors, score >= 0.5)
MIN_DOOR_SCORE = 0.5  # the doors the prior was fitted on
FEW_DOORS = 5  # fewer detected doors than this print SPREAD_FEW
SPREAD_FEW = 0.158  # 68% relative scale error with 1-4 doors, val two-way
SPREAD_MANY = 0.0795  # with 5 or more doors
BOX_RATIO = 1.104  # a room's box area over its outline area, val median
OUTLINE_SPREAD = 0.157  # 68% |log| of that ratio around its median, val
MIN_SIDE_M = 0.7  # a room box narrower than a door is its label (a guard, not fitted)
MIN_COVER = 0.2  # rooms tile their plan; labels cover a few % of it (a guard, not fitted)
MIN_COVER_ROOMS = 3  # fewer boxes on a page say nothing about coverage
REFUSED_NOTE = "room area: "  # how the note on a room the box does not measure starts


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
        source=f"a door is about {DOOR_M} m wide; median of {len(sides)} detected doors",
        uncertainty=SPREAD_FEW if len(sides) < FEW_DOORS else SPREAD_MANY,
    )


def rooms_with_areas(
    rooms: Sequence[Room], scale: Scale, pages: Sequence[Page]
) -> tuple[list[Room], list[str]]:
    """Each room without an area gets its outline's area at `scale`, as an estimate, unless its
    box cannot be the room (`refused_boxes`): that room keeps no area, and the notes say why. A
    room that has an area keeps it."""
    if scale.m_per_unit is None:
        return list(rooms), []
    by_page = {page.page: page for page in pages}
    refused = refused_boxes(rooms, scale, pages)
    spread = math.hypot(2 * math.log1p(scale.uncertainty or 0.0), OUTLINE_SPREAD)
    out: list[Room] = []
    for room in rooms:
        page = by_page.get(room.page)
        if room.area_m2 is not None or page is None or room.id in refused:
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
    notes = [f"{REFUSED_NOTE}{room_id} not measured, {why}" for room_id, why in refused.items()]
    return out, notes


def refused_boxes(
    rooms: Sequence[Room],
    scale: Scale,
    pages: Sequence[Page],
    min_side_m: float = MIN_SIDE_M,
    min_cover: float = MIN_COVER,
) -> dict[str, str]:
    """The rooms (by id) whose area would come from a box that cannot be the room, each with the
    reason: on a page whose room boxes (at least MIN_COVER_ROOMS) cover under `min_cover` of the
    box around them all, every box room; else a box narrower than `min_side_m` at `scale`. Only
    rooms the box would measure count: no polygon, no area yet."""
    if scale.m_per_unit is None:
        return {}
    by_page = {page.page: page for page in pages}
    refused: dict[str, str] = {}
    for number, page in by_page.items():
        on_page = [room for room in rooms if room.page == number]
        boxed = [r for r in on_page if r.polygon is None and r.area_m2 is None]
        cover = _cover([room.box for room in on_page])
        if len(on_page) >= MIN_COVER_ROOMS and cover < min_cover:
            why = (
                f"the {len(on_page)} room boxes on page {number} cover {cover:.0%} of the area "
                f"around them (under {min_cover:.0%}): they box the labels, not the rooms"
            )
            refused |= dict.fromkeys((room.id for room in boxed), why)
            continue
        for room in boxed:
            x0, y0, x1, y1 = room.box
            side = min((x1 - x0) * page.width, (y1 - y0) * page.height) * scale.m_per_unit
            if side < min_side_m:
                refused[room.id] = (
                    f"its box is {side:.2f} m across, narrower than a door ({min_side_m:g} m): "
                    "it boxes the label, not the room"
                )
    return refused


def _cover(boxes: Sequence[Box]) -> float:
    """The share of the box around `boxes` that they cover (overlaps once); 1.0 for none."""
    if not boxes:
        return 1.0
    around = (max(b[2] for b in boxes) - min(b[0] for b in boxes)) * (
        max(b[3] for b in boxes) - min(b[1] for b in boxes)
    )
    if around <= 0:
        return 1.0
    xs = sorted({x for b in boxes for x in (b[0], b[2])})
    union = 0.0
    for left, right in itertools.pairwise(xs):  # each vertical slab: its covered y-length
        spans = sorted((b[1], b[3]) for b in boxes if b[0] <= left and b[2] >= right)
        covered, top = 0.0, -math.inf
        for y0, y1 in spans:
            covered += max(0.0, y1 - max(y0, top))
            top = max(top, y1)
        union += covered * (right - left)
    return union / around


def _shoelace(polygon: Sequence[tuple[float, float]]) -> float:
    pairs = zip(polygon, [*polygon[1:], polygon[0]], strict=True)
    return abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in pairs)) / 2

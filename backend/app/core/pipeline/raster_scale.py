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
- An area printed in a room's label (`area_source` printed, a raster label reader's) is kept as
  read, but `label_area_checks` sets it against the room's outline (or box) at the sheet's scale:
  more than LABEL_RANGE apart, one of the two is a misread ("KH 97 m²" with its decimal comma
  lost, on a 9.7 m² room), so both become stage-8 values of the room's area with no rule between
  them, and the answer leaves it to a person. A box narrower than MIN_SIDE_M is the label itself,
  not the room: nothing to compare with, the label stands.
"""

import math
import statistics
from collections.abc import Sequence

from app.core.drawing.model import (
    Element,
    MeasuredValue,
    MeasureMethod,
    Page,
    Room,
    Scale,
    Subject,
)
from app.core.pipeline.model import Measurement

DOOR_M = 0.794  # m, val (C-yolo26s-1536 ONNX doors, score >= 0.5)
MIN_DOOR_SCORE = 0.5  # the doors the prior was fitted on
FEW_DOORS = 5  # fewer detected doors than this print SPREAD_FEW
SPREAD_FEW = 0.158  # 68% relative scale error with 1-4 doors, val two-way
SPREAD_MANY = 0.0795  # with 5 or more doors
BOX_RATIO = 1.104  # a room's box area over its outline area, val median
OUTLINE_SPREAD = 0.157  # 68% |log| of that ratio around its median, val
# A printed label area and the outline at the sheet's scale further apart than this (either way)
# is a misread on one side. The outline's 68% |log| band at the door estimate is about 0.33
# (hypot(2 log1p(SPREAD_FEW), OUTLINE_SPREAD)); log 3 = 1.10 is over 3 of those bands (7 at a
# printed scale), while a lost decimal comma is 10x.
LABEL_RANGE = 3.0
MIN_SIDE_M = 0.7  # a room box narrower than a door boxes the label, not the room
LABEL_NOTE = "room label area: "  # how a label-area check's note starts


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


def label_area_checks(
    rooms: Sequence[Room], scale: Scale, pages: Sequence[Page]
) -> tuple[list[Measurement], list[str]]:
    """Each room whose area is printed in its label (`area_source` printed) and more than
    LABEL_RANGE from its outline (its box: over BOX_RATIO) at `scale`: two stage-8 values of its
    area, the label's (`printed_label`) and the outline's (`detector`: what the raster reading
    drew), which no rule decides between, and a note. A box narrower than MIN_SIDE_M boxes the
    label itself and is not compared. Nothing without a scale."""
    if scale.m_per_unit is None:
        return [], []
    by_page = {page.page: page for page in pages}
    found: list[Measurement] = []
    notes: list[str] = []
    for room in rooms:
        page = by_page.get(room.page)
        if room.area_source != "printed" or not room.area_m2 or page is None:
            continue
        x0, y0, x1, y1 = room.box
        side = min((x1 - x0) * page.width, (y1 - y0) * page.height) * scale.m_per_unit
        if room.polygon is None and side < MIN_SIDE_M:
            continue
        share = _shoelace(room.polygon) if room.polygon else (x1 - x0) * (y1 - y0) / BOX_RATIO
        outline = share * page.width * page.height * scale.m_per_unit**2
        if outline <= 0 or max(room.area_m2 / outline, outline / room.area_m2) <= LABEL_RANGE:
            continue
        subject = Subject(kind="room", ref=room.id)
        pair: tuple[tuple[float, MeasureMethod], ...] = (
            (room.area_m2, "printed_label"),
            (round(outline, 2), "detector"),
        )
        found += [
            Measurement(
                quantity="room_area",
                subject=subject,
                value=MeasuredValue(
                    value=value, unit="m2", method=method, page=room.page, box=room.box
                ),
            )
            for value, method in pair
        ]
        notes.append(
            f"{LABEL_NOTE}{room.id} prints {room.area_m2:g} m², its outline at the sheet's scale "
            f"is about {outline:.3g} m² (more than {LABEL_RANGE:g}x apart): left for a person"
        )
    return found, notes


def _shoelace(polygon: Sequence[tuple[float, float]]) -> float:
    pairs = zip(polygon, [*polygon[1:], polygon[0]], strict=True)
    return abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in pairs)) / 2


# SCALE_CARBON_DOORS=on (app/adapters/raster_scale/ CarbonDoorScale): when the detector found no
# door it is sure of, the Carbon reader's own door boxes. shortcut: CARBON_DOOR_M is DOOR_M, fitted
# on the detector's boxes, not Carbon's (it boxes a door with its swing, a square about a leaf wide
# on a side; on golden's 19 Carbon door boxes the scale comes out about 14.5% low); fit it on the
# hard set before the setting goes on: scripts/carbon_door_scale.py prints the value ("fit:")
CARBON_DOOR_M = DOOR_M


def carbon_door_scale(sides: Sequence[float]) -> Scale | None:
    """The scale from the door prior over Carbon's door boxes `sides`; None without a door. The
    band is SPREAD_FEW however many doors (the widest; the bands were fitted on the detector's)."""
    if not sides:
        return None
    return Scale(
        status="estimated",
        m_per_unit=CARBON_DOOR_M / statistics.median(sides),
        source=f"a door is about {CARBON_DOOR_M} m wide; median of {len(sides)} doors the Carbon "
        "reader found (the detector found no door it is sure of)",
        uncertainty=SPREAD_FEW,
    )

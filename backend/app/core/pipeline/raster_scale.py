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
- An area printed in a room's label (`area_source` printed, a raster label reader's) is kept as
  read, but `label_area_checks` sets it against the room's outline (or box) at the sheet's scale:
  more than LABEL_RANGE apart, one of the two is a misread ("KH 97 m²" with its decimal comma
  lost, on a 9.7 m² room), so both become stage-8 values of the room's area with no rule between
  them, and the answer leaves it to a person. A box under MIN_BOX_M2 (the rule below) is the
  label itself, not the room: nothing to compare with, the label stands.
- A box that cannot be the room gets no area (`refused_boxes`): a room reader sometimes boxes the
  room's printed label, not the room ("LOBBY 0.18 m²" on a 7.4 m² floor). A box under MIN_BOX_M2
  at the sheet's scale (a door leaf's footprint) is smaller than any room; and when the box rooms
  of a page (MIN_COVER_ROOMS or more) cover under MIN_COVER of the box around them all, they box
  scattered labels. The room stays, its area unknown, the reason in a note; never a smaller
  number. Always on for a raster sheet with a scale (no setting). The thresholds are guards, not
  fitted values: on golden v2 the first version refused 5 of 873 box rooms, 0 of them right
  (eu-big's fit, #14 c6883029882); golden v2 has no scanned PDF with gold room areas.
  scripts/fit_label_boxes.py sweeps them per half on cached replies.
"""

import bisect
import itertools
import math
import statistics
from collections.abc import Sequence

from app.core.drawing.model import (
    Box,
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
LABEL_NOTE = "room label area: "  # how a label-area check's note starts
# A box smaller than a door leaf's footprint (0.7 x 0.7 m) holds no room (a guard). The box's
# area, not its shorter side: real rooms can be narrow (high_quality-11271's kitchen 0.63 x 3 m,
# 1.9 m², and its utility kitchen APK about 0.6 x 1.8 m, 1.1 m², are kept), while a label is small
# both ways (USCG's "LOBBY" box, 0.18 m², is refused). A long thin label passes a side rule.
MIN_BOX_M2 = 0.5
# Box rooms covering under this share of the box around them all are scattered labels (a guard):
# USCG page 2's 14 label boxes cover 6%; rooms that tile a plan cover 50-90%, a sparse plan of
# separate blocks about 25%.
MIN_COVER = 0.1
MIN_COVER_ROOMS = 3  # fewer boxes on a page say nothing about coverage
REFUSED_NOTE = "room area: "  # how the note on a room the box does not measure starts
# The attr a refused room carries (its reason): a whole-sheet total leaves it out, marked partial
AREA_REFUSED = "area_refused"
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


def rooms_with_areas(
    rooms: Sequence[Room], scale: Scale, pages: Sequence[Page]
) -> tuple[list[Room], list[str]]:
    """Each room without an area gets its outline's area at `scale`, as an estimate, unless its
    box cannot be the room (`refused_boxes`): that room keeps no area, `attrs[AREA_REFUSED]` and
    the notes say why (a refusal at an earlier scale is measured again). A room that has an area
    keeps it."""
    if scale.m_per_unit is None:
        return list(rooms), []
    by_page = {page.page: page for page in pages}
    refused = refused_boxes(rooms, scale, pages)
    spread = math.hypot(2 * math.log1p(scale.uncertainty or 0.0), OUTLINE_SPREAD)
    out: list[Room] = []
    for room in rooms:
        if AREA_REFUSED in room.attrs:  # refused at the scale this one replaces
            attrs = {key: value for key, value in room.attrs.items() if key != AREA_REFUSED}
            room = room.model_copy(update={"attrs": attrs})
        page = by_page.get(room.page)
        if room.id in refused and room.area_m2 is None and page is not None:
            out.append(
                room.model_copy(update={"attrs": {**room.attrs, AREA_REFUSED: refused[room.id]}})
            )
            continue
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
    notes = [f"{REFUSED_NOTE}{room_id} not measured, {why}" for room_id, why in refused.items()]
    return out, notes


def refused_boxes(
    rooms: Sequence[Room],
    scale: Scale,
    pages: Sequence[Page],
    min_box_m2: float = MIN_BOX_M2,
    min_cover: float = MIN_COVER,
) -> dict[str, str]:
    """The rooms (by id) whose area would come from a box that cannot be the room, each with the
    reason: on a page whose box rooms (no polygon; at least MIN_COVER_ROOMS) cover under
    `min_cover` of the box around them all, every one that has no area yet; else a box under
    `min_box_m2` at `scale`. Only rooms the box would measure are refused: no polygon, no area
    yet. Always applied on a raster sheet with a scale (no setting)."""
    if scale.m_per_unit is None:
        return {}
    by_page = {page.page: page for page in pages}
    refused: dict[str, str] = {}
    for number, page in by_page.items():
        boxes = [room for room in rooms if room.page == number and room.polygon is None]
        boxed = [room for room in boxes if room.area_m2 is None]
        cover = _cover([room.box for room in boxes])
        if len(boxes) >= MIN_COVER_ROOMS and cover < min_cover:
            why = (
                f"the {len(boxes)} room boxes on page {number} cover {cover:.0%} of the area "
                f"around them (under {min_cover:.0%}): they box the labels, not the rooms"
            )
            refused |= dict.fromkeys((room.id for room in boxed), why)
            continue
        for room in boxed:
            x0, y0, x1, y1 = room.box
            width = (x1 - x0) * page.width * scale.m_per_unit
            height = (y1 - y0) * page.height * scale.m_per_unit
            if width * height < min_box_m2:
                refused[room.id] = (
                    f"its box is {width:.2f} x {height:.2f} m ({width * height:.2f} m²), smaller "
                    f"than any room (a door leaf's footprint, {min_box_m2:g} m²)"
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


def label_area_checks(
    rooms: Sequence[Room], scale: Scale, pages: Sequence[Page]
) -> tuple[list[Measurement], list[str]]:
    """Each room whose area is printed in its label (`area_source` printed) and more than
    LABEL_RANGE from its outline (its box: over BOX_RATIO) at `scale`: two stage-8 values of its
    area, the label's (`printed_label`) and the outline's (`detector`: what the raster reading
    drew), which no rule decides between, and a note. A box under MIN_BOX_M2 boxes the label
    itself and is not compared (refused_boxes' area rule). Nothing without a scale."""
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
        box_m2 = (x1 - x0) * page.width * (y1 - y0) * page.height * scale.m_per_unit**2
        if room.polygon is None and box_m2 < MIN_BOX_M2:
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


def outline_m2(room: Room, page: Page, m_per_unit: float) -> float | None:
    """A room's outline area at `m_per_unit`: its polygon, else its box over BOX_RATIO; None for
    a box under MIN_BOX_M2, which boxes a label, not the room (as `label_area_checks`)."""
    x0, y0, x1, y1 = room.box
    if (
        room.polygon is None
        and (x1 - x0) * page.width * (y1 - y0) * page.height * m_per_unit**2 < MIN_BOX_M2
    ):
        return None
    share = _shoelace(room.polygon) if room.polygon else (x1 - x0) * (y1 - y0) / BOX_RATIO
    return share * page.width * page.height * m_per_unit**2


def _shoelace(polygon: Sequence[tuple[float, float]]) -> float:
    pairs = zip(polygon, [*polygon[1:], polygon[0]], strict=True)
    return abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in pairs)) / 2


# SCALE_CARBON_DOORS=on (app/adapters/raster_scale/ CarbonDoorScale): when the detector found no
# door it is sure of, the Carbon reader's own door boxes (it boxes a door with its swing: a side
# longer than the detector's leaf box). Fitted by scripts/carbon_door_scale.py on 26 scans of dev
# swiss plans with a known scale, none in golden v2 (scripts/make_scans.py, pre-registered halves):
# the half-1 fit; 11/11 half-2 sheets inside the band (DOOR_M gave 3/21, median -25.2%); USCG fp21
# alone fit 1.123. shortcut: only 3 real scans behind it (fp21, 2 HABS), refit when more exist
CARBON_DOOR_M = 1.069  # m
CARBON_DOORS = "doors the Carbon reader found"  # in the source of every scale made from them


def carbon_door_scale(sides: Sequence[float]) -> Scale | None:
    """The scale from the door prior over Carbon's door boxes `sides`; None without a door. The
    band is SPREAD_FEW however many doors (the widest; the bands were fitted on the detector's)."""
    if not sides:
        return None
    return Scale(
        status="estimated",
        m_per_unit=CARBON_DOOR_M / statistics.median(sides),
        source=f"a door is about {CARBON_DOOR_M} m wide; median of {len(sides)} {CARBON_DOORS} "
        "(the detector found no door it is sure of)",
        uncertainty=SPREAD_FEW,
    )

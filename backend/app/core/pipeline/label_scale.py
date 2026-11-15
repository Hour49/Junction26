"""LABEL_SCALE=on: the areas printed in a raster sheet's room labels give its scale.

Many plans print each room's area in its label ("KH 9.7 m²", "BEDROOM 112 SF"); those numbers
survive a camera and a scanner, unlike a printed ratio (it needs the paper's dpi). Each room with
a printed area and an outline is a ruler: m_per_px_i = sqrt(label_m2 / outline_px_i), the outline
being the room's polygon, else its box over raster_scale.BOX_RATIO (floorplan2bim: printed room
areas as a ruler, 3.1% median scale error with exact rooms, 7.9% with recognised ones, CubiCasa5K;
docs/research/lit-campaign/reports/lit-scale.md). The areas come in square metres: the Carbon
reader converts square feet in its prompt, the Gemini room-label parser reads m² only.

- MIN_ROOMS (3) rooms at least, the sheet-wide label check's minimum (takeoff.LABEL_SCALE_ROOMS):
  with two, one misread label moves the median halfway; with three, the median is a real room.
- The scale is the median of the rooms' scales. A room further than OUTLIER from that median (in
  log scale: half of log raster_scale.LABEL_RANGE, the per-room conflict rule's range in area) is
  a misread and is dropped: a lost decimal comma is 10x in area, 3.16x in scale (log 1.15 > 0.55).
  A box under raster_scale.MIN_BOX_M2 at the median boxes the label, not the room: dropped too.
  The median is then taken again over the rooms kept, MIN_ROOMS still needed.
- The band (68%) is the median's standard error from the rooms' robust spread (1.4826 MAD of log
  m_per_px_i, times 1.2533 / sqrt(n) for a median), never under MIN_BAND: floorplan2bim's median
  error with recognised (not exact) rooms, which a box reader's rooms are.
- Where (the adapter, app/adapters/raster_scale/label.py): a raster sheet whose scale is the door
  estimate or none (a measured bar or a trusted printed ratio is `scaled` and stays), not a camera
  photo the rectifier left as it was (perspective breaks one global scale). With no scale the
  label scale is the sheet's; next to a door estimate it replaces it only when their 68% bands
  do not overlap (LABEL_SCALE=on), or whenever it is made (LABEL_SCALE=always), and the estimate
  stays a value of a `scale` conflict. On 10 Swiss dev scans that print room areas (cached Carbon
  replies, scripts/label_scale_bench.py) the label scale was 1.9% off the known scale (median,
  10/10 inside its band), the Carbon door estimate 4.1% (9/10): `on` never fired there (the door
  band, ±16%, overlaps), `always` takes the better one on each.
- Circularity: the rooms' labels agree with a scale made from them, so the sheet-wide label check
  (takeoff.label_disputed) is skipped on it; the per-room checks (raster_scale.label_area_checks)
  stay: one room 10x off the others is still a misread.
"""

import math
import statistics
from collections.abc import Sequence

from app.core.drawing.model import MeasuredValue, MeasureMethod, Page, Room, Scale, Subject
from app.core.pipeline.model import Extracted, Measurement
from app.core.pipeline.printed import label_checked, unestimated
from app.core.pipeline.raster_scale import (
    BOX_RATIO,
    LABEL_RANGE,
    REFUSED_NOTE,
    outline_m2,
    rooms_with_areas,
)

MIN_ROOMS = 3  # as takeoff.LABEL_SCALE_ROOMS: the median is a room, not a mean of two
OUTLIER = 0.5 * math.log(LABEL_RANGE)  # |log| in scale; a 10x area slip is 1.15
MIN_BAND = 0.079  # floorplan2bim's median scale error with recognised rooms
LABEL_SOURCE = "areas printed in"  # how the source of every scale made from room labels starts


def label_scale(rooms: Sequence[Room], pages: Sequence[Page]) -> Scale | None:
    """The scale the rooms' printed areas give (module docstring); None with fewer than
    MIN_ROOMS usable rooms."""
    by_page = {page.page: page for page in pages}
    rulers: list[tuple[float, Room, Page]] = []
    for room in rooms:
        page = by_page.get(room.page)
        if room.area_source != "printed" or not room.area_m2 or page is None:
            continue
        x0, y0, x1, y1 = room.box
        share = _share(room) if room.polygon else (x1 - x0) * (y1 - y0) / BOX_RATIO
        if share > 0:
            rulers.append(
                (math.sqrt(room.area_m2 / (share * page.width * page.height)), room, page)
            )
    if len(rulers) < MIN_ROOMS:
        return None
    middle = statistics.median(m for m, _, _ in rulers)
    kept = [
        m for m, room, page in rulers
        if abs(math.log(m / middle)) <= OUTLIER and outline_m2(room, page, middle) is not None
    ]  # fmt: skip
    if len(kept) < MIN_ROOMS:
        return None
    m_per_unit = statistics.median(kept)
    spread = 1.4826 * statistics.median(abs(math.log(m / m_per_unit)) for m in kept)
    band = max(MIN_BAND, math.expm1(1.2533 * spread / math.sqrt(len(kept))))
    return Scale(
        status="estimated",
        m_per_unit=m_per_unit,
        source=f"{LABEL_SOURCE} {len(kept)} room labels",
        uncertainty=round(band, 4),
    )


def with_label_scale(found: Extracted, pages: Sequence[Page], always: bool = False) -> Extracted:
    """`found` on the scale its room labels give, when that applies (module docstring): its
    estimated room areas measured again at it, the door estimate kept as a `scale` conflict
    value, its printed room areas checked again. Else `found` as it is. `always`
    (LABEL_SCALE=always): the label scale replaces a door estimate even inside its band."""
    before = found.scale
    if before.status not in ("estimated", "no_scale"):
        return found
    scale = label_scale(found.rooms, pages)
    if scale is None or scale.m_per_unit is None:
        return found
    if before.m_per_unit is not None and not always and not _apart(scale, before):
        return found
    rooms, refused = rooms_with_areas(unestimated(found.rooms), scale, pages)
    said = f"scale: {scale.source}"
    if before.m_per_unit is not None:
        said += f", in place of the scale estimated from the doors ({before.source})"
    notes = (*(n for n in found.notes if not n.startswith(REFUSED_NOTE)), said, *refused)
    relabelled = found.model_copy(
        update={
            "scale": scale,
            "rooms": tuple(rooms),
            "printed": (*found.printed, *_conflict(before, scale)),
            "notes": notes,
        }
    )
    return label_checked(relabelled, pages)


def _apart(one: Scale, other: Scale) -> bool:
    """Whether two estimated scales' 68% bands do not overlap."""
    assert one.m_per_unit is not None and other.m_per_unit is not None
    reach = math.log1p(one.uncertainty or 0.0) + math.log1p(other.uncertainty or 0.0)
    return abs(math.log(one.m_per_unit / other.m_per_unit)) > reach


def _conflict(before: Scale, labels: Scale) -> list[Measurement]:
    """The door estimate (`detector`) and the label scale (`printed_label`) as two values of the
    sheet's scale; nothing when there was no estimate."""
    if before.m_per_unit is None or labels.m_per_unit is None:
        return []
    sheet = Subject(kind="sheet", ref=None)
    pair: tuple[tuple[float, MeasureMethod], ...] = (
        (before.m_per_unit, "detector"),
        (labels.m_per_unit, "printed_label"),
    )
    return [
        Measurement(
            quantity="scale",
            subject=sheet,
            value=MeasuredValue(value=value, unit="m/px", method=method),
        )
        for value, method in pair
    ]


def _share(room: Room) -> float:
    """A polygon room's outline as a share of its page (the shoelace formula)."""
    assert room.polygon is not None
    pairs = zip(room.polygon, [*room.polygon[1:], room.polygon[0]], strict=True)
    return abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in pairs)) / 2

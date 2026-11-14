"""What a raster sheet prints about its own scale and quantities, against what was read off it.

A raster reading gets its scale from the doors it detected (`raster_scale`: estimated, about 16%
off with few doors), or none. Many sheets print theirs: a scale bar, or a ratio ("1:200",
"1/4\" = 1'-0\"", "1\" = 40'"). And some print a quantity outright ("SECOND FLOOR = 48 DORMS").
A `PrintedReader` reads these (the Carbon reader's `printed_scale` and `printed_facts`, plus the
scale bar's two labelled ends on a full-resolution tile); this module turns them into the sheet's
scale and the stage-8 measurements to check the reading with.

- Scale. A bar gives metres per pixel directly: its labelled length over its length in pixels
  (the median when several bars are read). A ratio gives it only with the image's resolution, and
  only when the file states one that can be trusted (`trusted_dpi`): an image has no paper size.
  The printed scale replaces the estimate, and the estimate is kept as a second value of a `scale`
  conflict entry, so a difference of more than second_count.ESTIMATE_TOLERANCE (10%) shows; the
  printed one is kept. When the two are more than second_count.ESTIMATE_RANGE (2x) apart, one of
  them is a misread: a measured bar still wins (the pixel distance between two of its labelled
  ticks is a measurement; the estimate can rest on one door), and the takeoff flags every area
  and length on the sheet (`takeoff.disputed_scale`); a ratio does not (it needs a resolution and
  can belong to another detail): the estimate stays the sheet's scale and no rule decides.
- Printed facts. A printed count of an element class, of a room type or of all rooms becomes a
  second value of that count (method `printed_total`). It never replaces the count read off the
  drawing: no rule decides between the two, so a difference stays open for a person.
"""

import math
import re
import statistics
from collections.abc import Sequence

from pydantic import Field

from app.core.drawing.model import (
    ELEMENT_CLASSES,
    ROOM_TYPES,
    Box,
    MeasuredValue,
    MeasureMethod,
    Page,
    Scale,
    ScaleEvidence,
    Subject,
)
from app.core.model import Frozen
from app.core.pipeline.model import Extracted, Measurement
from app.core.pipeline.raster_scale import REFUSED_NOTE, rooms_with_areas
from app.core.pipeline.second_count import ESTIMATE_RANGE, far_apart, mm_per_px

INCH_M = 0.0254
POINTS_PER_INCH = 72.0  # a PDF page's unit
MIN_BAR_PX = 20.0  # a bar shorter than this on the image is not measured: a few px off is 10%
DPI_RANGE = (100.0, 1200.0)  # a stated resolution outside it is not a scan's or an export's
DEFAULT_DPI = (72.0, 96.0)  # what software writes when it knows nothing: never trusted
MAX_PAPER_INCHES = 6.0  # an imperial scale draws at most half size, 6" to the foot
COUNT_UNIT = "count"


class ScaleBar(Frozen):
    """A printed scale bar: the image points (page fractions) of two of its labelled ticks and the
    length between those labels, in metres."""

    page: int = Field(ge=1)
    start: tuple[float, float]
    end: tuple[float, float]
    length_m: float = Field(gt=0)
    text: str | None = None  # the labels as printed, e.g. "0 1 2 5 m"


class PrintedFact(Frozen):
    """A quantity the sheet prints, as the Carbon reader gives it: `subject` an element class,
    room:<type>, room (all rooms), floor_area, apartment_area, storey or other."""

    text: str
    subject: str
    value: float = Field(allow_inf_nan=False)
    unit: str
    page: int = Field(default=1, ge=1)
    box: Box | None = None


class PrintedSheet(Frozen):
    printed_scale: str | None = None  # as printed: "1:100", "1/4 in = 1 ft", "bar"
    bars: tuple[ScaleBar, ...] = ()
    printed_facts: tuple[PrintedFact, ...] = ()
    notes: tuple[str, ...] = ()  # what the reader could not read, and why


_GROUPED = "[ \u00a0\u202f,.]"  # a thousands separator: space, no-break spaces, comma, point
# "1:1 000" (Finnish), "1:1,000", "1:1.000": three-digit groups are thousands; "1:2,5" is 2.5
_RATIO = re.compile(
    rf"(?<![\d.])1\s*:\s*(?:(\d{{1,3}}(?:{_GROUPED}\d{{3}})+)|(\d+(?:[.,]\d+)?))(?![\d.])"
)
# A whole inch before a fraction only in 1 1/2" (or 1-1/2"), the one mixed number on an
# architect's scale: any other number there is a view, level or sheet number ("LEVEL 2 1/4\"",
# "A-301 1/8\""), not inches.
_FRACTION = r"(?<![\d.])(?:(1)[\s-]+(?=1\s*/\s*2(?!\d)))?(\d+(?:\.\d+)?)(?:\s*/\s*(\d+))?"
_INCHES = r"(?:\"|''|\u201d|in(?:ch(?:es)?)?\b)"  # ", '', a right double quote, in, inch
_FEET = r"(?:'|\u2019|ft\b|feet\b|foot\b)"  # ', a right single quote, ft, feet
_IMPERIAL = re.compile(
    rf"{_FRACTION}\s*{_INCHES}\s*=\s*(\d+(?:\.\d+)?)\s*{_FEET}(?:\s*-?\s*(\d+(?:\.\d+)?)\s*{_INCHES})?",
    re.IGNORECASE,
)


def ratio_of(text: str | None) -> float | None:
    """How many times larger the building is than the sheet, from a printed scale: "1:200" is
    200; "1/4\" = 1'-0\"" is 48; "1\" = 40'" is 480. None when the text states no ratio."""
    if not text:
        return None
    if (found := _RATIO.search(text)) is not None:
        grouped, plain = found.groups()
        ratio = float(re.sub(_GROUPED, "", grouped) if grouped else plain.replace(",", "."))
        return ratio if ratio > 0 else None
    if (found := _IMPERIAL.search(text)) is not None:
        return _imperial_ratio(found)
    return None


def imperial_scales(text: str) -> list[tuple[float, str]]:
    """Every imperial scale `text` prints, as `ratio_of` reads it, with the scale as printed:
    "1/4\" = 1'-0\"" is (48, "1/4\" = 1'-0\""). The text should be one label: a 1 before 1/2" is
    read as a whole inch, so a view number 1 next to a 1/2" scale would be."""
    found = ((_imperial_ratio(match), match.group(0).strip()) for match in _IMPERIAL.finditer(text))
    return [(ratio, printed) for ratio, printed in found if ratio is not None]


def _imperial_ratio(found: re.Match[str]) -> float | None:
    """The ratio of an imperial scale; None for no scale: more than MAX_PAPER_INCHES of paper per
    foot or a drawing larger than the building is a misread number, not a scale."""
    whole, numerator, denominator, feet, inches = found.groups()
    paper = float(whole or 0) + float(numerator) / (float(denominator) if denominator else 1.0)
    real = float(feet) * 12 + (float(inches) if inches else 0.0)
    if not 0 < paper <= MAX_PAPER_INCHES or real < paper:
        return None
    return real / paper


def trusted_dpi(dpi: tuple[float, float] | None) -> float | None:
    """The image's stated resolution when it can be trusted: the same both ways, in DPI_RANGE,
    and not a software default (DEFAULT_DPI)."""
    if dpi is None:
        return None
    x, y = dpi
    if abs(x - y) > 0.01 * max(x, y) or not DPI_RANGE[0] <= x <= DPI_RANGE[1]:
        return None
    if any(abs(x - default) < 0.5 for default in DEFAULT_DPI):
        return None
    return x


def bar_m_per_px(bar: ScaleBar, pages: Sequence[Page]) -> float | None:
    """Metres per pixel from a scale bar; None for a bar on no page or shorter than MIN_BAR_PX."""
    page = next((page for page in pages if page.page == bar.page), None)
    if page is None:
        return None
    px = math.hypot(
        (bar.end[0] - bar.start[0]) * page.width, (bar.end[1] - bar.start[1]) * page.height
    )
    return bar.length_m / px if px >= MIN_BAR_PX else None


def printed_scale(printed: PrintedSheet, pages: Sequence[Page], dpi: float | None) -> Scale | None:
    """The sheet's scale as it prints it, in metres per page unit: its bars (median), else its
    ratio at `dpi` (a trusted resolution, or None) on a page in pixels, at 72 to the inch on a
    page in points; None when neither gives one."""
    ratio = ratio_of(printed.printed_scale)
    shown = printed.printed_scale if ratio is not None else None
    measured = [m for m in (bar_m_per_px(bar, pages) for bar in printed.bars) if m is not None]
    if measured:
        evidence: tuple[ScaleEvidence, ...] = (
            ("scale_bar", "scale_text") if shown else ("scale_bar",)
        )
        return Scale(
            status="scaled",
            m_per_unit=statistics.median(measured),
            evidence=evidence,
            text=shown,
            source=f"printed scale bar ({_bars(len(measured))})",
        )
    if ratio is not None and dpi is not None:
        # Metres per page unit. A scanned PDF's page is in points, 72 to the inch of its paper,
        # whatever resolution its render states: `dpi` there only says the paper size is known.
        points = bool(pages) and pages[0].unit == "pt"
        return Scale(
            status="scaled",
            m_per_unit=ratio * INCH_M / (POINTS_PER_INCH if points else dpi),
            evidence=("scale_text",),
            text=shown,
            source=(
                f"printed scale {shown} on the page's paper size"
                if points
                else f"printed scale {shown} at the image's {dpi:g} dpi"
            ),
        )
    return None


def _bars(n: int) -> str:
    return "one bar" if n == 1 else f"median of {n} bars"


def scale_measurements(printed: Scale, before: Scale) -> list[Measurement]:
    """The printed scale and the estimate it replaces (`before`, when it is one), as two values
    of the sheet's `scale` (method `detector`: the estimate rests on the detected doors). Nothing
    when there was no estimate."""
    estimate = before if before.status == "estimated" else None
    if estimate is None or estimate.m_per_unit is None or printed.m_per_unit is None:
        return []
    method: MeasureMethod = "scale_bar" if "scale_bar" in printed.evidence else "scale_text"
    sheet = Subject(kind="sheet", ref=None)
    return [
        Measurement(
            quantity="scale",
            subject=sheet,
            value=MeasuredValue(value=estimate.m_per_unit, unit="m/px", method="detector"),
        ),
        Measurement(
            quantity="scale",
            subject=sheet,
            value=MeasuredValue(value=printed.m_per_unit, unit="m/px", method=method),
        ),
    ]


def fact_measurements(facts: Sequence[PrintedFact]) -> list[Measurement]:
    """Each printed count of an element class, a room type or all rooms, as a second value of
    that count (method `printed_total`). Areas, storeys and other facts are not compared. When
    the sheet prints one count twice, the first is kept."""
    out: dict[tuple[str, Subject], Measurement] = {}
    for fact in facts:
        if fact.unit != COUNT_UNIT or fact.value < 0 or fact.value != int(fact.value):
            continue
        if fact.subject in ELEMENT_CLASSES:
            quantity, subject = "element_count", Subject(kind="class", ref=fact.subject)
        elif fact.subject == "room":
            quantity, subject = "room_count", Subject(kind="sheet", ref=None)
        elif fact.subject.removeprefix("room:") in ROOM_TYPES and fact.subject.startswith("room:"):
            quantity, subject = "room_count", Subject(kind="class", ref=fact.subject)
        else:
            continue
        value = MeasuredValue(
            value=fact.value,
            unit=COUNT_UNIT,
            method="printed_total",
            page=fact.page if fact.box is not None else None,
            box=fact.box,
        )
        out.setdefault(
            (quantity, subject), Measurement(quantity=quantity, subject=subject, value=value)
        )
    return list(out.values())


def with_printed(
    found: Extracted, printed: PrintedSheet, pages: Sequence[Page], dpi: float | None
) -> Extracted:
    """`found` with what the sheet prints: its printed scale in place of an estimated one (or of
    none), every room area the estimate gave measured again at it, and the printed scale and
    counts as stage-8 values against the reading. A scale the reading measured itself is kept."""
    notes = [*found.notes, *printed.notes]
    measurements = [
        *_room_types_counted(found, printed.printed_facts),
        *fact_measurements(printed.printed_facts),
    ]
    notes += [f"printed on the sheet: {fact.text}" for fact in printed.printed_facts]
    scale = printed_scale(printed, pages, dpi)
    if found.scale.status in ("scaled", "not_to_scale"):
        scale = None
    elif (
        scale is not None
        and scale.m_per_unit is not None
        and found.scale.status == "estimated"
        and found.scale.m_per_unit is not None
        and far_apart(scale.m_per_unit, found.scale.m_per_unit)
        and "scale_bar" not in scale.evidence
    ):  # one of the two is a misread: the estimate stays, the conflict is left to a person
        measurements = [*scale_measurements(scale, found.scale), *measurements]
        notes.append(
            f"printed scale ({scale.source}) is more than {ESTIMATE_RANGE:g}x the scale "
            "estimated from the doors: not used, left for a person to check"
        )
        scale = None
    elif (
        scale is not None
        and scale.m_per_unit is not None
        and found.scale.status == "estimated"
        and found.scale.m_per_unit is not None
        and far_apart(scale.m_per_unit, found.scale.m_per_unit)
    ):  # a measured bar: it wins, and the takeoff flags what rests on it
        notes.append(
            f"printed scale bar ({mm_per_px(scale.m_per_unit)}) is more than "
            f"{ESTIMATE_RANGE:g}x the scale estimated from the doors "
            f"({mm_per_px(found.scale.m_per_unit)}): the bar is used, its areas and lengths "
            "are flagged for a person to check"
        )
    elif scale is None and printed.printed_scale:
        notes.append(
            f"printed scale {printed.printed_scale}: read, not used (no scale bar was measured "
            "and the image states no resolution to trust)"
        )
    update: dict[str, object] = {"notes": tuple(notes), "printed": (*found.printed, *measurements)}
    if scale is not None:
        measurements = [*scale_measurements(scale, found.scale), *measurements]
        rooms = [
            room.model_copy(update={"area_m2": None, "area_status": None, "area_source": None,
                                    "area_uncertainty": None})
            if room.area_source == "geometry_x_estimate" else room
            for room in found.rooms
        ]  # fmt: skip
        measured, refused = rooms_with_areas(rooms, scale, pages)
        update |= {
            "scale": scale,
            "rooms": tuple(measured),
            "printed": (*found.printed, *measurements),
            "notes": (  # the rooms are measured again: the estimate's refusals go
                *(note for note in notes if not note.startswith(REFUSED_NOTE)),
                f"scale: {scale.source}",
                *refused,
            ),
        }
    return found.model_copy(update=update)


def _room_types_counted(found: Extracted, facts: Sequence[PrintedFact]) -> list[Measurement]:
    """How many rooms of each type the reading has, for each room type the sheet prints a count
    of: the value a printed count of that type stands against (`measured` has no per-type room
    count). None when the reading did not look for rooms."""
    if found.read is not None and "room" not in found.read:
        return []
    wanted = dict.fromkeys(
        fact.subject for fact in facts
        if fact.unit == COUNT_UNIT and fact.subject.removeprefix("room:") in ROOM_TYPES
        and fact.subject.startswith("room:")
    )  # fmt: skip
    return [
        Measurement(
            quantity="room_count",
            subject=Subject(kind="class", ref=kind),
            value=MeasuredValue(
                value=sum(room.type == kind.removeprefix("room:") for room in found.rooms),
                unit="rooms",
                method=found.method,
            ),
        )
        for kind in wanted
    ]

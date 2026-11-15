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
  second value of that count (method `printed_total`). It does not replace the count read off the
  drawing: no rule decides between the two, so a difference stays open for a person. With
  PRINTED_TOTAL_ANSWERS=on, one that matches the count exactly is reported (printed_answer.py).
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
    Room,
    Scale,
    ScaleEvidence,
    Subject,
)
from app.core.model import Frozen
from app.core.pipeline.model import Extracted, Measurement
from app.core.pipeline.raster_scale import (
    AREA_REFUSED,
    CARBON_DOORS,
    LABEL_NOTE,
    REFUSED_NOTE,
    label_area_checks,
    rooms_with_areas,
)
from app.core.pipeline.scale_signatures import Signatures, Verdict, bar_verdict, ratio_verdict
from app.core.pipeline.second_count import ESTIMATE_RANGE, far_apart, mm_per_px

INCH_M = 0.0254
POINTS_PER_INCH = 72.0  # a PDF page's unit
MIN_BAR_PX = 20.0  # a bar shorter than this on the image is not measured: a few px off is 10%
DPI_RANGE = (100.0, 1200.0)  # a stated resolution outside it is not a scan's or an export's
DEFAULT_DPI = (72.0, 96.0)  # what software writes when it knows nothing: never trusted
MAX_PAPER_INCHES = 6.0  # an imperial scale draws at most half size, 6" to the foot
COUNT_UNIT = "count"
# A sheet that prints a scale we could not read keeps no scale rather than one from Carbon's door
# sizes: on integ's jf03 (a hand-written 1/4") that scale gave areas outside their stated band.
CARBON_DOORS_REFUSED = (
    "the sheet prints a scale that could not be read; "
    "a scale from door sizes is not used in its place"
)
# A Finnish flat type: 4H+K is four rooms and a kitchen, 3h+k+s three rooms, kitchen and sauna. It
# names the flat; it does not count the rooms a plan draws (live 2026-11-14: 4H+K against 18 read)
FLAT_TYPE = re.compile(
    r"(?<![^\W\d_])\d+\s*h\s*\+\s*[a-zåäö]+(?:\s*\+\s*[a-zåäö]+)*", re.IGNORECASE
)


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
_INCHES = r"(?:\"|''|\u201d|in(?:ch(?:es)?)?\b\.?)"  # ", '', a right double quote, in(.), inch
_FEET = r"(?:'|\u2019|ft\b\.?|feet\b|foot\b)"  # ', a right single quote, ft(.), feet
# How old and typeset sheets print a scale (QA R3-C1, USCG Building 407: "SIZE \u00bc\"=1'-0\""):
# a fraction glyph is " n/d" (1\u00bd is 1 1/2), the fraction slash a slash, primes quotes
_GLYPHS = str.maketrans(
    {
        "\u00bc": " 1/4",
        "\u00bd": " 1/2",
        "\u00be": " 3/4",
        "\u215b": " 1/8",
        "\u215c": " 3/8",
        "\u215d": " 5/8",
        "\u215e": " 7/8",
        "\u2044": "/",  # the fraction slash
        "\u2032": "'",  # prime
        "\u2033": '"',  # double prime
    }
)
# A glyph right after a digit is that many inches and more: 1\u00bc" is 1.25" (review-612 S1)
_AFTER_DIGIT = re.compile("(\\d+)([\u00bc\u00bd\u00be\u215b\u215c\u215d\u215e])")


def _plain(text: str) -> str:
    """`text` with its fraction glyphs, fraction slash and primes as `_IMPERIAL` reads them."""
    mixed = _AFTER_DIGIT.sub(
        lambda m: f"{int(m.group(1)) + _fraction(_GLYPHS[ord(m.group(2))]):g}", text
    )
    return mixed.translate(_GLYPHS)


def _fraction(text: str) -> float:
    numerator, denominator = text.split("/")
    return float(numerator) / float(denominator)


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
    if (found := _IMPERIAL.search(_plain(text))) is not None:
        return _imperial_ratio(found)
    return None


def imperial_scales(text: str) -> list[tuple[float, str]]:
    """Every imperial scale `text` prints, as `ratio_of` reads it, with the scale as printed:
    "1/4\" = 1'-0\"" is (48, "1/4\" = 1'-0\""). The text should be one label: a 1 before 1/2" is
    read as a whole inch, so a view number 1 next to a 1/2" scale would be."""
    plain = _plain(text)
    found = ((_imperial_ratio(m), m.group(0).strip()) for m in _IMPERIAL.finditer(plain))
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
    return ratio_scale(printed, pages, dpi)


def ratio_scale(printed: PrintedSheet, pages: Sequence[Page], dpi: float | None) -> Scale | None:
    """The sheet's printed ratio in metres per page unit, at `dpi` on a page in pixels, at 72 to
    the inch on a page in points; None without a ratio or a resolution."""
    ratio = ratio_of(printed.printed_scale)
    shown = printed.printed_scale if ratio is not None else None
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
    that count (method `printed_total`). Areas, storeys and other facts are not compared, nor a
    flat type (4H+K) read as a room count. When the sheet prints one count twice, the first is
    kept."""
    out: dict[tuple[str, Subject], Measurement] = {}
    for fact in facts:
        if fact.unit != COUNT_UNIT or fact.value < 0 or fact.value != int(fact.value):
            continue
        if fact.subject.startswith("room") and FLAT_TYPE.search(fact.text):
            continue  # it stays in the notes, "printed on the sheet: 4H+K"
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
    found: Extracted,
    printed: PrintedSheet,
    pages: Sequence[Page],
    dpi: float | None,
    signatures: Signatures = "off",
) -> Extracted:
    """`found` with what the sheet prints: its printed scale in place of an estimated one (or of
    none), every room area the estimate gave measured again at it, and the printed scale and
    counts as stage-8 values against the reading. A scale the reading measured itself is kept.
    Every area printed in a room's label is then checked at the sheet's final scale.
    `signatures` (SCALE_SIGNATURES): two scales a known slip apart are named (scale_signatures):
    "bar" a bar against its ratio, "on" also a ratio against the doors."""
    notes = [*found.notes, *printed.notes]
    measurements = [
        *_room_types_counted(found, printed.printed_facts),
        *fact_measurements(printed.printed_facts),
    ]
    notes += [f"printed on the sheet: {fact.text}" for fact in printed.printed_facts]
    scale = printed_scale(printed, pages, dpi)
    signed = _signature(scale, found, printed, pages, dpi, signatures)
    if found.scale.status in ("scaled", "not_to_scale"):
        scale = None
    elif scale is not None and signed is not None and signed.keep_estimate:  # labels: the doors
        measurements = [*scale_measurements(scale, found.scale), *measurements]
        notes.append(signed.note)
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
        if CARBON_DOORS in (found.scale.source or ""):
            dropped = f"scale estimate: {found.scale.source}"
            notes = [n for n in notes if n != dropped and not n.startswith(REFUSED_NOTE)]
            notes.append(CARBON_DOORS_REFUSED)
            found = found.model_copy(
                update={"scale": Scale(status="no_scale"), "rooms": _unestimated(found.rooms)}
            )
    update: dict[str, object] = {"notes": tuple(notes), "printed": (*found.printed, *measurements)}
    if scale is not None:
        measurements = [*scale_measurements(scale, found.scale), *measurements]
        if signed is not None:
            notes.append(signed.note)
            measurements = [*_ratio_value(signed, scale, found.scale), *measurements]
        measured, refused = rooms_with_areas(_unestimated(found.rooms), scale, pages)
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
    return _label_checked(found.model_copy(update=update), pages)


def _signature(
    scale: Scale | None,
    found: Extracted,
    printed: PrintedSheet,
    pages: Sequence[Page],
    dpi: float | None,
    signatures: Signatures,
) -> Verdict | None:
    """SCALE_SIGNATURES: a measured bar against the ratio printed beside it, or (no bar) the
    ratio against the door estimate when they are inside ESTIMATE_RANGE (outside it, the
    far-apart rules decide), a known slip apart (scale_signatures). None otherwise."""
    if signatures == "off" or scale is None or scale.m_per_unit is None:
        return None
    if "scale_bar" in scale.evidence:
        return bar_verdict(scale, ratio_scale(printed, pages, dpi))
    estimate = found.scale
    if signatures != "on" or estimate.status != "estimated" or estimate.m_per_unit is None:
        return None
    if far_apart(scale.m_per_unit, estimate.m_per_unit):
        return None
    return ratio_verdict(scale, estimate, found.rooms, pages)


def _ratio_value(signed: Verdict, bar: Scale, before: Scale) -> list[Measurement]:
    """The printed ratio as a value of the sheet's `scale` beside the bar (and the bar too
    when no estimate put it there: a conflict needs two values)."""
    if signed.ratio is None or bar.m_per_unit is None:
        return []
    sheet = Subject(kind="sheet", ref=None)
    values: list[tuple[float, MeasureMethod]] = [(signed.ratio, "scale_text")]
    if before.status != "estimated" or before.m_per_unit is None:
        values.append((bar.m_per_unit, "scale_bar"))
    return [
        Measurement(
            quantity="scale",
            subject=sheet,
            value=MeasuredValue(value=value, unit="m/px", method=method),
        )
        for value, method in values
    ]


def _unestimated(rooms: Sequence[Room]) -> tuple[Room, ...]:
    """`rooms` without the areas an estimated scale gave them, or its refusals."""
    cleared = {"area_m2": None, "area_status": None, "area_source": None, "area_uncertainty": None}
    return tuple(
        room.model_copy(
            update={**cleared, "attrs": {k: v for k, v in room.attrs.items() if k != AREA_REFUSED}}
        )
        if room.area_source == "geometry_x_estimate" or AREA_REFUSED in room.attrs
        else room
        for room in rooms
    )


def _label_checked(found: Extracted, pages: Sequence[Page]) -> Extracted:
    """`found` with its printed room areas checked at its (final) scale: an earlier check, at
    the scale it replaced, goes (`label_area_checks`)."""
    checks, said = label_area_checks(found.rooms, found.scale, pages)
    earlier = [
        m for m in found.printed
        if m.quantity == "room_area" and m.value.method in ("printed_label", "detector")
    ]  # fmt: skip
    return found.model_copy(
        update={
            "printed": (*(m for m in found.printed if m not in earlier), *checks),
            "notes": (*(n for n in found.notes if not n.startswith(LABEL_NOTE)), *said),
        }
    )


unestimated = _unestimated  # for label_scale.py (LABEL_SCALE)
label_checked = _label_checked


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

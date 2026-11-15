"""Two scales of one sheet whose quotient is a known slip (SCALE_SIGNATURES).

`printed.with_printed` treats two scales as conflicting only when they are more than
second_count.ESTIMATE_RANGE (2x) apart. Inside that, the usual ways a printed scale is wrong
have exact quotients (scanned.md #2, #5 in docs/research/pdf-accuracy/): neighbouring
architectural scales (3/32" vs 1/8", 1:75 vs 1:100: 4/3), an A-series sheet printed one size
down (A1 on A2: sqrt 2), a sheet printed at two-thirds size or 1:100 vs 1:150 (3/2), a half-size
set (2), and an ARCH D sheet (24x36") fitted to 11x17 (36/17 on its long side, 24/11 on its short
side, which is the one that limits the fit). A quotient within TOLERANCE of one of these is not a
reading error of a few percent but one scale belonging to another print or view.

TOLERANCE is 2.5%: 4/3 and sqrt 2 are 6.1% apart, the closest pair that names different causes,
so two windows never overlap (36/17 and 24/11 are 3% apart but name one cause). A bar measured
over at least printed.MIN_BAR_PX and a ratio at a stated resolution are both good to about 1%.

A door estimate is not that precise (raster_scale: about 16% off with few doors, 15-33% on US
sheets), so a signature between a printed scale and the doors can be chance: on tonight's T1-T3
the bar and the doors were within 1% of 4/3, 3/2 and sqrt 2 while the bar was right on two of
them. `label_pick` is the tie-break: the areas printed in the rooms' labels at each candidate.
Measured 2026-11-15 on 28 scan reads with a gold scale: Carbon's door estimate fell inside a window
on 7 whose ratio was right and on 0-7 with a slipped ratio, so `ratio_verdict` runs only with
SCALE_SIGNATURES=on; `bar` runs `bar_verdict` alone (0 of 29 right scans flagged).
"""

import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from app.core.drawing.model import Page, Room, Scale
from app.core.pipeline.raster_scale import outline_m2
from app.core.pipeline.second_count import mm_per_px

Signatures = Literal["off", "bar", "on"]  # SCALE_SIGNATURES: which comparisons run
TOLERANCE = 0.025
# label_pick: at least this many rooms with a printed area (takeoff.LABEL_SCALE_ROOMS), and the
# median printed / outline area within LABEL_AGREE of 1 at one candidate and not the other
LABEL_ROOMS = 3
LABEL_AGREE = 0.10


@dataclass(frozen=True)
class Factor:
    name: str  # as a note shows it: "4/3"
    value: float  # the larger scale over the smaller, metres per unit
    cause: str  # in words a user reads


FACTORS: tuple[Factor, ...] = (
    Factor("4/3", 4 / 3, 'neighbouring scales (1:75 and 1:100, 3/32" and 1/8")'),
    Factor("√2", math.sqrt(2), "an A-series sheet printed one size down (A1 on A2)"),
    Factor("3/2", 3 / 2, "a sheet printed at two-thirds size, or 1:100 and 1:150"),
    Factor("2", 2.0, "a half-size print, or 1:100 and 1:200"),
    Factor("36/17", 36 / 17, 'an ARCH D sheet (24x36") fitted to 11x17'),
    Factor("24/11", 24 / 11, 'an ARCH D sheet (24x36") fitted to 11x17'),
)


@dataclass(frozen=True)
class Signature:
    name: str
    cause: str
    quotient: float  # the larger over the smaller, as measured
    larger: Literal["first", "second"]  # which of the two scales is the larger


def slip(a_m_per_unit: float, b_m_per_unit: float) -> Signature | None:
    """The known slip whose factor the two scales' quotient is within TOLERANCE of (the closest
    one), or None: no slip, or a scale that is not positive."""
    if a_m_per_unit <= 0 or b_m_per_unit <= 0:
        return None
    high, low = max(a_m_per_unit, b_m_per_unit), min(a_m_per_unit, b_m_per_unit)
    quotient = high / low
    near = [f for f in FACTORS if abs(quotient / f.value - 1) <= TOLERANCE]
    if not near:
        return None
    best = min(near, key=lambda f: abs(quotient / f.value - 1))
    larger: Literal["first", "second"] = "first" if a_m_per_unit >= b_m_per_unit else "second"
    return Signature(best.name, best.cause, quotient, larger)


def label_pick(
    rooms: Sequence[Room], pages: Sequence[Page], first: Scale, second: Scale
) -> Literal["first", "second"] | None:
    """Which of two scales the areas printed in the rooms' labels agree with: the median of
    printed / outline area within LABEL_AGREE of 1 at that scale and not at the other. None with
    fewer than LABEL_ROOMS labelled rooms, or when both or neither agree."""
    by_page = {page.page: page for page in pages}
    agree: list[bool] = []
    for scale in (first, second):
        if scale.m_per_unit is None:
            return None
        ratios: list[float] = []
        for room in rooms:
            page = by_page.get(room.page)
            if room.area_source != "printed" or not room.area_m2 or page is None:
                continue
            outline = outline_m2(room, page, scale.m_per_unit)
            if outline:
                ratios.append(room.area_m2 / outline)
        if len(ratios) < LABEL_ROOMS:
            return None
        agree.append(abs(statistics.median(ratios) - 1) <= LABEL_AGREE)
    if agree == [True, False]:
        return "first"
    if agree == [False, True]:
        return "second"
    return None


# The note that holds a sheet's areas (takeoff.disputed_scale reads it): after it, what an area
# or length rests on, in words a user reads
SCALE_SLIP = "scale slip: "


@dataclass(frozen=True)
class Verdict:
    """What `with_printed` does about a signature: a note; `keep_estimate`: the door estimate
    stays the sheet's scale; `ratio`: a printed ratio's metres per unit, a second value of the
    sheet's `scale` beside the bar."""

    note: str
    keep_estimate: bool = False
    ratio: float | None = None


def bar_verdict(bar: Scale, ratio: Scale | None) -> Verdict | None:
    """A measured bar and the ratio printed beside it (at the image's resolution) a known slip
    apart: the bar stays the sheet's scale (a measurement), the ratio becomes a conflict value
    and the note names the cause. None when there is no such ratio or no slip."""
    if ratio is None or ratio.m_per_unit is None or bar.m_per_unit is None:
        return None
    found = slip(ratio.m_per_unit, bar.m_per_unit)
    if found is None:
        return None
    return Verdict(
        note=(
            f"the printed scale {ratio.text} ({mm_per_px(ratio.m_per_unit)}) is {_times(found)} "
            f"the measured scale bar ({mm_per_px(bar.m_per_unit)}): {found.cause}, or the ratio "
            "belongs to another view; the bar is used"
        ),
        ratio=ratio.m_per_unit,
    )


def ratio_verdict(
    ratio: Scale, estimate: Scale, rooms: Sequence[Room], pages: Sequence[Page]
) -> Verdict | None:
    """A printed ratio (no bar) and the door estimate a known slip apart, which no 10% note
    covers: the room labels' printed areas pick one when they agree with it only
    (`label_pick`); else the ratio stays and every area and length is held (SCALE_SLIP). None
    when there is no slip."""
    if ratio.m_per_unit is None or estimate.m_per_unit is None:
        return None
    found = slip(ratio.m_per_unit, estimate.m_per_unit)
    if found is None:
        return None
    apart = (
        f"the printed scale {ratio.text} ({mm_per_px(ratio.m_per_unit)}) is {_times(found)} the "
        f"scale estimated from the doors ({mm_per_px(estimate.m_per_unit)}): {found.cause}"
    )
    match label_pick(rooms, pages, ratio, estimate):
        case "first":
            return Verdict(note=f"{apart}; the areas printed in the rooms agree with the ratio")
        case "second":
            return Verdict(
                note=f"{apart}; the areas printed in the rooms agree with the doors: the ratio "
                "is not used",
                keep_estimate=True,
            )
        case None:
            return Verdict(note=f"{SCALE_SLIP}measured where {apart}, so one of the two is misread")


def _times(found: Signature) -> str:
    """The first scale against the second: "4/3 times", or "3/4 of" (the inverse factor)."""
    if found.larger == "first":
        return f"{found.name} times"
    top, _, bottom = found.name.partition("/")
    return f"{bottom}/{top} of" if bottom else f"1/{found.name} of"

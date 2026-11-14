"""The scale of a sheet, read from the sheet alone: the printed ratio ("1:100", "1/4\" = 1'-0\"")
and the drawn scale bar. A PDF point is 1/72 inch of paper, so a printed ratio gives metres per
point without any guess.

A sheet that prints several different ratios (a plan at 1/8", its details at 3") has no one
scale: each belongs to a view, so no ratio is the sheet's, and a note lists them. A ratio printed
next to a slope word ("(1:12 RAMP SLOPE)", "SLOPE | 1:10 MAX") is a slope, not a scale.

The bar is a second reading of the same quantity. When both are there and agree, the ratio gives
the value. When they differ by more than stage 8's tolerance, the bar does (docs/PIPELINE.md
section 2: the measured value over the text), a note says so, and `PdfSecondCounter` hands both
readings to stage 8, which lists them as a conflict.
"""

import re
from collections import defaultdict
from itertools import pairwise

from app.adapters.vector_pdf.objects import FILL_NONE, Bounds, PdfPage, PdfPath
from app.core.drawing.model import Scale, ScaleEvidence
from app.core.pipeline.printed import imperial_scales
from app.core.pipeline.second_count import TOLERANCE, differ

M_PER_PT_ON_PAPER = 25.4 / 72 / 1000
RATIO = re.compile(r"(?<![\d.,:])1\s*:\s*(\d{1,4})(?![\d.,:])")
SLOPE_WORD = r"(?:slopes?|ramps?|gradient|falls?|gefälle|neigung|steigung|rampe|kaltevuus)"
SLOPE_QUALIFIER = r"(?:max(?:imum)?|min(?:imum)?|grade|pitch)"
# a slope word up to three characters before a ratio ("SLOPE | 1:10") or after it ("1:12 RAMP"),
SLOPE_BEFORE = re.compile(rf"\b{SLOPE_WORD}\W{{0,3}}$", re.IGNORECASE)
# or slope words and qualifiers that close the text after it ("1:10 MAX", "1:12 MAX SLOPE")
SLOPE_AFTER = re.compile(
    rf"\W{{0,3}}{SLOPE_WORD}\b|(?:\s+(?:{SLOPE_WORD}|{SLOPE_QUALIFIER})\b)+\W*$", re.IGNORECASE
)
PRINTED_AREA = re.compile(r"(\d+[.,]\d+)\s*m²")
BAR_LABEL = re.compile(r"(\d+)(?:\s*m)?")
BAR_FILLS = ((0, 0, 0), (255, 255, 255))
BAR_HEIGHT = (2.0, 8.0)  # points


def read_scale(page: PdfPage) -> tuple[Scale, tuple[str, ...]]:
    """The scale in metres per point of `page`, and notes about it."""
    printed, bar = printed_scales(page), read_bar(page)
    ratio = sheet_ratio(printed)
    several: tuple[str, ...] = ()
    if printed and ratio is None:
        texts: dict[float, str] = {}
        for value, text, _ in printed:
            texts.setdefault(value, text)
        several = (
            f"scale: the sheet prints {len(texts)} different scales ({', '.join(texts.values())}),"
            " one per view; none of them is the sheet's",
        )
    evidence: list[ScaleEvidence] = []
    if ratio:
        evidence.append("scale_text")
    if bar:
        evidence.append("scale_bar")
    if any(PRINTED_AREA.fullmatch(text.text) for text in page.texts):
        evidence.append("printed_areas")
    if ratio and bar:
        value, text, _ = ratio
        off = abs(bar[0] - value) / max(bar[0], value)
        if differ(value, bar[0], TOLERANCE):
            source = (
                f"scale bar: its length against its metre label; the text {text} is {off:.1%} off"
            )
            note = f"scale: the bar and the text {text} disagree by {off:.1%}; the bar is used"
            return _scaled(bar[0], evidence, text, source), (note,)
        source = f"sheet text {text}; the scale bar differs by {off:.1%}"
        return _scaled(value, evidence, text, source), ()
    if ratio:
        value, text, _ = ratio
        return _scaled(value, evidence, text, f"sheet text {text}; no scale bar found"), ()
    if bar:
        source = "scale bar: its length against its metre label"
        return _scaled(bar[0], evidence, None, source), several
    if several:
        return Scale(status="no_scale", source="several printed scales and no scale bar"), several
    return Scale(status="no_scale", source="no scale text and no scale bar on the sheet"), ()


def read_ratio(page: PdfPage) -> tuple[float, str, Bounds | None] | None:
    """Metres per point from the sheet's printed ratio, the ratio as printed ("1:100"), and where
    it is printed when one text object holds it; None when the sheet prints none, or several
    different ones."""
    return sheet_ratio(printed_scales(page))


def sheet_ratio(
    printed: list[tuple[float, str, Bounds | None]],
) -> tuple[float, str, Bounds | None] | None:
    """The first of `printed` when every printed ratio is the same, else None."""
    if not printed or len({value for value, _, _ in printed}) > 1:
        return None
    return printed[0]


def printed_scales(page: PdfPage) -> list[tuple[float, str, Bounds | None]]:
    """Every ratio the sheet prints, as `read_ratio` gives one. A ratio 1:N is read one line of
    the page text at a time, so a label broken into one character per line ("1", ":", "1", "2")
    is not read. It is a slope, and skipped, when every text object that prints it prints it as
    one (`is_slope`), or, when no one object holds it, its line does: the page text joins the
    objects on one baseline, so a word far off on the line ("RAMP UP") would read as next to it.
    An imperial ratio is read from each text object on its own (`printed.imperial_scales`):
    across objects, a view number or a ZIP code before a fraction would be read as whole
    inches."""
    printed: list[tuple[float, str, Bounds | None]] = []
    for line in page.text.splitlines():
        for ratio in RATIO.finditer(line):
            places = [
                (text, found)
                for text in page.texts
                for found in RATIO.finditer(text.text)
                if found.group(1) == ratio.group(1)
            ]
            scales = [text.bounds for text, found in places if not is_slope(text.text, found)]
            if (not scales) if places else is_slope(line, ratio):
                continue
            at = scales[0] if scales else None
            printed.append((int(ratio.group(1)) * M_PER_PT_ON_PAPER, f"1:{ratio.group(1)}", at))
    for text in page.texts:
        for value, as_printed in imperial_scales(text.text):
            printed.append((value * M_PER_PT_ON_PAPER, as_printed, text.bounds))
    return printed


def is_slope(text: str, ratio: re.Match[str]) -> bool:
    """Whether `ratio`, found in `text`, is printed as a slope: a slope word up to three
    characters before or after it ("SLOPE | 1:10", "(1:12 RAMP SLOPE)"), or slope words, max,
    min, grade or pitch closing the text after it ("1:10 MAX"). A word further off names
    something else: "RAMP LEVEL PLAN 1:100", "SLAB ON GRADE 1:50", "1:100 MAX SHEET SIZE A1"."""
    before = SLOPE_BEFORE.search(text, 0, ratio.start())
    return before is not None or SLOPE_AFTER.match(text, ratio.end()) is not None


def _scaled(value: float, evidence: list[ScaleEvidence], text: str | None, source: str) -> Scale:
    return Scale(
        status="scaled", m_per_unit=value, evidence=tuple(evidence), text=text, source=source
    )


def _is_block(path: PdfPath) -> bool:
    """A filled black or white rectangle as high as a scale bar."""
    x0, y0, x1, y1 = path.bounds
    return (
        path.segments in (4, 5)
        and path.fill_mode != FILL_NONE
        and path.fill in BAR_FILLS
        and BAR_HEIGHT[0] <= y1 - y0 <= BAR_HEIGHT[1]
        and x1 - x0 > 3
    )


def read_bar(page: PdfPage) -> tuple[float, Bounds] | None:
    """Metres per point from a scale bar, and where the bar is: a row of touching blocks, at
    least one black, with metre labels next to it; the largest label is the length of the whole
    bar."""
    rows: dict[tuple[int, int], set[tuple[float, float]]] = defaultdict(set)
    black: set[tuple[int, int]] = set()
    for path in filter(_is_block, page.paths):
        x0, y0, x1, y1 = path.bounds
        row = (round(y0), round(y1))
        rows[row].add((round(x0, 1), round(x1, 1)))
        if path.fill == (0, 0, 0):
            black.add(row)
    bars = [
        (sorted(blocks), row) for row, blocks in rows.items() if row in black and len(blocks) >= 2
    ]
    for blocks, (top, bottom) in sorted(bars, key=lambda bar: -len(bar[0])):
        if any(abs(a[1] - b[0]) > 1.0 for a, b in pairwise(blocks)):
            continue
        left, right = blocks[0][0], blocks[-1][1]
        labels = [
            int(found.group(1))
            for text in page.texts
            if (found := BAR_LABEL.fullmatch(text.text))
            and left - 5 <= text.centre[0] <= right + 15
            and abs(text.centre[1] - (top + bottom) / 2) < 25
        ]
        if labels and max(labels) > 0:
            return max(labels) / (right - left), (left, top, right, bottom)
    return None

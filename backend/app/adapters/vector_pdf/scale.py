"""The scale of a sheet, read from the sheet alone: the printed ratio ("1:100") and the drawn scale
bar. A PDF point is 1/72 inch of paper, so a ratio 1:N gives metres per point without any guess.

The bar is a second reading of the same quantity. When both are there the ratio gives the value and
the bar is compared with it; a difference above 2% is written in the notes, not hidden.
"""

import re
from collections import defaultdict
from itertools import pairwise

from app.adapters.vector_pdf.objects import FILL_NONE, PdfPage, PdfPath
from app.core.drawing.model import Scale, ScaleEvidence

M_PER_PT_ON_PAPER = 25.4 / 72 / 1000
RATIO = re.compile(r"(?<![\d.,:])1\s*:\s*(\d{1,4})(?![\d.,:])")
PRINTED_AREA = re.compile(r"\d+[.,]\d+\s*m²")
BAR_LABEL = re.compile(r"(\d+)(?:\s*m)?")
BAR_FILLS = ((0, 0, 0), (255, 255, 255))
BAR_HEIGHT = (2.0, 8.0)  # points
AGREE = 0.02


def read_scale(page: PdfPage) -> tuple[Scale, tuple[str, ...]]:
    """The scale in metres per point of `page`, and notes about it."""
    ratio = RATIO.search(page.text)
    bar = _bar_m_per_pt(page)
    evidence: list[ScaleEvidence] = []
    if ratio:
        evidence.append("scale_text")
    if bar:
        evidence.append("scale_bar")
    if any(PRINTED_AREA.fullmatch(text.text) for text in page.texts):
        evidence.append("printed_areas")
    if ratio:
        value = int(ratio.group(1)) * M_PER_PT_ON_PAPER
        text = f"1:{ratio.group(1)}"
        if bar is None:
            return _scaled(value, evidence, text, f"sheet text {text}; no scale bar found"), ()
        off = abs(bar / value - 1)
        source = f"sheet text {text}; the scale bar differs by {off:.1%}"
        notes = () if off <= AGREE else (f"scale: the bar and the text {text} disagree: {source}",)
        return _scaled(value, evidence, text, source), notes
    if bar:
        return _scaled(bar, evidence, None, "scale bar: its length against its metre label"), ()
    return Scale(status="no_scale", source="no scale text and no scale bar on the sheet"), ()


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


def _bar_m_per_pt(page: PdfPage) -> float | None:
    """Metres per point from a scale bar: a row of touching blocks, at least one black, with
    metre labels next to it; the largest label is the length of the whole bar."""
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
            return max(labels) / (right - left)
    return None

"""`legend` without a model call: the sheet's legend and printed scale, read with the local OCR
(rapidocr, app/adapters/raster_ocr). The legend is the block under a line headed "Legend" (in the
dataset's languages), else, with no such word (a Revit export prints none), the longest column of
text lines that each have a compact sample of ink to their left, the samples' left edges aligned.
An entry's sample is the ink left of its label, other text blanked, cut at the first blank gap: a
thin stroke at least `LINE` times longer than tall is a line style (a run), other ink a symbol;
a line with no sample is a group heading ("Heating") for the entries under it. The printed scale
is the first text line that states a ratio ("1:50") and any scale bar: a long thin bar ending
just left of a text line "<n> m", which agrees with a ratio the page prints, if it prints one
(implies a resolution in AGREE_DPI at it).

Shortcut: one legend block, top-down; a legend in several columns is read as its longest one;
upgrade with the VLM legend reader (spec, open decision 2). A scale bar is taken as 0 to the
printed length from its left end; a bar labelled at several ticks reads its last.
"""

import hashlib
import re
from collections.abc import Sequence
from typing import Protocol

import cv2
import numpy as np

from app.adapters.discipline_pictures import page_box, read_image
from app.adapters.discipline_pictures.cleanup import clean_page
from app.adapters.printed_scale import stated_dpi
from app.adapters.raster_ocr.reader import Quad
from app.core.drawing.model import Scale
from app.core.picture_facts import LegendEntry, PictureReading
from app.core.pipeline.model import DrawingFile, Sheet
from app.core.pipeline.ports import DrawingFiles
from app.core.pipeline.printed import (
    INCH_M,
    PrintedSheet,
    ScaleBar,
    printed_scale,
    ratio_of,
    trusted_dpi,
)

HEADER = re.compile(
    r"^\W*(?:legend|legende|legenda|leyenda|légende|selite|selitykset|merkkien\s+selitykset|"
    r"merkintöjen\s+selitykset|teckenförklaring|zeichenerklärung|symbol(?:s|e|er|it)?)\b",
    re.I,
)
INK = 200  # grey level below which a pixel is drawn
GAP = 3.0  # line heights between two entries that end the legend
REACH = 4.0  # line heights left of a label where its sample may end, at most
CUT = 0.5  # a blank gap of this many line heights ends a sample
BAND = 0.3  # line heights above and below a label where its sample may reach
WIDE = 8.0  # a legend sample is at most this many line heights long (a wall runs on)
LINE = 4.0  # a line style's sample is this many times longer than tall, at least
THIN = 0.35  # and at most this many line heights tall (a long radiator symbol is thicker)
PAD = 2  # pixels kept around a sample's ink
NO_SCALE = Scale(status="no_scale")
# OCR reads a symbol as a glyph ("目"): a line with no Latin letter or digit is a drawing, not
# text (every language of the dataset is written in Latin letters); a glyph of one or two
# characters ("O" for a circle) is a symbol too
LATIN = re.compile(r"[A-Za-z0-9\u00c0-\u024f]")
GLYPH = 2
SPECK = 0.04  # ink smaller than this many square line heights is scan noise
ROW_GAP = 2  # this many blank pixel rows part one legend row's sample from the next's
# "5 m", not "m:" text, "mm" or an area ("5 m2"); OCR on a scan glues the label to its ratio
# ("5 m1:100", "5m1:100") or reads a speck as a period ("5.m 1:100")
BAR_LABEL = re.compile(r"^\W*(\d+(?:[.,]\d+)?)\.?\s*m(?:\b(?!\s*:)|(?=\s*1\s*:\s*\d))", re.I)
# The resolution a bar may imply at a printed ratio: wider than a stated one's (DPI_RANGE), since a
# 72 or 96 dpi screen export or a photo of a large sheet is real; a misread is far below it (clinic:
# a "15 m" pipe stub at 1:100 implies 14 dpi; the demo pictures' true bar implies 100 dpi)
AGREE_DPI = (40.0, 1200.0)

Line = tuple[str, tuple[float, float, float, float]]  # text, box in pixels
Ink = tuple[int, int, int, int]  # x0, y0, x1, y1 in pixels, ends exclusive


class TextEngine(Protocol):
    """rapidocr's detection and recognition (raster_ocr.RapidOcrEngine)."""

    def detect(self, image: np.ndarray) -> list[Quad]: ...
    def recognise(self, crops: Sequence[np.ndarray]) -> list[tuple[str, float]]: ...
    def cut(self, image: np.ndarray, quad: Quad) -> np.ndarray: ...


def read_legend(
    rgb: np.ndarray, engine: TextEngine
) -> tuple[tuple[LegendEntry, ...] | None, PrintedSheet]:
    """The page's legend (None: none found) and its printed scale: ratio text and scale bars."""
    lines = _lines(rgb, engine)
    # salt out and light even, not straightened: the legend's boxes are on the page as given
    gray = clean_page(rgb.min(axis=2) if rgb.ndim == 3 else rgb, straighten=False).gray.copy()
    texts = [line for line in lines if _is_text(line[0])]
    for _, (x0, y0, x1, y1) in texts:  # a sample is ink that is not text
        gray[int(y0) : int(y1) + 1, int(x0) : int(x1) + 1] = 255
    h = float(np.median([box[3] - box[1] for _, box in texts])) if texts else 0.0
    _despeckle(gray, SPECK * h * h)
    samples = {n: _sample(gray, box, h) for n, (_, box) in enumerate(texts)}
    ratios = [ratio for text, _ in lines if (ratio := ratio_of(text)) is not None]
    printed = PrintedSheet(
        printed_scale=next((text for text, _ in lines if ratio_of(text) is not None), None),
        bars=tuple(
            bar
            for text, box in texts
            if (bar := _bar(gray, text, box, h)) and _agrees(bar, ratios, gray.shape[1])
        ),
    )
    block = _under_header(texts, h) or _column(texts, samples, h)
    height, width = gray.shape
    entries: list[LegendEntry] = []
    group: str | None = None
    for n in block:
        ink = samples[n]
        if ink is None:
            group = texts[n][0]
            continue
        x0, y0, x1, y1 = ink
        entries.append(
            LegendEntry(
                label=texts[n][0],
                group=group,
                line=x1 - x0 >= LINE * (y1 - y0) and y1 - y0 <= THIN * h,
                box=page_box(x0 - PAD, y0 - PAD, x1 + PAD, y1 + PAD, width, height),
            )
        )
    return (tuple(entries) or None), printed


def _is_text(text: str) -> bool:
    """Words, not symbols OCR read as glyphs ("O" for a circle, a symbol column as one line)."""
    return len(text) > GLYPH and 2 * len(LATIN.findall(text)) >= len(text)


def _despeckle(gray: np.ndarray, area: float) -> None:
    """Blank the specks of ink a scan leaves, smaller than `area` pixels, in place."""
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        (gray < INK).astype(np.uint8), connectivity=8
    )
    small = np.nonzero(stats[:, cv2.CC_STAT_AREA] < area)[0]
    small = small[small > 0]  # 0 is the background
    if count > 1 and len(small):
        gray[np.isin(labels, small)] = 255


def _under_header(texts: list[Line], h: float) -> list[int]:
    """The lines under a "Legend" header, top-down, to a gap of GAP line heights."""
    header = next((box for text, box in texts if HEADER.match(text)), None)
    if header is None:
        return []
    hx0, _, _, last = header
    below = sorted(
        (n for n, (_, box) in enumerate(texts) if box[1] >= last - 0.2 * h and hx0 - h <= box[0]),
        key=lambda n: texts[n][1][1],
    )
    block: list[int] = []
    for n in below:
        x0, y0, _, y1 = texts[n][1]
        if y0 - last > GAP * h:
            break
        if x0 <= hx0 + 12 * h and texts[n][1] != header:  # beside the legend is not under it
            block.append(n)
            last = y1
    return block


def _column(texts: list[Line], samples: dict[int, Ink | None], h: float) -> list[int]:
    """With no header: the longest run of at least two rows whose samples are compact, left-aligned
    within a line height and no more than GAP line heights apart; with the sample-less lines that
    start at the samples' left edge among or just above them (the group headings)."""
    rows = sorted(
        (
            n
            for n, ink in samples.items()
            if ink and ink[2] - ink[0] <= WIDE * h and ink[3] - ink[1] <= 2 * h
        ),
        key=lambda n: texts[n][1][1],
    )
    best: list[int] = []
    for first in rows:
        left = (samples[first] or (0, 0, 0, 0))[0]
        run = [first]
        for n in rows:
            if texts[n][1][1] <= texts[run[-1]][1][1]:
                continue
            if abs((samples[n] or (0, 0, 0, 0))[0] - left) > h:
                continue
            if texts[n][1][1] - texts[run[-1]][1][3] > GAP * h:
                break
            run.append(n)
        best = max(best, run, key=len)
    if len(best) < 2:
        return []
    left = (samples[best[0]] or (0, 0, 0, 0))[0]
    top, bottom = texts[best[0]][1][1] - GAP * h, texts[best[-1]][1][3]
    headings = [
        n for n, ink in samples.items()
        if ink is None and abs(texts[n][1][0] - left) <= h and top <= texts[n][1][1] <= bottom
    ]  # fmt: skip
    return sorted(best + headings, key=lambda n: texts[n][1][1])


def _sample(gray: np.ndarray, box: tuple[float, float, float, float], h: float) -> Ink | None:
    """The ink just left of a text line: its right end within REACH line heights of the text, cut
    at blank gaps of CUT line heights, the rows nearest the line's middle (not the next row's
    sample); None when there is none."""
    x0, y0, _, y1 = box
    top, bottom = int(max(0, y0 - BAND * h)), int(min(gray.shape[0], y1 + BAND * h))
    right, reach = int(x0), int(max(0, x0 - REACH * h))
    if right <= reach or bottom <= top:
        return None
    ink = gray[top:bottom, :right] < INK
    cols = _runs(ink.any(axis=0), CUT * h)
    if not cols or cols[-1][1] <= reach:
        return None
    middle = (y0 + y1) / 2 - top
    rows = _runs(ink[:, cols[-1][0] : cols[-1][1]].any(axis=1), ROW_GAP)
    ya, yb = min(rows, key=lambda run: abs((run[0] + run[1]) / 2 - middle))
    xa, xb = _runs(ink[ya:yb].any(axis=0), CUT * h)[-1]
    return xa, top + ya, xb, top + yb


def _runs(inked: np.ndarray, gap: float) -> list[tuple[int, int]]:
    """The runs of True (start, end exclusive), joined across blanks shorter than `gap`."""
    runs: list[tuple[int, int]] = []
    for x in np.nonzero(inked)[0].tolist():
        if runs and x - runs[-1][1] < gap:
            runs[-1] = (runs[-1][0], x + 1)
        else:
            runs.append((x, x + 1))
    return runs


def _bar(
    gray: np.ndarray, text: str, box: tuple[float, float, float, float], h: float
) -> ScaleBar | None:
    """A scale bar: a long thin bar ending just left of a text line "<n> m"."""
    found = BAR_LABEL.match(text)
    ink = _sample(gray, box, h) if found else None
    if found is None or ink is None:
        return None
    x0, y0, x1, y1 = ink
    if x1 - x0 < LINE * (y1 - y0) or y1 - y0 > h:
        return None
    height, width = gray.shape
    mid = (y0 + y1) / 2 / height
    return ScaleBar(
        page=1,
        start=(x0 / width, mid),
        end=(x1 / width, mid),
        length_m=float(found[1].replace(",", ".")),
        text=text,
    )


def _agrees(bar: ScaleBar, ratios: list[float], width: int) -> bool:
    """A bar agrees with the printed ratios when, at one of them, it implies a resolution in
    AGREE_DPI; with no ratio printed, any bar does. A size label OCR'd as "15 m" beside a pipe stub
    implies 14 dpi at 1:100 (clinic, 11x off)."""
    px = (bar.end[0] - bar.start[0]) * width
    if not ratios or px <= 0:
        return not ratios
    return any(
        AGREE_DPI[0] <= ratio * INCH_M * px / bar.length_m <= AGREE_DPI[1] for ratio in ratios
    )


def _lines(rgb: np.ndarray, engine: TextEngine) -> list[Line]:
    image = rgb if rgb.ndim == 3 else np.stack([rgb] * 3, axis=2)
    quads = engine.detect(image)
    texts = engine.recognise([engine.cut(image, quad) for quad in quads])
    lines: list[Line] = []
    for quad, (text, _) in zip(quads, texts, strict=True):
        xs, ys = [x for x, _ in quad], [y for _, y in quad]
        if LATIN.search(text):
            lines.append((text.strip(), (min(xs), min(ys), max(xs), max(ys))))
    return lines


class OcrLegend:
    """`LegendOf` and `ScaleOf` of the readers (app/adapters/discipline_pictures/__init__.py),
    from one OCR pass per page (kept by the file's sha256 while the lane reads it). The scale is
    the printed ratio at the resolution the file states, trusted as `printed.trusted_dpi` says;
    no estimate from doors (spec, Method 1)."""

    def __init__(self, files: DrawingFiles, engine: TextEngine) -> None:
        self._files = files
        self._engine = engine
        self._read: dict[str, tuple[tuple[LegendEntry, ...] | None, PrintedSheet]] = {}
        self.notes: list[str] = []

    def _of(
        self, source: DrawingFile, sheet: Sheet
    ) -> tuple[tuple[LegendEntry, ...] | None, PrintedSheet]:
        data = self._files.read(source.path)
        key = hashlib.sha256(data).hexdigest()
        if key not in self._read:
            if len(self._read) > 4:  # a few pages at most: each lane call reads one
                self._read.clear()
            rgb = read_image("legend", data, source, sheet)
            if isinstance(rgb, PictureReading):
                self.notes += rgb.notes
                self._read[key] = (None, PrintedSheet())
            else:
                self._read[key] = read_legend(rgb, self._engine)
        return self._read[key]

    def legend(self, source: DrawingFile, sheet: Sheet) -> tuple[LegendEntry, ...] | None:
        return self._of(source, sheet)[0]

    def scale(self, source: DrawingFile, sheet: Sheet) -> Scale:
        printed = self._of(source, sheet)[1]
        dpi = trusted_dpi(stated_dpi(self._files.read(source.path)))
        found = printed_scale(printed, sheet.pages, dpi)
        return NO_SCALE if found is None else found

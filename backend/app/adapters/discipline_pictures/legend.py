"""`legend` without a model call: the sheet's legend and printed scale, read with the local OCR
(rapidocr, app/adapters/raster_ocr). The legend is the block under a line headed "Legend" (in the
dataset's languages); each line below it is an entry whose sample is the ink to the left of its
label: a thin stroke at least `LINE` times longer than tall is a line style (a run), other ink a
symbol, and a line with no ink to its left is a group heading ("Heating") for the entries under
it. The block ends at a gap of `GAP` line heights. The printed scale is the first text line that
states a ratio ("1:50").

Shortcut: one legend block, read top-down under its header; a legend in several columns, or one
with no header word, is not read (`None`): upgrade with the VLM legend reader (spec, open
decision 2).
"""

import hashlib
import re
from collections.abc import Sequence
from typing import Protocol

import numpy as np

from app.adapters.discipline_pictures import page_box, read_image
from app.adapters.printed_scale import stated_dpi
from app.adapters.raster_ocr.reader import Quad
from app.core.drawing.model import Scale
from app.core.picture_facts import LegendEntry, PictureReading
from app.core.pipeline.model import DrawingFile, Sheet
from app.core.pipeline.ports import DrawingFiles
from app.core.pipeline.printed import PrintedSheet, printed_scale, ratio_of, trusted_dpi

HEADER = re.compile(
    r"^\W*(?:legend|legende|legenda|leyenda|légende|selite|selitykset|merkkien\s+selitykset|"
    r"merkintöjen\s+selitykset|teckenförklaring|zeichenerklärung|symbol(?:s|e|er|it)?)\b",
    re.I,
)
INK = 200  # grey level below which a pixel is drawn
GAP = 3.0  # line heights between two entries that end the legend
LEFT = 0.3  # line heights left of the header's left edge where a sample may start
LINE = 4.0  # a line style's sample is this many times longer than tall, at least
THIN = 0.35  # and at most this many line heights tall (a long radiator symbol is thicker)
PAD = 2  # pixels kept around a sample's ink
NO_SCALE = Scale(status="no_scale")
# OCR reads a symbol as a glyph ("目"): a line with no Latin letter or digit is a drawing, not
# text (every language of the dataset is written in Latin letters)
LATIN = re.compile(r"[A-Za-z0-9\u00c0-\u024f]")

Line = tuple[str, tuple[float, float, float, float]]  # text, box in pixels


class TextEngine(Protocol):
    """rapidocr's detection and recognition (raster_ocr.RapidOcrEngine)."""

    def detect(self, image: np.ndarray) -> list[Quad]: ...
    def recognise(self, crops: Sequence[np.ndarray]) -> list[tuple[str, float]]: ...
    def cut(self, image: np.ndarray, quad: Quad) -> np.ndarray: ...


def read_legend(
    rgb: np.ndarray, engine: TextEngine
) -> tuple[tuple[LegendEntry, ...] | None, str | None]:
    """The page's legend (None: no header found, or nothing under it) and its printed scale."""
    lines = _lines(rgb, engine)
    scale = next((text for text, _ in lines if ratio_of(text) is not None), None)
    header = next((box for text, box in lines if HEADER.match(text)), None)
    if header is None:
        return None, scale
    hx0, _, _, hy1 = header
    h = header[3] - header[1]
    gray = rgb.min(axis=2) if rgb.ndim == 3 else rgb
    height, width = gray.shape
    below = sorted(
        (line for line in lines if line[1][1] >= hy1 - 0.2 * h and hx0 - h <= line[1][0]),
        key=lambda line: line[1][1],
    )
    entries: list[LegendEntry] = []
    group: str | None = None
    last = hy1
    for text, (x0, y0, _, y1) in below:
        if y0 - last > GAP * h:
            break
        if x0 > hx0 + 12 * h:  # beside the legend, not under it
            continue
        last = y1
        left, right = int(max(0, hx0 - LEFT * h)), int(x0 - 0.25 * h)
        top, bottom = int(max(0, y0 - 0.6 * h)), int(min(height, y1 + 0.6 * h))
        ys, xs = np.nonzero(gray[top:bottom, left:right] < INK) if right > left else ((), ())
        if len(xs) == 0:
            group = text
            continue
        bx0, bx1 = left + int(np.min(xs)), left + int(np.max(xs)) + 1
        by0, by1 = top + int(np.min(ys)), top + int(np.max(ys)) + 1
        long, tall = bx1 - bx0, by1 - by0
        entries.append(
            LegendEntry(
                label=text,
                group=group,
                line=long >= LINE * tall and tall <= THIN * h,
                box=page_box(bx0 - PAD, by0 - PAD, bx1 + PAD, by1 + PAD, width, height),
            )
        )
    return (tuple(entries) or None), scale


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
        self._read: dict[str, tuple[tuple[LegendEntry, ...] | None, str | None]] = {}
        self.notes: list[str] = []

    def _of(
        self, source: DrawingFile, sheet: Sheet
    ) -> tuple[tuple[LegendEntry, ...] | None, str | None]:
        data = self._files.read(source.path)
        key = hashlib.sha256(data).hexdigest()
        if key not in self._read:
            if len(self._read) > 4:  # a few pages at most: each lane call reads one
                self._read.clear()
            rgb = read_image("legend", data, source, sheet)
            if isinstance(rgb, PictureReading):
                self.notes += rgb.notes
                self._read[key] = (None, None)
            else:
                self._read[key] = read_legend(rgb, self._engine)
        return self._read[key]

    def legend(self, source: DrawingFile, sheet: Sheet) -> tuple[LegendEntry, ...] | None:
        return self._of(source, sheet)[0]

    def scale(self, source: DrawingFile, sheet: Sheet) -> Scale:
        text = self._of(source, sheet)[1]
        dpi = trusted_dpi(stated_dpi(self._files.read(source.path)))
        found = printed_scale(PrintedSheet(printed_scale=text), sheet.pages, dpi)
        return NO_SCALE if found is None else found

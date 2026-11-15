"""`glyphs`: plan symbols by a trained glyph detector (DISCIPLINE_PICTURES=glyphs).

A YOLO26 detector (ONNX, on the CPU) finds every drawn glyph on the page and names its style: one
of 8 shapes x 3 fills, x the number printed beside it past 24 legend labels (none, 2, 3): 72
classes. It does not know what a style means; the legend does. A legend row's style is the
strongest detection inside its sample box; a detection on the plan (not on a legend row: the
sample box widened to the page's right edge) of a style takes the label of the first row of that
style. A row nobody detected, and a style no row has, read nothing.

The page is read in TILE px tiles at its own resolution, STRIDE apart, so a 24 px symbol stays 24
px; across tiles two detections whose centres are within SAME_PX are one (the stronger stays).

The model folder (`DISCIPLINE_GLYPHS_MODEL`) holds `model.onnx` (Ultralytics' end-to-end export:
one output (1, N, 6) of x0, y0, x1, y1 in the tile's pixels, score, class). Trained on rendered
bsc-clinic pictures (prototypes/pic-det, report .agents/exp/pics-pic-det.md). Weights are never
committed. Like `template`, it cannot run without a legend.

DISCIPLINE_GLYPHS_LEGEND=glyphs (default `ocr`: the OCR legend, legend.py) reads the legend from
the detector's own glyphs instead (`glyph_legend`): a legend row is a detected glyph with a
printed label right of it, the rows stacked in one column, each label read by OCR recognition of
its band (no text detection, which misses label lines on scans). DigitalHub held out, YOLO26-M
weights: symbols counted within 10% on 27/54 units, P 0.95 R 0.81, against 9/54 with the OCR
legend (.agents/exp/pics-pipe-glyph.md, 2026-11-15).
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import numpy as np

from app.adapters.discipline_pictures import (
    NO_LEGEND,
    LegendOf,
    nothing,
    page_box,
    pixels,
    read_image,
)
from app.adapters.discipline_pictures.legend import _is_text
from app.core.ifc_facts import Spot
from app.core.picture_facts import LegendEntry, PictureReading, Sighting
from app.core.pipeline.model import DrawingFile, Sheet
from app.core.pipeline.ports import DrawingFiles

READER = "glyphs"
TILE, STRIDE = 1024, 768
SAME_PX = 8.0  # two detections whose centres are this close are one
SCORE = 0.25  # the detector's score below which a detection is dropped (Ultralytics' default)
PAD = 6  # px around a legend sample box that still counts as the sample
# glyph_legend, in glyph heights (the median detected glyph's), fitted on bsc-clinic renders only
STEP = 4.0  # between the centres of two stacked legend glyphs, at most (a line row may sit between)
ALIGN = 1.0  # the left edges of one legend column's glyphs differ by at most this
LONG = 4.0  # a label band is at least this wide
TALL = 0.4  # and has at least this many inked rows (a pipe running right of a glyph has fewer)
BLANK = 3.0  # blank columns that end a label
INK = 160  # grey level below which a pixel is ink (scans print lighter than clean pages)


@dataclass(frozen=True)
class Glyph:
    style: int
    score: float
    box: tuple[float, float, float, float]  # page pixels

    @property
    def centre(self) -> tuple[float, float]:
        return (self.box[0] + self.box[2]) / 2, (self.box[1] + self.box[3]) / 2


Detect = Callable[[np.ndarray], list[Glyph]]  # one RGB tile -> its glyphs in tile pixels
# OCR recognition of text-line crops (raster_ocr's RapidOcrEngine.recognise): (text, score) each
Recognise = Callable[[Sequence[np.ndarray]], list[tuple[str, float]]]


class GlyphReader:
    def __init__(
        self,
        files: DrawingFiles,
        legend_of: LegendOf,
        model: Path,
        recognise: Recognise | None = None,  # given: the legend is read from the glyphs
    ) -> None:
        self._files = files
        self._legend_of = legend_of
        self._model = model
        self._recognise = recognise

    def read(self, source: DrawingFile, sheet: Sheet) -> PictureReading:
        if self._recognise is not None:
            rgb = read_image(READER, self._files.read(source.path), source, sheet)
            if isinstance(rgb, PictureReading):
                return rgb
            glyphs = tiled(rgb, onnx_detector(self._model))
            return own_legend_reading(rgb, glyphs, self._recognise)
        legend = self._legend_of(source, sheet)
        if legend is None:
            return nothing(READER, None, f"{READER}: {NO_LEGEND}")
        rgb = read_image(READER, self._files.read(source.path), source, sheet)
        if isinstance(rgb, PictureReading):
            return rgb.model_copy(update={"legend": legend})
        return read_glyphs(rgb, legend, onnx_detector(self._model))


def read_glyphs(rgb: np.ndarray, legend: tuple[LegendEntry, ...], detect: Detect) -> PictureReading:
    """The legend's symbols on the RGB page, as sightings on page 1."""
    return _reading(rgb, tiled(rgb, detect), legend)


def own_legend_reading(
    rgb: np.ndarray, glyphs: Sequence[Glyph], recognise: Recognise
) -> PictureReading:
    """The page's symbols with the legend read from its own glyphs (`glyph_legend`)."""
    legend = glyph_legend(rgb, glyphs, recognise)
    if legend is None:
        return nothing(READER, None, f"{READER}: {NO_LEGEND}")
    return _reading(rgb, glyphs, legend)


def _reading(
    rgb: np.ndarray, glyphs: Sequence[Glyph], legend: tuple[LegendEntry, ...]
) -> PictureReading:
    height, width = rgb.shape[:2]
    rows = [
        (entry.label, pixels(entry.box, width, height))
        for entry in legend
        if not entry.line and entry.box is not None
    ]
    label_of = bind(glyphs, rows)
    sightings = []
    for glyph in glyphs:
        x, y = glyph.centre
        if any(_inside(x, y, box, right=width) for _, box in rows):
            continue  # the legend's own sample
        if glyph.style in label_of:
            spot = Spot(page=1, box=page_box(*glyph.box, width, height), reader=READER)
            sightings.append(
                Sighting(label=label_of[glyph.style], spot=spot, score=round(glyph.score, 4))
            )
    sightings.sort(key=lambda s: (s.spot.box[1], s.spot.box[0]))
    read = tuple(dict.fromkeys(label_of.values()))
    missed = [label for label, _ in rows if label not in read]
    notes = (f"{READER}: no style found for the legend's {missed!r}",) if missed else ()
    return PictureReading(
        reader=READER, legend=legend, read=read, sightings=tuple(sightings), notes=notes
    )


def bind(glyphs: Sequence[Glyph], rows: Sequence[tuple[str, tuple[int, int, int, int]]]) -> dict:
    """Style -> legend label: each row's strongest glyph inside its sample box; the first row of
    a style keeps it."""
    label_of: dict[int, str] = {}
    for label, box in rows:
        inside = [g for g in glyphs if _inside(*g.centre, box)]
        if inside:
            label_of.setdefault(max(inside, key=lambda g: g.score).style, label)
    return label_of


def glyph_legend(
    rgb: np.ndarray, glyphs: Sequence[Glyph], recognise: Recognise
) -> tuple[LegendEntry, ...] | None:
    """The legend from the page's glyphs (None: no row): a glyph is a row when the band right of
    it holds text-like ink (LONG wide, TALL inked rows); rows stack into columns (left edges
    within ALIGN, centres within STEP); the column with most rows (tie: longer labels) is the
    legend, top-down, each label recognised from its band. A one-row legend is a legend."""
    if not glyphs:
        return None
    gray = rgb.min(axis=2) if rgb.ndim == 3 else rgb
    height, width = gray.shape
    gh = float(np.median([g.box[3] - g.box[1] for g in glyphs]))
    band: dict[int, tuple[int, int, int, int]] = {}
    for i, g in enumerate(glyphs):
        y0, y1 = int(max(0, g.box[1] - 0.1 * gh)), int(min(height, g.box[3] + 0.1 * gh))
        x0 = int(min(width - 1, g.box[2] + 0.15 * gh))
        x1 = _label_end(gray[y0:y1, x0:], gh) + x0
        if x1 - x0 < LONG * gh:
            continue
        if int(((gray[y0:y1, x0:x1] < INK).sum(axis=1) >= 2).sum()) >= TALL * gh:
            band[i] = (x0, y0, x1, y1)
    stacks: list[list[int]] = []
    for i in sorted(band, key=lambda i: glyphs[i].box[1]):
        g = glyphs[i]
        cy = g.centre[1]
        for stack in stacks:
            if (
                abs(glyphs[stack[0]].box[0] - g.box[0]) <= ALIGN * gh
                and 0 < cy - glyphs[stack[-1]].centre[1] <= STEP * gh
            ):
                stack.append(i)
                break
        else:
            stacks.append([i])
    if not stacks:
        return None
    best = max(stacks, key=lambda s: (len(s), sum(band[i][2] - band[i][0] for i in s)))
    texts = recognise(
        [np.ascontiguousarray(rgb[y0:y1, x0:x1]) for x0, y0, x1, y1 in (band[i] for i in best)]
    )
    entries = tuple(
        LegendEntry(
            label=text.strip(), group=None, line=False, box=page_box(*glyphs[i].box, width, height)
        )
        for (text, _), i in zip(texts, best, strict=True)
        if _is_text(text.strip())
    )
    return entries or None


def _label_end(band: np.ndarray, gh: float) -> int:
    """The right end of the ink that starts the band, cut at BLANK glyph heights of no ink; a
    column is ink with 2 dark pixels or more (one is scan salt). 0: no ink near the start."""
    inked = (band < INK).sum(axis=0) >= 2
    end = blank = 0
    for x, ink in enumerate(inked.tolist()):
        if ink:
            end, blank = x + 1, 0
        else:
            blank += 1
            if blank > BLANK * gh:
                break
    return end


def tiled(rgb: np.ndarray, detect: Detect) -> list[Glyph]:
    """The page's glyphs from TILE px tiles, in page pixels, near-duplicates across tiles merged."""
    height, width = rgb.shape[:2]
    found: list[Glyph] = []
    for top in _starts(height):
        for left in _starts(width):
            tile = rgb[top : top + TILE, left : left + TILE]
            for g in detect(tile):
                x0, y0, x1, y1 = g.box
                found.append(Glyph(g.style, g.score, (x0 + left, y0 + top, x1 + left, y1 + top)))
    kept: list[Glyph] = []
    for g in sorted(found, key=lambda g: -g.score):
        x, y = g.centre
        if all(abs(x - k.centre[0]) > SAME_PX or abs(y - k.centre[1]) > SAME_PX for k in kept):
            kept.append(g)
    return kept


def _starts(n: int) -> list[int]:
    if n <= TILE:
        return [0]
    return sorted({*range(0, n - TILE + 1, STRIDE), n - TILE})


def _inside(x: float, y: float, box: tuple[int, int, int, int], right: float | None = None) -> bool:
    x0, y0, x1, y1 = box
    return x0 - PAD <= x <= (right if right is not None else x1 + PAD) and y0 - PAD <= y <= y1 + PAD


def onnx_detector(model: Path) -> Detect:
    session = _session(model / "model.onnx")
    name = session.get_inputs()[0].name

    def detect(tile: np.ndarray) -> list[Glyph]:
        h, w = tile.shape[:2]
        canvas = np.full((TILE, TILE, 3), 114, dtype=np.uint8)  # Ultralytics' letterbox grey
        canvas[:h, :w] = tile
        x = canvas.transpose(2, 0, 1)[None].astype(np.float32) / 255.0
        (out,) = session.run(None, {name: x})
        return [g for g in decode(out[0]) if g.box[0] < w and g.box[1] < h]

    return detect


def decode(out: np.ndarray) -> list[Glyph]:
    """The raw head's (4 + classes, anchors) output: centre x, centre y, width, height in canvas
    pixels, then one score per class; each anchor's best class, at SCORE or above. Duplicates
    are left for `tiled`'s merge."""
    scores = out[4:]
    style = scores.argmax(axis=0)
    best = scores[style, np.arange(scores.shape[1])]
    keep = np.flatnonzero(best >= SCORE)
    cx, cy, bw, bh = out[:4, keep]
    return [
        Glyph(
            int(style[i]),
            float(best[i]),
            (float(x - a / 2), float(y - b / 2), float(x + a / 2), float(y + b / 2)),
        )
        for i, x, y, a, b in zip(keep, cx, cy, bw, bh, strict=True)
    ]


@cache
def _session(path: Path) -> Any:
    import onnxruntime  # only when the reader runs

    return onnxruntime.InferenceSession(str(path), providers=["CPUExecutionProvider"])

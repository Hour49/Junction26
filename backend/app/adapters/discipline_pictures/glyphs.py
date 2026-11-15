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
from app.core.ifc_facts import Spot
from app.core.picture_facts import LegendEntry, PictureReading, Sighting
from app.core.pipeline.model import DrawingFile, Sheet
from app.core.pipeline.ports import DrawingFiles

READER = "glyphs"
TILE, STRIDE = 1024, 768
SAME_PX = 8.0  # two detections whose centres are this close are one
SCORE = 0.25  # the detector's score below which a detection is dropped (Ultralytics' default)
PAD = 6  # px around a legend sample box that still counts as the sample


@dataclass(frozen=True)
class Glyph:
    style: int
    score: float
    box: tuple[float, float, float, float]  # page pixels

    @property
    def centre(self) -> tuple[float, float]:
        return (self.box[0] + self.box[2]) / 2, (self.box[1] + self.box[3]) / 2


Detect = Callable[[np.ndarray], list[Glyph]]  # one RGB tile -> its glyphs in tile pixels


class GlyphReader:
    def __init__(self, files: DrawingFiles, legend_of: LegendOf, model: Path) -> None:
        self._files = files
        self._legend_of = legend_of
        self._model = model

    def read(self, source: DrawingFile, sheet: Sheet) -> PictureReading:
        legend = self._legend_of(source, sheet)
        if legend is None:
            return nothing(READER, None, f"{READER}: {NO_LEGEND}")
        rgb = read_image(READER, self._files.read(source.path), source, sheet)
        if isinstance(rgb, PictureReading):
            return rgb.model_copy(update={"legend": legend})
        return read_glyphs(rgb, legend, onnx_detector(self._model))


def read_glyphs(rgb: np.ndarray, legend: tuple[LegendEntry, ...], detect: Detect) -> PictureReading:
    """The legend's symbols on the RGB page, as sightings on page 1."""
    height, width = rgb.shape[:2]
    glyphs = tiled(rgb, detect)
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

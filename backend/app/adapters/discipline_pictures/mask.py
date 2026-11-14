"""`mask`: the local reader of a raster plan's runs (pipes, ducts, trays). For each legend line
entry drawn in a colour of its own: the page's pixels of that colour, outside the legend, in
connected pieces; each elongated piece is one run, its length at the sheet's scale. Without a
scale there are no runs and the notes say `NO_SCALE`. A sample drawn as dashes is a dashed line:
its runs are rows of pieces of its dash length (`chained`), which a solid line of the same colour
leaves alone. A black or grey line is not read (shortcut: text and walls share its colour; read
dashed black lines when the bench draws them).

A piece of area A and outline P is taken as a strip: P = 2(L + w), A = L * w, so its length is
L = (P/2 + sqrt(P²/4 - 4A)) / 2.
"""

import math

import cv2
import numpy as np

from app.adapters.discipline_pictures import (
    NO_LEGEND,
    Dashes,
    LegendOf,
    Piece,
    ScaleOf,
    chained,
    dash_pattern,
    is_dash,
    nothing,
    page_box,
    pixels,
    read_image,
)
from app.core.ifc_facts import Spot
from app.core.picture_facts import NO_SCALE, LegendEntry, PictureReading, Run
from app.core.pipeline.model import DrawingFile, Sheet
from app.core.pipeline.ports import DrawingFiles

READER = "mask"
COLOURFUL = 60  # max - min channel: a pixel with a colour, not black or grey
SAME_COLOUR = 50  # per channel: a pixel drawn in the legend line's colour
ELONGATED = 4.0  # a run is at least this many times longer than wide (text, blobs are not)
PAD = 2  # pixels around a legend box


class MaskReader:
    def __init__(self, files: DrawingFiles, legend_of: LegendOf, scale_of: ScaleOf) -> None:
        self._files = files
        self._legend_of = legend_of
        self._scale_of = scale_of

    def read(self, source: DrawingFile, sheet: Sheet) -> PictureReading:
        legend = self._legend_of(source, sheet)
        if legend is None:
            return nothing(READER, None, f"{READER}: {NO_LEGEND}")
        m_per_unit = self._scale_of(source, sheet).m_per_unit
        if m_per_unit is None:
            return nothing(READER, legend, NO_SCALE)
        rgb = read_image(READER, self._files.read(source.path), source, sheet)
        if isinstance(rgb, PictureReading):
            return rgb.model_copy(update={"legend": legend})
        return read_runs(rgb, legend, m_per_unit * sheet.pages[0].width / rgb.shape[1])


def read_runs(rgb: np.ndarray, legend: tuple[LegendEntry, ...], m_per_px: float) -> PictureReading:
    height, width = rgb.shape[:2]
    on_legend = [pixels(e.box, width, height, PAD) for e in legend if e.box is not None]
    notes: list[str] = []
    lines: list[tuple[LegendEntry, np.ndarray, Dashes | None]] = []
    for entry in legend:
        if not entry.line or entry.box is None:
            continue
        colour = _colour(rgb, entry.box)
        if colour is None:
            notes.append(f"{READER}: the legend's {entry.label!r} has no colour of its own")
            continue
        x0, y0, x1, y1 = pixels(entry.box, width, height)
        sample = [piece for piece, _ in _pieces(_mask(rgb[y0:y1, x0:x1], colour))]
        lines.append((entry, colour, dash_pattern(sample)))
    runs: list[Run] = []
    for entry, colour, dashes in lines:
        mask = _mask(rgb, colour)
        for x0, y0, x1, y1 in on_legend:
            mask[y0:y1, x0:x1] = 0
        pieces = _pieces(mask)
        if dashes is not None:
            found = chained([piece for piece, _ in pieces], dashes)
        else:
            # a solid line leaves the dashes of a dashed line in its colour to that line
            dashed = [d for _, c, d in lines if d is not None and _same(c, colour)]
            found = [
                (p.length, p.box)
                for p, area in pieces
                if p.length * p.length >= ELONGATED * area  # length >= ELONGATED x width
                and not any(is_dash(p, d) for d in dashed)
            ]
        runs += [
            Run(
                label=entry.label,
                size=None,  # shortcut: sizes printed along a run come from the VLM tiles later
                length_m=length * m_per_px,
                spots=(Spot(page=1, box=page_box(*box, width, height), reader=READER),),
            )
            for length, box in found
        ]
    return PictureReading(
        reader=READER,
        legend=legend,
        read=tuple(entry.label for entry, _, _ in lines),
        runs=tuple(runs),
        notes=tuple(notes),
    )


def _mask(rgb: np.ndarray, colour: np.ndarray) -> np.ndarray:
    return np.all(np.abs(rgb.astype(np.int16) - colour) <= SAME_COLOUR, axis=2).astype(np.uint8)


def _same(a: np.ndarray, b: np.ndarray) -> bool:
    return bool(np.all(np.abs(a - b) <= SAME_COLOUR))


def _colour(rgb: np.ndarray, box: tuple[float, float, float, float]) -> np.ndarray | None:
    """The median colour of the coloured pixels in `box`; None when it has none."""
    x0, y0, x1, y1 = pixels(box, rgb.shape[1], rgb.shape[0])
    crop = rgb[y0:y1, x0:x1].reshape(-1, 3).astype(np.int16)
    coloured = crop[crop.max(axis=1) - crop.min(axis=1) >= COLOURFUL]
    return np.median(coloured, axis=0) if len(coloured) else None


def _pieces(mask: np.ndarray) -> list[tuple[Piece, int]]:
    """Each connected piece of `mask` as a strip (length in px, pixel box), with its area."""
    count, labels, stats, centres = cv2.connectedComponentsWithStats(mask, connectivity=8)
    pieces: list[tuple[Piece, int]] = []
    for k in range(1, count):
        x, y, w, h, area = (int(v) for v in stats[k])
        piece = (labels[y : y + h, x : x + w] == k).astype(np.uint8)
        contours, _ = cv2.findContours(piece, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        # the contour runs through the edge pixels' centres: the shape's edge is half a pixel out
        half = (sum(cv2.arcLength(c, closed=True) for c in contours) + 4) / 2
        length = (half + math.sqrt(max(0.0, half * half - 4 * area))) / 2
        cx, cy = centres[k]
        pieces.append((Piece(length, (float(cx), float(cy)), (x, y, x + w, y + h)), area))
    return pieces

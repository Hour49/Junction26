"""`template`: the second, local reader of a plan's symbols. Each legend symbol, cut from the
legend and cropped to its ink, is matched over the page (normalised cross-correlation) turned a
quarter at a time. Coarse to fine: the page is shrunk once, for all symbols, so the smallest
symbol's long side is `COARSE_SIDE` px; peaks there above `COARSE_THRESHOLD` are candidates,
matched again at full size, at three sizes around the legend's, in a window around each. Those above
`THRESHOLD` are symbols; of two overlapping, the stronger stays. A peak on the legend itself is
the legend.

The score of a sighting is its correlation peak (0..1). It cannot run without a legend, and it
does not read a photo the rectifier could not flatten (the caller does not ask it to).
"""

import cv2
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

READER = "template"
THRESHOLD = 0.75  # correlation peak for a symbol; tune on bench dev only
SIZES = (0.9, 1.0, 1.1)  # of the legend symbol's size
# px: the smallest symbol's long side on the shrunk page. On the A1 test page, 16 is twice as
# fast and misses none, 12 misses some; tune on bench dev
COARSE_SIDE = 20
COARSE_THRESHOLD = 0.5  # correlation peak on the shrunk page for a candidate
INK = 200  # grey level below which a pixel is drawn
PAD = 2  # pixels kept around the ink of a legend symbol
SAME = 0.5  # two matches overlapping this share of the smaller box are one symbol


class TemplateReader:
    def __init__(self, files: DrawingFiles, legend_of: LegendOf) -> None:
        self._files = files
        self._legend_of = legend_of

    def read(self, source: DrawingFile, sheet: Sheet) -> PictureReading:
        legend = self._legend_of(source, sheet)
        if legend is None:
            return nothing(READER, None, f"{READER}: {NO_LEGEND}")
        rgb = read_image(READER, self._files.read(source.path), source, sheet)
        if isinstance(rgb, PictureReading):
            return rgb.model_copy(update={"legend": legend})
        return read_symbols(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY), legend)


def read_symbols(gray: np.ndarray, legend: tuple[LegendEntry, ...]) -> PictureReading:
    """Every legend symbol's matches on the grey page, as sightings on page 1."""
    height, width = gray.shape
    found: list[tuple[float, int, int, int, int, str]] = []  # score, x, y, w, h, label
    read: list[str] = []
    notes: list[str] = []
    symbols: list[tuple[str, np.ndarray]] = []
    for entry in legend:
        if entry.line or entry.box is None:
            continue
        symbol = _symbol(gray, entry.box)
        if symbol is None:
            notes.append(f"{READER}: the legend's {entry.label!r} has no ink to match")
            continue
        read.append(entry.label)
        symbols.append((entry.label, symbol))
    shrink = min([1.0] + [COARSE_SIDE / max(symbol.shape) for _, symbol in symbols])
    coarse = cv2.resize(gray, None, fx=shrink, fy=shrink, interpolation=cv2.INTER_AREA)
    for label, symbol in symbols:
        found += [(*peak, label) for peak in _peaks(gray, coarse, shrink, symbol)]
    on_legend = [pixels(e.box, width, height, PAD) for e in legend if e.box is not None]
    kept: list[tuple[float, int, int, int, int, str]] = []
    for score, x, y, w, h, label in sorted(found, reverse=True):
        cx, cy = x + w / 2, y + h / 2
        if any(x0 <= cx <= x1 and y0 <= cy <= y1 for x0, y0, x1, y1 in on_legend):
            continue
        if all(
            _overlap((x, y, w, h), (kx, ky, kw, kh)) < SAME * min(w * h, kw * kh)
            for _, kx, ky, kw, kh, _ in kept
        ):
            kept.append((score, x, y, w, h, label))
    sightings = tuple(
        Sighting(
            label=label,
            spot=Spot(page=1, box=page_box(x, y, x + w, y + h, width, height), reader=READER),
            score=round(min(score, 1.0), 4),
        )
        for score, x, y, w, h, label in sorted(kept, key=lambda k: (k[2], k[1]))
    )
    return PictureReading(
        reader=READER, legend=legend, read=tuple(read), sightings=sightings, notes=tuple(notes)
    )


def _symbol(gray: np.ndarray, box: tuple[float, float, float, float]) -> np.ndarray | None:
    """The legend symbol in `box`, cropped to its ink; None when the box holds no ink."""
    x0, y0, x1, y1 = pixels(box, gray.shape[1], gray.shape[0])
    crop = gray[y0:y1, x0:x1]
    rows, cols = np.nonzero(crop < INK)
    if rows.size == 0:
        return None
    top, left = max(0, rows.min() - PAD), max(0, cols.min() - PAD)
    return crop[top : rows.max() + PAD + 1, left : cols.max() + PAD + 1]


def _peaks(
    gray: np.ndarray, coarse: np.ndarray, shrink: float, symbol: np.ndarray
) -> list[tuple[float, int, int, int, int]]:
    """(score, x, y, w, h) on the full page of each match of `symbol` above THRESHOLD, any
    quarter turn: candidates on the `coarse` page (`gray` shrunk by `shrink`), each matched
    again at full size in a window around it."""
    peaks: list[tuple[float, int, int, int, int]] = []
    seen: set[bytes] = set()
    for quarter in range(4):
        turned = np.ascontiguousarray(np.rot90(symbol, quarter))
        key = turned.tobytes() + str(turned.shape).encode()  # a side may be 256 px or more
        if key in seen:  # a symmetric symbol turned onto itself
            continue
        seen.add(key)
        h, w = turned.shape
        small = cv2.resize(
            turned,
            (max(3, round(w * shrink)), max(3, round(h * shrink))),
            interpolation=cv2.INTER_AREA,
        )
        sizes = [cv2.resize(turned, (round(w * size), round(h * size))) for size in SIZES]
        if small.shape[0] > coarse.shape[0] or small.shape[1] > coarse.shape[1] or small.std() == 0:
            continue
        score = cv2.matchTemplate(coarse, small, cv2.TM_CCOEFF_NORMED)
        local = cv2.dilate(score, np.ones((max(1, small.shape[0] // 2),) * 2, np.uint8))
        ys, xs = np.nonzero((score >= COARSE_THRESHOLD) & (score >= local))
        margin = int(np.ceil(2 / shrink)) + int(np.ceil(0.1 * max(h, w)))
        for y, x in zip(ys.tolist(), xs.tolist(), strict=True):
            best = _refine(
                gray, round(x / shrink) - margin, round(y / shrink) - margin, margin, sizes
            )
            if best is not None and best[0] >= THRESHOLD:
                peaks.append(best)
    return peaks


def _refine(
    gray: np.ndarray, left: int, top: int, margin: int, sizes: list[np.ndarray]
) -> tuple[float, int, int, int, int] | None:
    """The best full-size match of any of `sizes` with its top left corner within `margin`
    around (left + margin, top + margin)."""
    best: tuple[float, int, int, int, int] | None = None
    x0, y0 = max(0, left), max(0, top)
    for template in sizes:
        h, w = template.shape
        window = gray[y0 : top + h + 2 * margin + 1, x0 : left + w + 2 * margin + 1]
        if window.shape[0] < h or window.shape[1] < w or template.std() == 0:
            continue
        _, score, _, (px, py) = cv2.minMaxLoc(
            cv2.matchTemplate(window, template, cv2.TM_CCOEFF_NORMED)
        )
        if best is None or score > best[0]:
            best = (float(score), x0 + px, y0 + py, w, h)
    return best


def _overlap(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> int:
    """The area two (x, y, w, h) boxes share."""
    wide = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])
    high = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
    return max(0, wide) * max(0, high)

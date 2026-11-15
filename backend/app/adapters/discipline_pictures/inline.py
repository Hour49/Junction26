"""`inline`: a reader for symbols that do not stand alone: a valve on its pipe, or several valves
and a meter drawn on one spot of a riser. The template reader's correlation treats the pipe's or the
neighbour's ink in a symbol's white middle as a mismatch, and of two overlapping matches keeps
only the stronger, whatever their labels. Here a place matches a legend symbol when nearly all of
the symbol's ink is there (`COVER`, extra ink is allowed) and the plain correlation is still
fair (`FLOOR`). The best correlated match is kept first and claims its ink; a later one must
still have `OWN` of its ink unclaimed. So a valve and a meter drawn on one spot are both kept,
while a bar inside a solid square, or the same symbol a pixel aside, is not a second symbol.

The score of a sighting is its correlation peak (0..1), as the template reader's."""

import cv2
import numpy as np

from app.adapters.discipline_pictures import page_box, pixels
from app.adapters.discipline_pictures.template import INK, PAD
from app.core.ifc_facts import Spot
from app.core.picture_facts import LegendEntry, PictureReading, Sighting

READER = "inline"
COVER = 0.9  # share of the legend symbol's ink found at a place; tune on the bench's tune half
FLOOR = 0.4  # plain correlation a place must still reach; tune on the bench's tune half
OWN = 0.5  # share of its ink a match must not share with a better one; tune on the tune half
# where a page pixel counts as ink, between the legend symbol's ink and paper: runs drawn
# lighter than the symbols (coloured or grey pipes) then do not make up a symbol's ink
TONE = 0.3  # tune on the bench's tune half
SLACK = 3  # px: a symbol's ink may sit this far from the legend's (antialiasing, a scan's blur)

_Match = tuple[str, float, int, int, np.ndarray, np.ndarray]  # label, then as `_matches` gives


def read_inline(gray: np.ndarray, legend: tuple[LegendEntry, ...]) -> PictureReading:
    """Every legend symbol's matches on the grey page, as sightings on page 1."""
    height, width = gray.shape
    inks: dict[int, np.ndarray] = {}  # the page's ink at a tone cut, widened by SLACK
    on_legend = [pixels(e.box, width, height, PAD) for e in legend if e.box is not None]
    read: list[str] = []
    notes: list[str] = []
    found: list[_Match] = []
    for entry in legend:
        if entry.line or entry.box is None:
            continue
        symbol = _symbol(gray, entry.box)
        if symbol is None:
            notes.append(f"{READER}: the legend's {entry.label!r} has no ink to match")
            continue
        read.append(entry.label)
        dark, light = np.median(symbol[symbol < INK]), np.median(symbol[symbol >= INK])
        cut = int(dark + TONE * (light - dark))
        if cut not in inks:
            inks[cut] = cv2.dilate((gray < cut).astype(np.float32), np.ones((SLACK, SLACK)))
        found += [(entry.label, *m) for m in _matches(gray, inks[cut], symbol, cut)]
    claimed = np.zeros(gray.shape, np.float32)  # ink a kept match explains
    kept: list[_Match] = []
    for match in sorted(found, key=lambda m: -m[1]):  # the best correlation first
        _, _, x, y, ink, wide = match
        h, w = ink.shape
        if any(x0 <= x + w / 2 <= x1 and y0 <= y + h / 2 <= y1 for x0, y0, x1, y1 in on_legend):
            continue
        if (ink * (1 - claimed[y : y + h, x : x + w])).sum() >= OWN * ink.sum():
            kept.append(match)
            claimed[y : y + h, x : x + w] = np.maximum(claimed[y : y + h, x : x + w], wide)
    sightings = tuple(
        Sighting(
            label=label,
            spot=Spot(
                page=1,
                box=page_box(x, y, x + ink.shape[1], y + ink.shape[0], width, height),
                reader=READER,
            ),
            score=round(min(score, 1.0), 4),
        )
        for label, score, x, y, ink, _ in sorted(kept, key=lambda k: (k[3], k[2]))
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


def _matches(
    gray: np.ndarray, page_ink: np.ndarray, symbol: np.ndarray, cut: int
) -> list[tuple[float, int, int, np.ndarray, np.ndarray]]:
    """(correlation, x, y, ink, ink widened by SLACK) of each local best place for `symbol`, any
    quarter turn; `ink` is the turned symbol's pixels darker than `cut`, its shape the match's
    size."""
    found: list[tuple[float, int, int, np.ndarray, np.ndarray]] = []
    seen: set[bytes] = set()
    for quarter in range(4):
        turned = np.ascontiguousarray(np.rot90(symbol, quarter))
        key = turned.tobytes() + bytes(turned.shape)
        h, w = turned.shape
        if key in seen or h > gray.shape[0] or w > gray.shape[1] or turned.std() == 0:
            continue  # a symmetric symbol turned onto itself, or nothing to correlate
        seen.add(key)
        ink = (turned < cut).astype(np.float32)
        if not ink.any():
            continue
        wide = cv2.dilate(ink, np.ones((SLACK, SLACK), np.uint8))
        cover = cv2.matchTemplate(page_ink, ink, cv2.TM_CCORR) / ink.sum()
        fair = cv2.matchTemplate(gray, turned, cv2.TM_CCOEFF_NORMED)
        fair[cover < COVER] = -1  # the correlation picks the spot among covered places
        best = cv2.dilate(fair, np.ones((max(3, h // 2), max(3, w // 2)), np.uint8))
        ys, xs = np.nonzero((fair >= FLOOR) & (fair >= best))
        spots = zip(ys.tolist(), xs.tolist(), strict=True)
        found += [(float(fair[y, x]), x, y, ink, wide) for y, x in spots]
    return found

"""`walls`: the wall lines of a services picture, in page pixels, for `register` to lay the
picture over its floor plan when no room names are shared.

On a services sheet the walls are the grey or thin background lines under the coloured runs. The
coloured pixels (as `mask` tells a colour) are painted out first so a pipe never becomes a wall,
the page is cleaned as a scan (`cleanup`: salt out, light evened; not straightened: `register`
finds the turn), and the small ink pieces (letters, symbols) go, as do the frame and title
block with any piece that spans most of the page.
Long straight lines are found by probabilistic Hough, kept when solid along their length (a row
of dashes is not), and the parallel pieces one thick wall gives are fitted into one line.

Shortcut: straight walls only; an arc or a wall drawn dashed is not read.
"""

import math

import cv2
import numpy as np

from app.adapters.discipline_pictures.cleanup import clean_page
from app.adapters.discipline_pictures.mask import COLOURFUL
from app.core.services.register import Segment

INK = 235  # grey level below which a pixel is drawn: grey walls count (as cleanup's TURN_INK)
RUN_PAD = 2  # px around a coloured pixel also painted out: a scan blurs a run's edges grey
FRAME = 0.9  # an ink piece this wide or tall a share of the page is the frame (and title block)
LONG = 0.03  # a wall line is at least this share of the page's long side
GAP = 0.01  # share of the long side a wall line may be broken by (a run painted out over it)
SOLID = 0.85  # share of a line's length on ink: a row of dashes or a chance line has gaps
MERGE_DEG = 3.0  # two pieces this parallel ...
MERGE_PX = 8.0  # ... this close side by side (a thick wall's two edges) ...
JOIN = 0.01  # ... and this share of the long side apart end to end are one line


def walls(rgb: np.ndarray) -> tuple[Segment, ...]:
    """The wall lines of the picture `rgb` (H x W x 3), as segments in its pixels."""
    channels = rgb.astype(np.int16)
    colourful = (channels.max(axis=2) - channels.min(axis=2)) > COLOURFUL
    colourful = cv2.dilate(colourful.astype(np.uint8), np.ones((2 * RUN_PAD + 1,) * 2, np.uint8))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    gray[colourful > 0] = 255
    ink = (clean_page(gray, straighten=False).gray < INK).astype(np.uint8)
    side = max(ink.shape)
    long, gap = round(LONG * side), round(GAP * side)
    ink = _long_pieces(ink, long)
    found = cv2.HoughLinesP(
        ink * 255, 1, math.pi / 360, threshold=long // 2, minLineLength=long, maxLineGap=gap
    )
    if found is None:
        return ()
    pieces = [
        (float(x0), float(y0), float(x1), float(y1))
        for x0, y0, x1, y1 in found.reshape(-1, 4)
        if _solid(ink, (x0, y0, x1, y1))
    ]
    return tuple(
        Segment(a=(x0, y0), b=(x1, y1))
        for x0, y0, x1, y1 in _merged(pieces, JOIN * side)
        if math.hypot(x1 - x0, y1 - y0) >= long
    )


def _long_pieces(ink: np.ndarray, long: int) -> np.ndarray:
    """`ink` without its small pieces (letters, symbols) and those that span most of the page
    (its frame, with the title block)."""
    _, labels, stats, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    height, width = ink.shape
    w, h = stats[1:, cv2.CC_STAT_WIDTH], stats[1:, cv2.CC_STAT_HEIGHT]
    kept = (np.maximum(w, h) >= long) & (w < FRAME * width) & (h < FRAME * height)
    return np.isin(labels, np.flatnonzero(kept) + 1).astype(np.uint8)


def _solid(ink: np.ndarray, line: tuple[int, int, int, int]) -> bool:
    """Whether the line lies on ink (within a pixel) for at least `SOLID` of its length."""
    x0, y0, x1, y1 = line
    n = max(2, round(math.hypot(x1 - x0, y1 - y0)))
    xs = np.linspace(x0, x1, n).round().astype(int)
    ys = np.linspace(y0, y1, n).round().astype(int)
    near = cv2.dilate(ink, np.ones((3, 3), np.uint8))
    return float(near[ys, xs].mean()) >= SOLID


type Line = tuple[float, float, float, float]


def _merged(pieces: list[Line], join: float) -> list[Line]:
    """The pieces with each group of parallel, side-by-side, end-to-end ones made one line,
    fitted through all their ends (a thick wall's slanted pieces even out)."""
    groups: list[list[Line]] = []
    for piece in sorted(pieces, key=lambda p: -math.hypot(p[2] - p[0], p[3] - p[1])):
        for group in groups:
            if _one(_fit(group), piece, join):
                group.append(piece)
                break
        else:
            groups.append([piece])
    return [_fit(group) for group in groups]


def _fit(group: list[Line]) -> Line:
    """The line through the group's ends, from its first to its last along it."""
    ends = np.array([e for x0, y0, x1, y1 in group for e in ((x0, y0), (x1, y1))], np.float32)
    ux, uy, cx, cy = (float(v) for v in cv2.fitLine(ends, cv2.DIST_L2, 0, 0.01, 0.01).ravel())
    along = (ends[:, 0] - cx) * ux + (ends[:, 1] - cy) * uy
    lo, hi = float(along.min()), float(along.max())
    return (cx + ux * lo, cy + uy * lo, cx + ux * hi, cy + uy * hi)


def _one(line: Line, piece: Line, join: float) -> bool:
    """Whether `piece` is part of `line`: parallel, side by side and end to end."""
    x0, y0, x1, y1 = line
    length = max(math.hypot(x1 - x0, y1 - y0), 1e-9)
    ux, uy = (x1 - x0) / length, (y1 - y0) / length
    px, py = piece[2] - piece[0], piece[3] - piece[1]
    cos = abs(ux * px + uy * py) / max(math.hypot(px, py), 1e-9)
    if math.degrees(math.acos(min(1.0, cos))) > MERGE_DEG:
        return False
    ends = [(piece[0], piece[1]), (piece[2], piece[3])]
    if max(abs((x - x0) * -uy + (y - y0) * ux) for x, y in ends) > MERGE_PX:
        return False
    along = [(x - x0) * ux + (y - y0) * uy for x, y in ends]
    return min(along) <= length + join and max(along) >= -join

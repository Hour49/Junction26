"""`plan_views`: where on a whole sheet its plan view(s) lie, so `walls()` and `register` can run
on the plan alone. Whole sheets carry attic views, schedules, risers and title blocks that crowd
the plan's lines out of `register`'s longest-lines cap: real pairs placed only when cropped
(spec #457 c6887370808, Madalina's pic-research, USCG Bldg 140 / 550).

Method: at a quarter of the resolution, the page frame band is blanked and page-spanning ink
pieces dropped; long axis-parallel runs (an opening with a long thin line) keep walls and grid
lines and lose text, hatching and symbols; the runs, dilated a little, cluster into views; a view
scores its run pixels times how closed an outline its box edges hold. Too small or too large
clusters and a small one in the bottom-right corner (the title block) are dropped.

The finder stays dumb: the caller always tries the whole page too (`candidates`), registers each
pair and keeps the best Place, adding the box origin back to the shift.
"""

import cv2
import numpy as np

Box = tuple[int, int, int, int]  # x0, y0, x1, y1 in input pixels

SHRINK = 4  # work at 1/4 resolution
INK = 60  # paper minus grey above this is ink (1-bit and grey scans)
FRAME_BAND = 0.06  # of the long side, blanked on every edge: the page frame sits 4-5% in
SPANNING = 0.85  # an ink piece this wide or tall a share of the page is the frame or joined to it
RUN = 0.04  # a run at least this share of the long side survives (k)
RUN_MIN = 15  # px at work resolution, whatever the page size
CLOSE = 0.006  # fallback: gaps this share of the long side bridged along a line (broken walls)
CLUSTER = 0.015  # runs dilated by this share of the long side cluster into one view
TOO_BIG = (0.80, 0.70)  # a cluster wider AND taller than these shares is the frame or everything
TOO_SMALL = (0.12, 0.10)  # narrower OR shorter than these is a legend or a stamp
CORNER_AREA = 0.15  # a cluster centred in the bottom-right quarter under this page share: title
EDGE_BAND = 0.02  # of the box's long side: the band whose run pixels count as its outline
KEEP = 0.15  # views scoring this share of the best are returned ...
MOST = 3  # ... at most this many, best first
GROW = 0.02  # of the page's long side added around each box
FILLS = 0.60  # the best view spans this share of the page both ways: the plan fills the page
SPANNED = 0.5  # ... or this share of the long runs was in page-spanning pieces (its outer walls)


def plan_views(gray: np.ndarray, paper: int = 255) -> list[Box]:
    """The boxes of the sheet's plan views, best first, at most `MOST`; empty when none is
    found (the caller still has the whole page, `candidates`)."""
    return _find(gray, paper)[0]


def candidates(gray: np.ndarray, paper: int = 255) -> list[Box]:
    """Every crop the caller should register: the whole page first when the plan fills it (or
    no view is found), else after the views."""
    height, width = gray.shape[:2]
    page: Box = (0, 0, width, height)
    views, fills = _find(gray, paper)
    if not views:
        return [page]
    x0, y0, x1, y1 = views[0]
    if fills or ((x1 - x0) >= FILLS * width and (y1 - y0) >= FILLS * height):
        return [page, *views]
    return [*views, page]


def _find(gray: np.ndarray, paper: int) -> tuple[list[Box], bool]:
    """The views' boxes, and whether most long runs were in page-spanning pieces."""
    if gray.ndim != 2 or min(gray.shape) < SHRINK * 8:
        return [], False
    height, width = gray.shape
    small = cv2.resize(
        gray, (width // SHRINK, height // SHRINK), interpolation=cv2.INTER_AREA
    ).astype(np.int16)
    ink = ((paper - small) > INK).astype(np.uint8)
    h, w = ink.shape
    side = max(h, w)
    band = round(FRAME_BAND * side)
    ink[:band], ink[h - band :], ink[:, :band], ink[:, w - band :] = 0, 0, 0, 0
    every = int(_runs(ink, side).sum())
    ink = _without_spanning(ink)
    lines = _runs(ink, side)
    fills = int(lines.sum()) < SPANNED * every
    found = _views(lines, side)
    if not found:  # thin walls broken by doors and fixtures: bridge small gaps along lines
        found = _views(_runs(_bridged(ink, side), side), side)
    if not found:
        return [], fills
    best = found[0][0]
    grow = GROW * side
    boxes: list[Box] = []
    for score, (x0, y0, x1, y1) in found[:MOST]:
        if score < KEEP * best:
            break
        boxes.append(
            (
                max(0, round((x0 - grow) * width / w)),
                max(0, round((y0 - grow) * height / h)),
                min(width, round((x1 + grow) * width / w)),
                min(height, round((y1 + grow) * height / h)),
            )
        )
    return boxes, fills


def _without_spanning(ink: np.ndarray) -> np.ndarray:
    """`ink` without the 8-connected pieces nearly as wide or as tall as the page."""
    h, w = ink.shape
    n, labels, stats, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    spanning = (stats[:, cv2.CC_STAT_WIDTH] > SPANNING * w) | (
        stats[:, cv2.CC_STAT_HEIGHT] > SPANNING * h
    )
    spanning[0] = False
    if not spanning[1:n].any():
        return ink
    out = ink.copy()
    out[spanning[labels]] = 0
    return out


def _runs(ink: np.ndarray, side: int) -> np.ndarray:
    """The long horizontal and vertical runs of `ink`."""
    k = max(RUN_MIN, round(RUN * side))
    across = cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((1, k), np.uint8))
    down = cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((k, 1), np.uint8))
    return np.maximum(across, down)


def _bridged(ink: np.ndarray, side: int) -> np.ndarray:
    """`ink` with gaps up to `CLOSE` of the long side closed along rows and along columns."""
    g = max(3, round(CLOSE * side))
    across = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, np.ones((1, g), np.uint8))
    down = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, np.ones((g, 1), np.uint8))
    return np.maximum(across, down)


def _views(lines: np.ndarray, side: int) -> list[tuple[float, Box]]:
    """The clusters of `lines` that may be views, (score, box at work resolution), best first."""
    h, w = lines.shape
    d = max(1, round(CLUSTER * side))
    grown = cv2.dilate(lines, np.ones((d, d), np.uint8))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(grown, connectivity=8)
    found: list[tuple[float, Box]] = []
    for i in range(1, n):
        x, y, bw, bh = (int(v) for v in stats[i, :4])
        if bw > TOO_BIG[0] * w and bh > TOO_BIG[1] * h:
            continue
        if bw < TOO_SMALL[0] * w or bh < TOO_SMALL[1] * h:
            continue
        cx, cy = x + bw / 2, y + bh / 2
        if cx > w / 2 and cy > h / 2 and bw * bh < CORNER_AREA * w * h:
            continue
        own = (labels[y : y + bh, x : x + bw] == i) & (lines[y : y + bh, x : x + bw] > 0)
        found.append((float(own.sum()) * _outline(own), (x, y, x + bw, y + bh)))
    found.sort(key=lambda f: -f[0])
    return found


def _outline(own: np.ndarray) -> float:
    """How closed an outline the box's edges hold: the mean over its four sides of the share of
    the side's band (positions along it) with a run pixel in it (0..1)."""
    bh, bw = own.shape
    e = max(1, round(EDGE_BAND * max(bh, bw)))
    sides = (
        own[:e].any(axis=0),
        own[bh - e :].any(axis=0),
        own[:, :e].any(axis=1),
        own[:, bw - e :].any(axis=1),
    )
    return float(np.mean([s.mean() for s in sides]))

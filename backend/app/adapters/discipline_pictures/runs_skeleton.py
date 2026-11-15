"""`skeleton`: the local reader of a raster plan's runs without colour (a greyscale scan, a photo
copy). A run is told by its legend line's grey and dash pattern, and measured along the line's
skeleton (one pixel wide, so a line's thickness or blur does not count).

Steps: drop the scanner's salt; keep the strokes darker than the background's light grey; thin
them to their skeleton (Zhang-Suen); give each skeleton pixel the grey of its line (the darkest
pixel next to it); legend line samples are read the same way. Lines whose grey is close are one
grey: inside it, a dashed line takes the rows of its dashes (`chained`) and a solid line the rest.
Two legend lines drawn alike (one grey, one dash) cannot be told apart on the page: both are
refused, named in `notes`. A black line is not read (shortcut, as `mask`: text and symbols share
its colour).

The length is the drawn length on this sheet: a riser or drop does not show on a plan.
"""

from itertools import pairwise

import cv2
import numpy as np

from app.adapters.discipline_pictures import (
    Dashes,
    Piece,
    chained,
    dash_pattern,
    is_dash,
    page_box,
    pixels,
)
from app.adapters.discipline_pictures.mask import size_of
from app.core.ifc_facts import Spot
from app.core.picture_facts import LegendEntry, PictureReading, Run

READER = "skeleton"
INK = 200  # darker than this is drawn; the background's walls are light grey (217 on the bench)
BLACK = 70  # a line this dark is text, a symbol or a black line, not a run's grey
SALT = 80  # a lone pixel darker than this, with no dark neighbour, is scanner salt
ALIKE = 6  # two legend lines whose greys differ by this or less are one grey
NEAR = 15  # a skeleton pixel is drawn in a grey when it is this close to it, and closest
MIN_RUN = 3  # px: a shorter solid piece is a speck
PAD = 2  # pixels around a legend box


def read_runs(
    image: np.ndarray, legend: tuple[LegendEntry, ...], m_per_px: float
) -> PictureReading:
    """The runs of every legend line on `image` (grey, or RGB read as its grey)."""
    grey = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    grey = _desalted(np.ascontiguousarray(grey, dtype=np.uint8))
    height, width = grey.shape
    core = cv2.erode(grey, np.ones((3, 3), np.uint8))  # a stroke pixel's line grey
    ink = (grey < INK) & (grey >= BLACK)
    notes: list[str] = []
    styles: list[tuple[LegendEntry, float, Dashes | None]] = []
    for entry in legend:
        if entry.box is None:
            continue
        x0, y0, x1, y1 = pixels(entry.box, width, height, PAD)
        if entry.line:
            style = _sample(ink[y0:y1, x0:x1], core[y0:y1, x0:x1])
            if style is None:
                notes.append(f"{READER}: the legend's {entry.label!r} has no grey line")
            else:
                styles.append((entry, *style))
        ink[y0:y1, x0:x1] = False
    ys, xs = np.nonzero(thin(ink))
    groups = _greys(styles)
    levels = np.array([np.mean([g for _, g, _ in group]) for group in groups], np.float32)
    off = np.abs(core[ys, xs].astype(np.float32)[:, None] - levels[None, :])  # pixel x grey
    closest = off.argmin(axis=1) if len(groups) else np.zeros(len(ys), int)
    near = off.min(axis=1) <= NEAR if len(groups) else np.zeros(len(ys), bool)
    runs: list[Run] = []
    read: list[str] = []
    for k, group in enumerate(groups):
        mine = near & (closest == k)  # a skeleton pixel goes to its closest grey
        pieces = _pieces_at(ys[mine], xs[mine])
        for entry, dashes, alike in _told_apart(group):
            if alike:
                names = ", ".join(repr(e.label) for e in alike)
                notes.append(f"{READER}: {entry.label!r} is drawn like {names}: not read")
                continue
            read.append(entry.label)
            if dashes is not None:
                found = chained(pieces, dashes)
            else:
                dashed = [d for _, _, d in group if d is not None]
                found = [
                    (p.length, p.box)
                    for p in pieces
                    if p.length >= MIN_RUN and not any(is_dash(p, d) for d in dashed)
                ]
            runs += [
                Run(
                    label=entry.label,
                    size=size_of(entry.label),
                    length_m=length * m_per_px,
                    spots=(Spot(page=1, box=page_box(*box, width, height), reader=READER),),
                )
                for length, box in found
            ]
    order = {e.label: k for k, e in enumerate(legend)}
    return PictureReading(
        reader=READER,
        legend=legend,
        read=tuple(sorted(read, key=order.__getitem__)),
        runs=tuple(runs),
        notes=tuple(notes),
    )


def thin(mask: np.ndarray) -> np.ndarray:
    """The one-pixel skeleton of `mask` (Zhang-Suen thinning), 0/1."""
    m = np.pad(mask.astype(bool), 1)
    inner = m[1:-1, 1:-1]
    while True:
        changed = False
        for first in (True, False):
            p2, p3, p4, p5 = m[:-2, 1:-1], m[:-2, 2:], m[1:-1, 2:], m[2:, 2:]
            p6, p7, p8, p9 = m[2:, 1:-1], m[2:, :-2], m[1:-1, :-2], m[:-2, :-2]
            ring = (p2, p3, p4, p5, p6, p7, p8, p9, p2)
            b = sum(p.astype(np.uint8) for p in ring[:8])
            a = sum((~x & y).astype(np.uint8) for x, y in pairwise(ring))
            keep = (p2 & p4 & p6) | (p4 & p6 & p8) if first else (p2 & p4 & p8) | (p2 & p6 & p8)
            gone = inner & (b >= 2) & (b <= 6) & (a == 1) & ~keep
            if gone.any():
                inner &= ~gone
                changed = True
        if not changed:
            return inner.astype(np.uint8)


def skeleton_length(skeleton: np.ndarray) -> float:
    """Length in px of a one-pixel skeleton: its links, a diagonal one √2."""
    return float(_links(skeleton.astype(bool)).sum())


def _links(s: np.ndarray) -> np.ndarray:
    """Per pixel, the length of its links to the right and down (a diagonal only where no
    straight pair of links already joins the two pixels)."""
    p = np.pad(s, 1)
    c, r, d, dr, dl, lft = (
        p[1:-1, 1:-1],
        p[1:-1, 2:],
        p[2:, 1:-1],
        p[2:, 2:],
        p[2:, :-2],
        p[1:-1, :-2],
    )
    return (
        (c & r).astype(np.float32)
        + (c & d)
        + np.sqrt(2) * (c & dr & ~r & ~d)
        + np.sqrt(2) * (c & dl & ~lft & ~d)
    )


def _desalted(grey: np.ndarray) -> np.ndarray:
    dark = (grey < SALT).astype(np.uint8)
    alone = (dark == 1) & (cv2.boxFilter(dark, -1, (3, 3), normalize=False) == 1)
    return np.where(alone, cv2.medianBlur(grey, 3), grey)


def _sample(ink: np.ndarray, core: np.ndarray) -> tuple[float, Dashes | None] | None:
    """A legend line sample's grey and dash pattern; None when it has no grey line."""
    skeleton = thin(ink)
    if not skeleton.any():
        return None
    return float(np.median(core[skeleton == 1])), dash_pattern(_pieces(skeleton == 1))


def _greys(
    styles: list[tuple[LegendEntry, float, Dashes | None]],
) -> list[list[tuple[LegendEntry, float, Dashes | None]]]:
    """The legend lines grouped by grey: neighbours ALIKE or closer are one grey."""
    groups: list[list[tuple[LegendEntry, float, Dashes | None]]] = []
    for style in sorted(styles, key=lambda s: s[1]):
        if groups and style[1] - groups[-1][-1][1] <= ALIKE:
            groups[-1].append(style)
        else:
            groups.append([style])
    return groups


def _told_apart(
    group: list[tuple[LegendEntry, float, Dashes | None]],
) -> list[tuple[LegendEntry, Dashes | None, list[LegendEntry]]]:
    """Each line of one grey with its pattern and the other lines drawn alike (same dashes)."""

    def alike(a: Dashes | None, b: Dashes | None) -> bool:
        if a is None or b is None:
            return a is b
        return (
            is_dash(Piece(a.dash, (0, 0), (0, 0, 0, 0)), b)
            and abs(a.gap - b.gap) <= 0.3 * b.gap + 1
        )

    return [
        (entry, dashes, [e for e, _, d in group if e is not entry and alike(dashes, d)])
        for entry, _, dashes in group
    ]


def _pieces_at(ys: np.ndarray, xs: np.ndarray) -> list[Piece]:
    """`_pieces` of the skeleton pixels at (ys, xs), in page pixels (worked on their crop)."""
    if len(ys) == 0:
        return []
    y0, x0 = int(ys.min()), int(xs.min())
    crop = np.zeros((int(ys.max()) - y0 + 1, int(xs.max()) - x0 + 1), bool)
    crop[ys - y0, xs - x0] = True
    return [
        Piece(p.length, (p.centre[0] + x0, p.centre[1] + y0), _moved(p.box, x0, y0))
        for p in _pieces(crop)
    ]


def _moved(
    box: tuple[float, float, float, float], dx: int, dy: int
) -> tuple[float, float, float, float]:
    return (box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy)


def _pieces(mask: np.ndarray) -> list[Piece]:
    """Each 8-connected piece of a skeleton mask: its length along the skeleton (end pixels
    included), centre and pixel box."""
    count, labels, stats, centres = cv2.connectedComponentsWithStats(
        mask.astype(np.uint8), connectivity=8
    )
    lengths = np.bincount(
        labels.ravel(), weights=_links(mask.astype(bool)).ravel(), minlength=count
    )
    return [
        Piece(
            float(lengths[k]) + 1,
            (float(centres[k][0]), float(centres[k][1])),
            (
                int(stats[k][0]),
                int(stats[k][1]),
                int(stats[k][0] + stats[k][2]),
                int(stats[k][1] + stats[k][3]),
            ),
        )
        for k in range(1, count)
    ]

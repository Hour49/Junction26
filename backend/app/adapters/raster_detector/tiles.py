"""RASTER_TILES=auto: a big sheet is read by the detector tile by tile (local-dec AV, 2026-11-14).

The detector letterboxes a page to its canvas (1024 px), so on a 10-14k px sheet a door is 2-6
canvas px, where training saw about 45 (CubiCasa doors, median). A page whose long side is over
`ABOVE` is cut into square tiles of `SIZE` page px overlapping by `OVERLAP`; each tile is read as
a page is. A detection touching an inner tile edge is dropped (its object is whole in the
neighbour: the overlap is larger than a door), and the rest are merged by non-maximum suppression
at `IOU` inside a class (or a group of classes that compete, the door kinds) on page coordinates.
The knobs were fixed before any tiled run (.agents/exp/big-tiles.md pre-registration).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

type Box = tuple[float, float, float, float]

ABOVE = 4000  # page px, long side: smaller pages are read whole, as before
SIZE = 2048  # tile side, page px: a door on a 1:200 sheet is then about 40 canvas px
OVERLAP = 256  # page px shared by neighbouring tiles; larger than a door
EDGE = 4  # page px: a box this close to an inner tile edge is the neighbour's
IOU = 0.5


def tiled(width: int, height: int) -> bool:
    """Whether a page of this size is read in tiles."""
    return max(width, height) > ABOVE


def starts(length: int, size: int = SIZE, overlap: int = OVERLAP) -> list[int]:
    """Tile origins along one side: `size` apart less `overlap`, the last one shifted back to
    end at the page edge; one tile when the side is not longer than `size`."""
    if length <= size:
        return [0]
    step = size - overlap
    origins = list(range(0, length - size, step))
    return [*origins, length - size]


def grid(width: int, height: int) -> list[tuple[int, int, int, int]]:
    """The tiles of a page as (x0, y0, x1, y1) page px, row by row."""
    return [
        (x, y, min(width, x + SIZE), min(height, y + SIZE))
        for y in starts(height)
        for x in starts(width)
    ]


def inner_edge(box: Box, tile: tuple[int, int, int, int], width: int, height: int) -> bool:
    """True when `box` (page px) touches an edge of `tile` that is not the page's own edge."""
    x0, y0, x1, y1 = tile
    return (
        (x0 > 0 and box[0] <= x0 + EDGE)
        or (y0 > 0 and box[1] <= y0 + EDGE)
        or (x1 < width and box[2] >= x1 - EDGE)
        or (y1 < height and box[3] >= y1 - EDGE)
    )


@dataclass(frozen=True)
class Found:
    """One detection of one tile, on page px."""

    name: str  # training class
    score: float
    box: Box
    seen: tuple[int, ...] = ()  # the views that saw it (N-view reads)


def _iou(a: Box, b: Box) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    if w <= 0 or h <= 0:
        return 0.0
    inter = w * h
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def merge(found: Sequence[Found], groups: Sequence[Sequence[str]] = ()) -> list[Found]:
    """Non-maximum suppression across tiles: from the highest score down, a detection is kept
    unless one kept of its class (or class group) overlaps it at IoU >= `IOU`."""
    family: Mapping[str, int] = {name: i for i, names in enumerate(groups) for name in names}
    kept: list[Found] = []
    for det in sorted(found, key=lambda d: -d.score):
        key = family.get(det.name, det.name)
        if all(family.get(k.name, k.name) != key or _iou(det.box, k.box) < IOU for k in kept):
            kept.append(det)
    return kept

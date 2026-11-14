"""Reading a square canvas in several views (its rotations and mirrors) and fusing the views'
detections into one per object. No model, no files. Used by `detector-v<N>:<arm>` and by the
region arm (app/adapters/raster_region/).

They mirror the prototype that was scored on val (core's predict.py `view_of`/`box_back` and
counts.py `fuse_views`), including where numbers are rounded, so the runtime gives the arm's counts:

- `view_of` / `box_back`: the eight rotations and mirrors of a square canvas, and a box found on
  one of them moved back to the canvas as is;
- `as_found`: a raw model row as predict.py saved it;
- `read_views`: every detection of a canvas's first N views, in the canvas as is;
- `fuse_views`: one detection per object from the N views (score = sum over views / views), with
  the views that saw it.
"""

from collections.abc import Callable
from dataclasses import dataclass

from PIL import Image

type Box = tuple[float, float, float, float]

# (transpose, mirror, flip); view 0 is the canvas as is (core's predict.VIEWS)
VIEWS: tuple[tuple[int, int, int], ...] = tuple(
    (t, h, v) for t in (0, 1) for h in (0, 1) for v in (0, 1)
)
MIN_SCORE = 0.02  # rows under this score were never saved by the prototype (predict.py)


@dataclass(frozen=True)
class Det:
    """One detection: training class, score, box in canvas pixels, the view it was seen in (a
    fused detection: the views that saw it, in `seen`)."""

    name: str
    score: float
    box: Box
    view: int = 0
    seen: tuple[int, ...] = ()


def view_of(canvas: Image.Image, view: tuple[int, int, int]) -> Image.Image:
    """One of the eight symmetries of a square canvas: transpose, then mirror, then flip."""
    turn, mirror, flip = view
    if turn:
        canvas = canvas.transpose(Image.Transpose.TRANSPOSE)
    if mirror:
        canvas = canvas.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if flip:
        canvas = canvas.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    return canvas


def box_back(box: Box, view: tuple[int, int, int], side: int) -> Box:
    """A box found on a view, in the frame of the canvas as is (the inverse of view_of)."""
    x0, y0, x1, y1 = box
    turn, mirror, flip = view
    if flip:
        y0, y1 = side - y1, side - y0
    if mirror:
        x0, x1 = side - x1, side - x0
    if turn:
        x0, y0, x1, y1 = y0, x0, y1, x1
    return (round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2))


def as_found(name: str, score: float, box: Box, side: int) -> Det:
    """A raw model row as the prototype saved it: score to 4 places, box clamped to the canvas
    and rounded to 2 (core's predict.py OnnxYolo)."""
    clamped = tuple(round(min(float(side), max(0.0, v)), 2) for v in box)
    return Det(name, round(score, 4), clamped)  # type: ignore[arg-type]


def read_views(
    canvas: Image.Image, views: int, side: int, detect: Callable[[Image.Image], list[Det]]
) -> list[Det]:
    """Every detection of the canvas's first `views` views (`detect` reads one square canvas),
    in the canvas as is, view by view; one view keeps view 0 on every detection."""
    found = []
    for index, view in enumerate(VIEWS[:views]):
        for det in detect(view_of(canvas, view)):
            back = box_back(det.box, view, side)
            found.append(Det(det.name, det.score, back, index if views > 1 else 0))
    return found


def _ios(a: Box, b: Box) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    if w <= 0 or h <= 0:
        return 0.0
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    return w * h / max(1e-9, min(area_a, area_b))


def fuse_views(found: list[Det], views: int, limit: float = 0.5) -> list[Det]:
    """One detection per object: boxes of one class from different views that overlap (over the
    smaller box >= limit, against the cluster's first box) are one object, scored by the sum of
    its views' scores over `views`, boxed by the mean box, `seen` its views. One view: unchanged."""
    if views == 1:
        return list(found)
    clusters: list[tuple[Det, set[int], list[float], list[Box]]] = []
    for det in sorted(found, key=lambda d: -d.score):
        for first, seen, total, boxes in clusters:
            if first.name != det.name or det.view in seen:
                continue
            if _ios(det.box, first.box) >= limit:
                seen.add(det.view)
                total[0] += det.score
                boxes.append(det.box)
                break
        else:
            clusters.append((det, {det.view}, [det.score], [det.box]))
    return [
        Det(
            first.name,
            round(total[0] / views, 4),
            tuple(round(sum(b[i] for b in boxes) / len(boxes), 2) for i in range(4)),  # type: ignore[arg-type]
            seen=tuple(sorted(seen)),
        )
        for first, seen, total, boxes in clusters
    ]

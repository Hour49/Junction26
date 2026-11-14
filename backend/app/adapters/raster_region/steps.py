"""The pure steps of the region arm, on detections in canvas pixels. No model, no files.

They mirror the prototype that was scored on val (prototypes/region/regionlib.py, perplan.py,
filter_region.py, and core's predict.py `view_of`/`box_back` and counts.py `fuse_views`),
including where numbers are rounded, so the runtime gives the arm's counts:

- `view_of` / `box_back`: the eight rotations and mirrors of a square canvas, and a box found on
  one of them moved back to the canvas as is;
- `plan_windows` / `merge_windows`: one window per plan on a sheet, and the windows' element
  boxes moved back to the page's canvas, each window keeping the boxes centred in its plan;
- `keep_in_region`: the element boxes centred on the annotated-flat mask;
- `fuse_views`: one detection per object from the eight views (score = sum over views / views).
"""

from dataclasses import dataclass, replace
from math import ceil, floor

import numpy as np
from PIL import Image

type Box = tuple[float, float, float, float]

# (transpose, mirror, flip); view 0 is the canvas as is (core's predict.VIEWS)
VIEWS: tuple[tuple[int, int, int], ...] = tuple(
    (t, h, v) for t in (0, 1) for h in (0, 1) for v in (0, 1)
)


@dataclass(frozen=True)
class Det:
    """One detection: training class, score, box in canvas pixels, the view it was seen in."""

    name: str
    score: float
    box: Box
    view: int = 0


@dataclass(frozen=True)
class Frame:
    """A page (or a window of it) on a square canvas: scaled to new size, pasted at (dx, dy)."""

    side: int
    width: int
    height: int
    new_width: int
    new_height: int
    dx: int
    dy: int

    @classmethod
    def fit(cls, width: int, height: int, side: int) -> "Frame":
        scale = side / max(width, height)
        new_width = max(1, min(side, round(width * scale)))
        new_height = max(1, min(side, round(height * scale)))
        return cls(
            side, width, height, new_width, new_height, (side - new_width) // 2,
            (side - new_height) // 2,
        )  # fmt: skip

    def to_page_px(self, x: float, y: float) -> tuple[float, float]:
        return (
            (x - self.dx) * self.width / self.new_width,
            (y - self.dy) * self.height / self.new_height,
        )

    def to_canvas(self, x: float, y: float) -> tuple[float, float]:
        return (
            x * self.new_width / self.width + self.dx,
            y * self.new_height / self.height + self.dy,
        )


def centre(box: Box) -> tuple[float, float]:
    return (box[0] + box[2]) / 2, (box[1] + box[3]) / 2


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


# ---------------------------------------------------------------------------- plan windows


@dataclass(frozen=True)
class Window:
    """One plan's window in page pixels: `crop` is what the detector sees, `core` the plan box
    whose detections this window owns."""

    crop: tuple[int, int, int, int]
    core: Box


def plan_windows(
    found: list[Det], frame: Frame, plan_class: str, plan_score: float, margin: float, own: float
) -> list[Window]:
    """One window per plan box (score >= plan_score) of the view-0 detections, in page pixels,
    grown by `margin` (crop) and `own` (the box that owns detections) of the plan's long side."""
    windows = []
    for det in found:
        if det.name != plan_class or det.score < plan_score:
            continue
        x0, y0 = frame.to_page_px(det.box[0], det.box[1])
        x1, y1 = frame.to_page_px(det.box[2], det.box[3])
        x0, y0 = max(0.0, x0), max(0.0, y0)
        x1, y1 = min(float(frame.width), x1), min(float(frame.height), y1)
        if x1 - x0 < 2 or y1 - y0 < 2:
            continue
        long = max(x1 - x0, y1 - y0)
        pad, keep = margin * long, own * long
        crop = (
            max(0, floor(x0 - pad)), max(0, floor(y0 - pad)),
            min(frame.width, ceil(x1 + pad)), min(frame.height, ceil(y1 + pad)),
        )  # fmt: skip
        windows.append(Window(crop, (x0 - keep, y0 - keep, x1 + keep, y1 + keep)))
    return windows


def merge_windows(
    whole: list[Det],
    page: Frame,
    per_window: list[tuple[Window, Frame, list[Det]]],
    plan_class: str,
) -> list[Det]:
    """The whole-page plans, then each window's element boxes centred in its own plan box,
    moved to the page's canvas (the whole-page element boxes are replaced)."""
    merged = [det for det in whole if det.name == plan_class]
    for window, frame, found in per_window:
        ox, oy = window.crop[0], window.crop[1]
        for det in found:
            if det.name == plan_class:
                continue
            x0, y0 = frame.to_page_px(det.box[0], det.box[1])
            x1, y1 = frame.to_page_px(det.box[2], det.box[3])
            a = page.to_canvas(x0 + ox, y0 + oy)
            b = page.to_canvas(x1 + ox, y1 + oy)
            box = (round(a[0], 3), round(a[1], 3), round(b[0], 3), round(b[1], 3))
            x, y = page.to_page_px(*centre(box))
            c = window.core
            if c[0] <= x <= c[2] and c[1] <= y <= c[3]:
                merged.append(replace(det, box=box))
    return merged


# --------------------------------------------------------------------------- target region


def keep_in_region(
    found: list[Det], page: Frame, mask: np.ndarray, mask_frame: Frame, plan_class: str,
    min_share: float,
) -> list[Det]:  # fmt: skip
    """The element boxes whose centre is on the mask (its own canvas); plans always kept. A mask
    covering no more than `min_share` of the page keeps everything (a failed prediction)."""
    on_page = mask[
        mask_frame.dy : mask_frame.dy + mask_frame.new_height,
        mask_frame.dx : mask_frame.dx + mask_frame.new_width,
    ]
    if on_page.size == 0 or not on_page.any() or on_page.mean() <= min_share:
        return list(found)
    rows, cols = mask.shape
    kept = []
    for det in found:
        if det.name == plan_class:
            kept.append(det)
            continue
        x, y = mask_frame.to_canvas(*page.to_page_px(*centre(det.box)))
        col, row = floor(x), floor(y)
        if 0 <= row < rows and 0 <= col < cols and mask[row, col]:
            kept.append(det)
    return kept


# ---------------------------------------------------------------------------------- fusion


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
    its views' scores over `views`, boxed by the mean box. One view: unchanged."""
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
        )
        for first, _, total, boxes in clusters
    ]

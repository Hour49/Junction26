"""The pure steps of the region arm, on detections in canvas pixels. No model, no files. Reading
the views and fusing them is the detector's (app/adapters/raster_detector/views.py).

They mirror the prototype that was scored on val (prototypes/region/regionlib.py, perplan.py,
filter_region.py), including where numbers are rounded, so the runtime gives the arm's counts:

- `plan_windows` / `merge_windows`: one window per plan on a sheet, and the windows' element
  boxes moved back to the page's canvas, each window keeping the boxes centred in its plan;
- `keep_in_region`: the element boxes centred on the annotated-flat mask.
"""

from dataclasses import dataclass, replace
from math import ceil, floor

import numpy as np

from app.adapters.raster_detector.views import Box, Det


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

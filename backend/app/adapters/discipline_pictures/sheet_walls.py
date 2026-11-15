"""`reader`: a services picture's wall lines per part, for `pairing.by_walls` (the follower's
wall register, DISCIPLINE_PICTURES on). The picture is shrunk to `LONG` pixels (`walls` takes
minutes on a whole 7,500 px scan), cut into the whole page and its plan views (`plan_view`), and
each part's walls read (the finder sees the page with its coloured runs painted out); lines
and boxes are given back in the picture's own pixels.

Shortcut: a picture file only (PNG, JPEG, ...); a scanned PDF page is not rendered here.
"""

from collections.abc import Callable

import cv2
import numpy as np

from app.adapters.discipline_pictures.mask import COLOURFUL
from app.adapters.discipline_pictures.plan_view import candidates
from app.adapters.discipline_pictures.walls import walls
from app.core.services.model import Point2
from app.core.services.pairing import Crop, SheetWalls
from app.core.services.picture_follow import Sheet
from app.core.services.register import Segment

LONG = 2500  # px: the long side the picture is read at (Tudor's measure: walls() ~1-3 s there)


def crops(image: np.ndarray) -> tuple[list[Crop], Point2]:
    """The picture's parts (whole page and plan views) with their wall lines, in the
    picture's pixels (each part's lines from its own corner), and the picture's size."""
    height, width = image.shape[:2]
    f = min(1.0, LONG / max(height, width))
    small = image if f == 1.0 else cv2.resize(image, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
    if small.ndim == 2:
        gray = small
    else:  # coloured runs painted out first (as `walls`): a pipe across the page is no frame
        rgb = small[..., :3]
        channels = rgb.astype(np.int16)
        gray = cv2.cvtColor(np.ascontiguousarray(rgb), cv2.COLOR_RGB2GRAY)
        gray[(channels.max(axis=2) - channels.min(axis=2)) > COLOURFUL] = 255
    out: list[Crop] = []
    for x0, y0, x1, y1 in candidates(gray):
        lines = walls(small[y0:y1, x0:x1])
        box = (x0 / f, y0 / f, x1 / f, y1 / f)
        if (x0, y0, x1, y1) == (0, 0, small.shape[1], small.shape[0]):
            box = (0.0, 0.0, float(width), float(height))  # the whole page, exactly
        out.append(
            (
                box,
                tuple(
                    Segment(a=(s.a[0] / f, s.a[1] / f), b=(s.b[0] / f, s.b[1] / f)) for s in lines
                ),
            )
        )
    return out, (float(width), float(height))


def decoded(data: bytes) -> np.ndarray | None:
    """A picture file's pixels (RGB); None when the bytes are no picture (a PDF, ...)."""
    image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR_RGB)
    return image if image is not None and image.size else None


def reader(image_of: Callable[[Sheet], np.ndarray | None]) -> SheetWalls:
    """The sheet-walls reader over `image_of` (the sheet's picture, RGB or grey; None: none)."""

    def read(sheet: Sheet) -> tuple[list[Crop], Point2] | str:
        image = image_of(sheet)
        if image is None or image.size == 0:
            return "the services sheet is no picture file: its walls are not read"
        parts, size = crops(image)
        if not any(lines for _, lines in parts):
            return "no wall lines were read on the services sheet"
        return parts, size

    return read

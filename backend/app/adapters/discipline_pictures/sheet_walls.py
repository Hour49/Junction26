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
CODE = "1"  # bump when walls(), the finder or this reading change: the kept parts are read again
KEPT = 256  # sheets' parts kept per process before the memo starts again (a few KB each)

# A sheet's file: its sha256 and how to load its bytes; None: the sheet has no file
FileOf = Callable[[Sheet], tuple[str, Callable[[], bytes]] | None]
Read = tuple[list[Crop], Point2] | str
_KEPT: dict[tuple[str, str, int], Read] = {}  # (CODE, sha256, page) -> what was read


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


def reader(file_of: FileOf, kept: dict[tuple[str, str, int], Read] | None = None) -> SheetWalls:
    """The sheet-walls reader over `file_of`. Every proposal pairs every picture sheet, so what
    a file's page gives (0.2-0.5 s a picture on the dev1 DigitalHub renders) is kept in `kept`
    (default: this process's memo) by its sha256, page and `CODE`."""
    memo = _KEPT if kept is None else kept

    def read(sheet: Sheet) -> Read:
        found = file_of(sheet)
        if found is None:
            return NO_PICTURE
        sha256, load = found
        key = (CODE, sha256, sheet.page)
        if key not in memo:
            if len(memo) >= KEPT:
                memo.clear()
            memo[key] = _read(decoded(load()))
        return memo[key]

    return read


NO_PICTURE = "the services sheet is no picture file: its walls are not read"


def _read(image: np.ndarray | None) -> Read:
    if image is None:
        return NO_PICTURE
    parts, size = crops(image)
    if not any(lines for _, lines in parts):
        return "no wall lines were read on the services sheet"
    return parts, size

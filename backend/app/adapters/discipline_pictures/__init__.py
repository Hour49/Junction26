"""The readers of a services or structural plan (docs/specs/backend/discipline-pictures.md), each
a `PictureReader`. The local ones, no model call: `template` (legend symbols matched over a
raster), `paths` (symbols and runs of a vector PDF), `mask` (coloured runs of a raster).

They take the sheet's legend from `LegendOf` (the VLM legend reader later; the bench's truth or a
test until then) and raise nothing on a page they cannot read: `read=()` and the reason in
`notes`.

A dashed line is read the way CAD exports and pictures draw it: as its dashes. The legend sample's
pieces give the pattern (`dash_pattern`); on the plan, the pieces of that length (`is_dash`) in a
row are one run (`chained`), measured from its first dash to its last.
"""

import math
import statistics
from collections.abc import Callable, Sequence
from io import BytesIO
from itertools import pairwise
from typing import NamedTuple

import numpy as np
import pypdfium2
import shapely
from PIL import Image

from app.adapters.page_render import render_upload
from app.adapters.raster_detector.post import open_rgb
from app.core.drawing.model import Box, Scale
from app.core.errors import InvalidInputError
from app.core.picture_facts import LegendEntry, PictureReading
from app.core.pipeline.model import DrawingFile, Sheet

LegendOf = Callable[[DrawingFile, Sheet], tuple[LegendEntry, ...] | None]
ScaleOf = Callable[[DrawingFile, Sheet], Scale]  # metres per unit of `sheet.pages[0]`
RENDER_DPI = 150  # a PDF page is read at this resolution
NO_LEGEND = "no legend on the sheet"


def page_image(data: bytes, source: DrawingFile, sheet: Sheet) -> np.ndarray:
    """Page 1 of `source` as an RGB array, in the frame of `sheet` (a PDF rendered)."""
    if source.kind == "pdf":
        data = render_upload(data, "pdf_scan", round(sheet.pages[0].width * RENDER_DPI / 72))
    with Image.open(BytesIO(data)) as image:
        return np.asarray(open_rgb(image))


def read_image(
    reader: str, data: bytes, source: DrawingFile, sheet: Sheet
) -> np.ndarray | PictureReading:
    """The page's pixels, or a reading of nothing that says why there are none."""
    try:
        return page_image(data, source, sheet)
    except (
        OSError,
        Image.DecompressionBombError,
        pypdfium2.PdfiumError,
        InvalidInputError,
    ) as error:
        return nothing(reader, None, f"{reader}: the page cannot be decoded ({error})")


def nothing(reader: str, legend: tuple[LegendEntry, ...] | None, why: str) -> PictureReading:
    return PictureReading(reader=reader, legend=legend, read=(), notes=(why,))


def pixels(box: Box, width: int, height: int, pad: int = 0) -> tuple[int, int, int, int]:
    """A page-fraction box as pixel bounds (x0, y0, x1, y1), padded, clamped to the image."""
    x0, y0, x1, y1 = box
    return (
        max(0, int(x0 * width) - pad),
        max(0, int(y0 * height) - pad),
        min(width, int(np.ceil(x1 * width)) + pad),
        min(height, int(np.ceil(y1 * height)) + pad),
    )


def page_box(x0: float, y0: float, x1: float, y1: float, width: int, height: int) -> Box:
    return (
        round(max(0.0, x0 / width), 5),
        round(max(0.0, y0 / height), 5),
        round(min(1.0, x1 / width), 5),
        round(min(1.0, y1 / height), 5),
    )


class Piece(NamedTuple):
    """One drawn piece of a line style: a whole run, or one dash. Page units (pt or px)."""

    length: float
    centre: tuple[float, float]
    box: tuple[float, float, float, float]


class Dashes(NamedTuple):
    dash: float  # length of one dash, page units
    gap: float


DASH_SLACK = 0.3  # share of the dash length a dash may differ by, plus one page unit
ROW = 1.5  # two dashes are in a row when their centres are this many dash + gap apart, or less


def dash_pattern(sample: Sequence[Piece]) -> Dashes | None:
    """The pattern of a legend line sample's pieces (a straight line); None for a solid line."""
    if len(sample) < 2:
        return None
    along = sorted(sample, key=lambda p: p.centre)
    pitch = statistics.median(math.dist(a.centre, b.centre) for a, b in pairwise(along))
    dash = statistics.median(p.length for p in sample)
    return Dashes(dash=dash, gap=max(0.0, pitch - dash))


def is_dash(piece: Piece, dashes: Dashes) -> bool:
    return abs(piece.length - dashes.dash) <= DASH_SLACK * dashes.dash + 1


def chained(
    pieces: Sequence[Piece], dashes: Dashes
) -> list[tuple[float, tuple[float, float, float, float]]]:
    """The dashes among `pieces` in rows of two or more, each row as (its length: the dashes plus
    the gaps between them, the box around it)."""
    found = [p for p in pieces if is_dash(p, dashes)]
    if len(found) < 2:
        return []
    points = shapely.points([p.centre for p in found])
    near, far = shapely.STRtree(points).query(
        points, predicate="dwithin", distance=ROW * (dashes.dash + dashes.gap)
    )
    root = list(range(len(found)))

    def top(i: int) -> int:
        while root[i] != i:
            root[i] = root[root[i]]
            i = root[i]
        return i

    for i, j in zip(near.tolist(), far.tolist(), strict=True):
        root[top(i)] = top(j)
    rows: dict[int, list[Piece]] = {}
    for i, piece in enumerate(found):
        rows.setdefault(top(i), []).append(piece)
    return [
        (
            sum(p.length for p in row) + (len(row) - 1) * dashes.gap,
            (
                min(p.box[0] for p in row),
                min(p.box[1] for p in row),
                max(p.box[2] for p in row),
                max(p.box[3] for p in row),
            ),
        )
        for row in rows.values()
        if len(row) >= 2
    ]

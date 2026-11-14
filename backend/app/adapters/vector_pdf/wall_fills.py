"""The walls a swiss_dwellings PDF draws as grey-filled polygons (fill 191, black stroke about
0.99 wide), with a gap where a door is. Not read by the vector reader: its extraction and counts
stay as they are. `get_plan_geometry` (app/adapters/pipeline_tools.py) shows them as `walls_drawn`.

A path of two rings is one wall with a hole (even-odd). Measured on site980_bldg2055_floor9178:
9 fills, 21.2 m² at 1:100 against 22.4 m² on the DXF's WALL layer.
"""

from dataclasses import dataclass

from shapely.geometry import Polygon as Shape

from app.adapters.vector_pdf import frame
from app.adapters.vector_pdf.objects import FILL_NONE, PdfPage, PdfPath, Rgb
from app.core.drawing.model import Box, Polygon

WALL_FILL: Rgb = (191, 191, 191)
WALL_STROKE: Rgb = (0, 0, 0)
WALL_WIDTH = 0.9  # points: the walls' outline is about 0.99, other grey fills are thinner


@dataclass(frozen=True)
class WallFill:
    polygon: Polygon  # the outer outline, in page fractions
    holes: tuple[Polygon, ...]
    box: Box
    area_m2: float | None  # net of the holes; None without a scale


def wall_fills(page: PdfPage, m_per_pt: float | None) -> list[WallFill]:
    found: list[WallFill] = []
    for path in page.paths:
        if not _is_wall(path):
            continue
        shapes = sorted((Shape(ring).buffer(0) for ring in path.rings), key=lambda s: -s.area)
        outer = frame.polygon(max(path.rings, key=lambda ring: Shape(ring).buffer(0).area), page)
        if outer is None or not shapes:
            continue
        net = shapes[0]
        for hole in shapes[1:]:
            net = net.symmetric_difference(hole)
        holes = [
            frame.polygon(ring, page)
            for ring in path.rings
            if Shape(ring).buffer(0).area < shapes[0].area
        ]
        found.append(
            WallFill(
                polygon=outer,
                holes=tuple(hole for hole in holes if hole is not None),
                box=frame.box(path.points, page),
                area_m2=None if m_per_pt is None else round(net.area * m_per_pt**2, 3),
            )
        )
    return found


def _is_wall(path: PdfPath) -> bool:
    return (
        path.fill_mode != FILL_NONE
        and path.fill == WALL_FILL
        and path.stroked
        and path.stroke == WALL_STROKE
        and path.width >= WALL_WIDTH
    )

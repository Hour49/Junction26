"""Page points to the page fractions of the drawing model, and what a style reader hands back."""

from collections.abc import Iterable
from dataclasses import dataclass

from shapely.geometry import MultiPolygon
from shapely.geometry import Polygon as Shape
from shapely.geometry.base import BaseGeometry

from app.adapters.vector_pdf.objects import PdfPage, Point
from app.core.drawing.model import Apartment, Box, Element, Plan, Polygon, Room

DECIMALS = 5


@dataclass(frozen=True)
class Reading:
    """What one style's rules found on a page, as page fractions."""

    plans: tuple[Plan, ...] = ()
    elements: tuple[Element, ...] = ()
    rooms: tuple[Room, ...] = ()
    apartments: tuple[Apartment, ...] = ()
    notes: tuple[str, ...] = ()


def _fraction(value: float, size: float) -> float:
    return round(min(max(value / size, 0.0), 1.0), DECIMALS)


def box(points: Iterable[Point], page: PdfPage) -> Box:
    """The box around `points`, clamped to the page."""
    xs, ys = zip(*points, strict=True)
    return (
        _fraction(min(xs), page.width),
        _fraction(min(ys), page.height),
        _fraction(max(xs), page.width),
        _fraction(max(ys), page.height),
    )


def polygon(points: Iterable[Point], page: PdfPage) -> Polygon | None:
    """`points` as an outline, or None when fewer than three are left."""
    ring = tuple((_fraction(x, page.width), _fraction(y, page.height)) for x, y in points)
    if len(ring) > 1 and ring[0] == ring[-1]:
        ring = ring[:-1]
    return ring if len(ring) >= 3 else None


def union_box(boxes: Iterable[Box]) -> Box:
    x0s, y0s, x1s, y1s = zip(*boxes, strict=True)
    return min(x0s), min(y0s), max(x1s), max(y1s)


def shape_of(ring: Iterable[Point]) -> BaseGeometry | None:
    """A ring as a valid shape with an area, or None. A ring that crosses itself is repaired."""
    points = list(ring)
    if len(points) < 3:
        return None
    shape = Shape(points).buffer(0)
    return None if shape.is_empty else shape


def outline_points(shape: BaseGeometry) -> list[Point]:
    """The outer ring of a shape; of its largest part when a repair split it."""
    if isinstance(shape, MultiPolygon):
        shape = max(shape.geoms, key=lambda part: part.area)
    if not isinstance(shape, Shape):
        return []
    return [(x, y) for x, y in shape.exterior.coords]

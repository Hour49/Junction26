"""One plan page as geometry in metres, and its walls between rooms (spec AC-15).

In and out: page fractions (0..1, top left), as get_plan_geometry gives them. Inside: metres,
x_m = x * width_m, y_m = y * height_m, with width_m = page width * metres per page unit.
"""

from dataclasses import dataclass
from typing import Literal

import shapely
from shapely.geometry import GeometryCollection, MultiPolygon, Point, Polygon, box
from shapely.geometry.base import BaseGeometry

from app.core.plan_edit.model import Ring

REACH_M = 0.30  # a room's wall is the mass within this distance of its inside face
MIN_WALL_M = 0.5  # a shorter touch between two rooms is a corner, not a wall between them


@dataclass(frozen=True)
class PlanRoom:
    id: str
    label: str  # as written in the room ("Bagno 1.01"); the id when nothing is written
    type: str  # RoomType
    polygon: Ring
    outdoor: bool = False


@dataclass(frozen=True)
class Opening:
    id: str
    kind: Literal["door", "window"]
    box: tuple[float, float, float, float]


@dataclass(frozen=True)
class PlanPage:
    """What an edit needs of one page: rooms with outlines, the drawn wall mass (outlines with
    holes), doors and windows, and the page size in metres."""

    drawing_id: str
    page: int
    width_m: float
    height_m: float
    rooms: tuple[PlanRoom, ...]
    mass: tuple[tuple[Ring, tuple[Ring, ...]], ...]
    openings: tuple[Opening, ...] = ()

    def shape(self, ring: Ring) -> Polygon:
        """A page-fraction ring as a valid polygon in metres."""
        return _valid(Polygon([(x * self.width_m, y * self.height_m) for x, y in ring]))

    def box_shape(self, found: tuple[float, float, float, float]) -> Polygon:
        x0, y0, x1, y1 = found
        return box(x0 * self.width_m, y0 * self.height_m, x1 * self.width_m, y1 * self.height_m)

    def ring(self, polygon: Polygon) -> Ring:
        """A polygon in metres as a page-fraction ring (its outline; holes are not drawn)."""
        return tuple(
            (round(x / self.width_m, 5), round(y / self.height_m, 5))
            for x, y in list(polygon.exterior.coords)[:-1]
        )

    def frame_box(self, geometry: BaseGeometry) -> tuple[float, float, float, float]:
        x0, y0, x1, y1 = geometry.bounds
        w, h = self.width_m, self.height_m
        return (round(x0 / w, 5), round(y0 / h, 5), round(x1 / w, 5), round(y1 / h, 5))

    def wall_mass(self) -> BaseGeometry:
        return shapely.unary_union(
            [
                _valid(Polygon(self._metres(outer), [self._metres(h) for h in holes]))
                for outer, holes in self.mass
            ]
        )

    def room_at(self, x: float, y: float) -> PlanRoom | None:
        """The room whose outline holds the point (page fractions); None: no room there."""
        at = Point(x * self.width_m, y * self.height_m)
        return next((r for r in self.rooms if self.shape(r.polygon).intersects(at)), None)

    def room_shapes(self) -> dict[str, Polygon]:
        return {room.id: self.shape(room.polygon) for room in self.rooms}

    def _metres(self, ring: Ring) -> list[tuple[float, float]]:
        return [(x * self.width_m, y * self.height_m) for x, y in ring]


@dataclass(frozen=True)
class Wall:
    id: str  # W1..Wn by (top, left) of its strip
    rooms: tuple[str, str]
    strip: BaseGeometry  # metres
    length_m: float
    thickness_m: float
    doors: tuple[str, ...]


def walls_of(page: PlanPage) -> list[Wall]:
    """The partitions between two rooms: mass ∩ A.buffer(t) ∩ B.buffer(t), at least 0.5 m long."""
    mass = page.wall_mass()
    shapes = page.room_shapes()
    reach = {rid: shape.buffer(REACH_M) for rid, shape in shapes.items()}
    ids = list(shapes)
    doors = [o for o in page.openings if o.kind == "door"]
    found: list[tuple[str, str, BaseGeometry, float, float]] = []
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            if not reach[a].intersects(reach[b]):
                continue
            # the closing of the pair keeps the strip between their faces: no nubs into the façade
            rooms = shapely.unary_union([shapes[a], shapes[b]])
            pair = rooms.buffer(REACH_M, join_style="mitre").buffer(-REACH_M, join_style="mitre")
            between = reach[a].intersection(reach[b]).intersection(pair)
            strip = mass.intersection(between)
            boxes = [page.box_shape(d.box) for d in doors]
            gap = shapely.unary_union([box for box in boxes if box.intersects(strip)])
            solid = shapely.unary_union(parts(strip))  # no slivers: GEOS can't cut by them
            opening = gap.intersection(between).difference(rooms).difference(solid)
            if length_of(strip) >= MIN_WALL_M:  # which pairs have a wall: as before
                found.append((a, b, strip, *_dims(strip, opening)))
    found.sort(key=lambda f: (round(f[2].bounds[1], 2), round(f[2].bounds[0], 2)))
    return [
        Wall(
            id=f"W{n}",
            rooms=(a, b),
            strip=strip,
            length_m=round(length, 2),
            thickness_m=round(thickness, 2),
            doors=tuple(d.id for d in doors if page.box_shape(d.box).intersects(strip)),
        )
        for n, (a, b, strip, length, thickness) in enumerate(found, start=1)
    ]


def _dims(strip: BaseGeometry, gap: BaseGeometry) -> tuple[float, float]:
    """A wall's length and thickness as drawn: each piece of its mass alone (a door gap splits
    it; the cut leaves zero-area slivers that one rectangle of the whole strip counted), and the
    door openings along it at its thickness (edits R1: "2.5 m, 0.1 m" for a 3 x 0.12 m wall)."""
    pieces = parts(strip)
    run = sum(length_of(piece) for piece in pieces)
    if run <= 0:
        return 0.0, 0.0
    thickness = sum(piece.area for piece in pieces) / run
    return run + gap.area / thickness, thickness


def length_of(strip: BaseGeometry) -> float:
    """The length of a thin strip: the long side of the rectangle with its area and perimeter,
    so an L-shaped wall counts both legs (a bounding rectangle would count one)."""
    area, half = strip.area, strip.length / 2
    if area <= 0:
        return 0.0
    return (half + max(half * half - 4 * area, 0.0) ** 0.5) / 2


def parts(geometry: BaseGeometry) -> list[Polygon]:
    """The polygons of a geometry, largest first; lines and points dropped."""
    if isinstance(geometry, Polygon):
        found = [geometry]
    elif isinstance(geometry, MultiPolygon):
        found = list(geometry.geoms)
    elif isinstance(geometry, GeometryCollection):
        members: list[BaseGeometry] = list(geometry.geoms)  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
        found = [p for g in members for p in parts(g)]
    else:
        found = []
    return sorted((p for p in found if not p.is_empty and p.area > 0), key=lambda p: -p.area)


def _valid(polygon: Polygon) -> Polygon:
    if polygon.is_valid:
        return polygon
    fixed = parts(polygon.buffer(0))
    return fixed[0] if fixed else polygon

"""Which windows of a building model belong to each of its spaces.

A plan sheet does not draw every window: one above or below the cut has no shape on the page, and
neither has one whose geometry the kernel cannot build (on one dataset model 54 of 110, the wall
drawn solid where they are). So "does this room have a window" is asked of the model, and a
window is linked to a space in three ways, any of which is enough:

- the model says so: an IfcRelSpaceBoundary between the space and the window. Three of the nine
  dev models have them, and one of those leaves a bedroom's window out, so they are not the only
  link;
- the window's shape, seen from above, is within SHAPE_SLACK_M of the space's footprint, and
  their heights overlap. On the dev model whose boundaries are complete this gives the same 206
  pairs as the boundaries, none more;
- a window without a shape is placed by its placement point alone, within POINT_SLACK_M of the
  footprint, heights overlapping (its height is the file's OverallHeight).

A space's windows are known when it has at least one. That it has none is known only when the
space has a solid, the model has windows and every one of them has a shape: a window placed by a
point, or not placed at all, may be the one that was missed, and a model without windows does
not model them.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import ifcopenshell.geom
import ifcopenshell.util.placement
from shapely import STRtree
from shapely.geometry import MultiPoint, Point
from shapely.geometry.base import BaseGeometry

SHAPE_SLACK_M = 0.3  # from a space's footprint (the wall's inner face) to a window in that wall
POINT_SLACK_M = 0.3
OVERLAP_M = 0.3  # the heights of a window and a space share more than a slab's edge


@dataclass(frozen=True)
class Solid:
    """A space's solid: what it covers seen from above, and from which height to which, in m."""

    footprint: BaseGeometry
    low: float
    high: float


def windows_of_spaces(
    file: Any, solids: Mapping[str, Solid], settings: Any, m_per_unit: float
) -> dict[str, tuple[str, ...]]:
    """By a space's GlobalId, the GlobalIds of its windows in the file's order. A space whose
    windows are not known is left out. `solids`: the spaces that have one, by GlobalId;
    `m_per_unit`: the file's length unit in metres."""
    spaces = list(solids)
    tree = STRtree([solids[guid].footprint for guid in spaces])
    linked: dict[str, list[str]] = {}
    for boundary in file.by_type("IfcRelSpaceBoundary"):
        space, window = boundary.RelatingSpace, boundary.RelatedBuildingElement
        if space is None or window is None:
            continue
        if space.is_a("IfcSpace") and window.is_a("IfcWindow"):
            linked.setdefault(space.GlobalId, []).append(window.GlobalId)
    order: dict[str, int] = {}
    shapeless = 0
    for number, window in enumerate(file.by_type("IfcWindow")):
        order[window.GlobalId] = number
        seen = _shape(window, settings)
        slack = SHAPE_SLACK_M
        if seen is None:
            shapeless += 1
            seen, slack = _placed(window, m_per_unit), POINT_SLACK_M
        if seen is None:
            continue
        from_above, low, high = seen
        for index in tree.query(from_above, predicate="dwithin", distance=slack):
            solid = solids[spaces[index]]
            if min(high, solid.high) - max(low, solid.low) > OVERLAP_M:
                linked.setdefault(spaces[index], []).append(window.GlobalId)
    found = {
        space: tuple(sorted(set(windows), key=order.__getitem__))
        for space, windows in linked.items()
    }
    if order and not shapeless:
        found = {**dict.fromkeys(spaces, ()), **found}
    return found


def _shape(window: Any, settings: Any) -> tuple[BaseGeometry, float, float] | None:
    """The window's shape seen from above and its lowest and highest point; None when the
    geometry kernel has nothing it can build. ifcopenshell gives metres, in world coordinates."""
    try:
        shape: Any = ifcopenshell.geom.create_shape(settings, window)
    except RuntimeError:
        return None
    verts = shape.geometry.verts
    if not verts:
        return None
    from_above = MultiPoint(list(zip(verts[0::3], verts[1::3], strict=True))).convex_hull
    return from_above, min(verts[2::3]), max(verts[2::3])


def _placed(window: Any, m_per_unit: float) -> tuple[BaseGeometry, float, float] | None:
    """Where the file places a window that has no shape: its placement point, and from there up
    its stated height. None: the file says neither."""
    if window.ObjectPlacement is None or not window.OverallHeight:
        return None
    placed: Any = ifcopenshell.util.placement.get_local_placement(window.ObjectPlacement)
    x, y, z = (float(placed[axis][3]) * m_per_unit for axis in range(3))
    return Point(x, y), z, z + float(window.OverallHeight) * m_per_unit

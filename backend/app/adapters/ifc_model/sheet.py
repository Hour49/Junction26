"""One plan sheet of a building model: the model says what each object is (objects.py), the
sheet's SVG twin says where it is drawn (svg.py). Ported from
prototypes/extraction-gold/ifc_gold.py.

- An element is a model object the sheet draws: its own shape, or the shapes of its parts (a
  wall drawn as its layers, a stair as its flights). Its box is around all of them. A model
  object the sheet does not draw is not an element: the plan cuts the storey at one height, so
  a window above the cut or a slab below it has no shape and no place on the page, and
  extraction_v1 has no element without a box. The notes count those per class, and the
  drawing's `model_objects` lists every object, drawn or not (`drawn` says which element or
  room each drawn one is). A storey's sums are over that list, not over the elements.
- A room is an IfcSpace the sheet draws. Its area is its outline at the sheet's scale (holes by
  the even-odd rule), which is what the dataset's room areas equal (review-5). Its label is the
  text printed inside it. A sheet also draws spaces of other storeys that reach through the cut:
  those are rooms too, marked `foreign`, so a storey's rooms are picked by `storey`.
- The sheet's storey is the one its title names, when the model puts objects on that storey.
  Otherwise (a "Foundation" sheet: the model has that level and nothing on it, and the sheet
  shows the storey above through the cut) it is a vote: the storey with the most drawn doors,
  windows, walls and spaces.
"""

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from shapely.geometry import MultiPolygon
from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import Polygon as Shape
from shapely.geometry.base import BaseGeometry

from app.adapters.ifc_model.objects import CLASSES, IfcObject, Model
from app.adapters.ifc_model.svg import Group, Point, SheetSvg
from app.adapters.vector_pdf.ifc_render import room_type
from app.core.drawing.model import (
    Attr,
    Box,
    Element,
    ElementClass,
    Plan,
    Polygon,
    QuantityKey,
    Room,
)

PLAN = "p1"
DECIMALS = 5
OUTLINE_CORNERS = (3, 60)  # an element drawn as one ring this long keeps it as its polygon
VOTERS: tuple[ElementClass, ...] = ("door", "window", "wall")
# A model object's quantity -> the attr a drawn element carries it as (the extraction gold's
# names, which app/core/pipeline/rules.py MEASURED reads).
ATTRS: Mapping[QuantityKey, str] = {
    "length_m": "length_m",
    "side_area_m2": "net_side_area_m2",
    "volume_m3": "net_volume_m3",
}


@dataclass(frozen=True)
class SheetReading:
    storey: str | None  # the storey the sheet shows
    plans: tuple[Plan, ...]
    elements: tuple[Element, ...]
    rooms: tuple[Room, ...]
    drawn: Mapping[str, str]  # GlobalId -> the id of the element or room it is drawn as
    notes: tuple[str, ...]


def read_sheet(
    model: Model, svg: SheetSvg, m_per_svg_unit: float | None, titled: str | None
) -> SheetReading:
    """`titled`: the storey the sheet's title names, when it has one."""
    storey = titled if titled in _storeys_in_use(model) else _most_drawn_storey(model, svg)
    elements, undrawn, listed = _elements(model, svg, storey)
    rooms, tinted = _rooms(model, svg, storey, m_per_svg_unit)
    boxes = [*(element.box for element in elements), *(room.box for room in rooms)]
    around = (
        (
            min(box[0] for box in boxes),
            min(box[1] for box in boxes),
            max(box[2] for box in boxes),
            max(box[3] for box in boxes),
        )
        if boxes
        else (0.0, 0.0, 1.0, 1.0)  # nothing we list is drawn: the plan is the page
    )
    notes: list[str] = []
    if undrawn:
        notes.append(
            f"the model lists on storey {storey}, and this sheet does not draw: "
            + ", ".join(f"{count} {class_}" for class_, count in sorted(undrawn.items()))
        )
    other = Counter(
        group.ifc_class for guid, group in svg.groups.items() if guid not in listed | tinted
    )
    if other:
        notes.append(
            "drawn shapes of classes the drawing model has no name for: "
            + ", ".join(f"{count} {name}" for name, count in sorted(other.items()))
        )
    return SheetReading(
        storey=storey,
        plans=(Plan(id=PLAN, page=1, box=around, storey=storey),),
        elements=elements,
        rooms=rooms,
        drawn={str(item.attrs["global_id"]): item.id for item in (*elements, *rooms)},
        notes=tuple(notes),
    )


def _drawn(found: IfcObject, svg: SheetSvg) -> list[Group]:
    """The shapes the sheet draws for an object: its own and its parts'."""
    return [svg.groups[guid] for guid in (found.guid, *found.parts) if guid in svg.groups]


def _storeys_in_use(model: Model) -> set[str | None]:
    listed = [found for objects in model.elements.values() for found in objects]
    return {found.storey for found in (*listed, *model.spaces) if found.storey is not None}


def _most_drawn_storey(model: Model, svg: SheetSvg) -> str | None:
    votes: Counter[str] = Counter()
    voters = [found for class_ in VOTERS for found in model.elements[class_]]
    for found in (*voters, *model.spaces):
        if found.storey is not None and _drawn(found, svg):
            votes[found.storey] += 1
    return votes.most_common(1)[0][0] if votes else None


def _elements(
    model: Model, svg: SheetSvg, storey: str | None
) -> tuple[tuple[Element, ...], Counter[str], set[str]]:
    """The drawn objects as elements; how many objects of the sheet's storey are not drawn, per
    class; and the GlobalIds of every shape used."""
    elements: list[Element] = []
    undrawn: Counter[str] = Counter()
    listed: set[str] = set()
    for class_ in CLASSES.values():
        for found in model.elements[class_]:
            shapes = _drawn(found, svg)
            if not shapes:
                undrawn[class_] += found.storey == storey
                continue
            listed.update(guid for guid in (found.guid, *found.parts) if guid in svg.groups)
            attrs: dict[str, Attr] = {
                "source_class": found.source_class,
                "global_id": found.guid,
                "storey": found.storey,
                "parts": len(shapes),
                **{ATTRS[key]: value for key, value in found.quantities.items()},
            }
            elements.append(
                Element(
                    id=f"e{len(elements) + 1}",
                    class_=class_,
                    page=1,
                    plan=PLAN,
                    box=_box([point for shape in shapes for point in shape.points], svg),
                    polygon=_outline(shapes, svg),
                    attrs=attrs,
                )
            )
    return tuple(elements), +undrawn, listed


def _rooms(
    model: Model, svg: SheetSvg, storey: str | None, m_per_svg_unit: float | None
) -> tuple[tuple[Room, ...], set[str]]:
    filled: dict[str, BaseGeometry] = {}
    for space in model.spaces:
        group = svg.groups.get(space.guid)
        if group is not None and (shape := _even_odd(group.rings)) is not None:
            filled[space.guid] = shape
    lines: dict[str, list[tuple[float, float, str]]] = {guid: [] for guid in filled}
    for text in svg.texts:
        point = ShapelyPoint(text.at)
        holding = [guid for guid, shape in filled.items() if shape.contains(point)]
        if holding:  # a text belongs to the smallest room around it (the first of equal ones)
            smallest = min(holding, key=lambda guid: filled[guid].area)
            lines[smallest].append((text.at[1], text.at[0], text.text))
    rooms: list[Room] = []
    for space in model.spaces:
        if space.guid not in filled:
            continue
        shape, group = filled[space.guid], svg.groups[space.guid]
        label = " ".join(text for _, _, text in sorted(lines[space.guid])) or None
        whole = (
            max(shape.geoms, key=lambda part: part.area)
            if isinstance(shape, MultiPolygon)
            else shape
        )
        rooms.append(
            Room(
                id=f"r{len(rooms) + 1}",
                type=room_type(label or group.name or ""),
                label=label,
                page=1,
                plan=PLAN,
                polygon=_polygon([(x, y) for x, y in whole.exterior.coords][:-1], svg)
                if isinstance(whole, Shape)
                else None,
                box=_box(group.points, svg),
                area_m2=None
                if m_per_svg_unit is None
                else round(shape.area * m_per_svg_unit**2, 3),
                attrs={
                    "number": group.name,
                    "storey": space.storey,
                    "global_id": space.guid,
                    "foreign": space.storey != storey,
                    "source_class": space.source_class,
                    "ifc_name": space.name,
                    "ifc_long_name": space.long_name,
                },
            )
        )
    return tuple(rooms), set(filled)


def _even_odd(rings: Sequence[Sequence[Point]]) -> BaseGeometry | None:
    """The filled area of a shape under the even-odd rule: a ring inside another is a hole."""
    shapes = sorted(
        (
            shape
            for ring in rings
            if len(ring) >= 3 and not (shape := Shape(ring).buffer(0)).is_empty
        ),
        key=lambda shape: -shape.area,
    )
    if not shapes:
        return None
    filled = shapes[0]
    for shape in shapes[1:]:
        filled = filled.symmetric_difference(shape)
    return None if filled.is_empty else filled


def _fraction(value: float) -> float:
    return round(min(max(value, 0.0), 1.0), DECIMALS)


def _box(points: Sequence[Point], svg: SheetSvg) -> Box:
    xs, ys = zip(*(svg.fraction(point) for point in points), strict=True)
    return _fraction(min(xs)), _fraction(min(ys)), _fraction(max(xs)), _fraction(max(ys))


def _polygon(points: Sequence[Point], svg: SheetSvg) -> Polygon | None:
    ring = tuple((_fraction(x), _fraction(y)) for x, y in map(svg.fraction, points))
    return ring if len(ring) >= 3 else None


def _outline(shapes: Sequence[Group], svg: SheetSvg) -> Polygon | None:
    """The outline of an element drawn as one shape: its longest ring. It says more than a box on
    a plan that is turned on the page."""
    if len(shapes) != 1:
        return None
    ring = max(shapes[0].rings, key=len)
    low, high = OUTLINE_CORNERS
    return _polygon(ring, svg) if low <= len(ring) <= high else None

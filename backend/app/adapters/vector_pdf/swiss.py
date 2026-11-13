"""Reading rules for floor plans in the swiss_dwellings sheet style, from the PDF alone.

One generator drew every sheet of that set, so a symbol has a fixed stroke, width and number of
segments, and a fill colour means something. Ported from prototypes/pdf-extract/swiss_counts.py
and swiss_areas.py, which measured these rules against the dataset's answers:

- Door: grey (68,68,68) 5-segment outline, one per opening, so a double door is one door.
- Toilet: a 48-segment black outline with a 2-segment tank line of the same width. Washbasin:
  the 48-segment outlines without one. Bathtub: 69 segments. Shower: 5 segments, stroke only.
- Window: a white-filled black rectangle with at least two lines along its long side, about as
  long as it and centred in it. The test uses the rectangle's own axis, because plans are
  rotated; a lift (crossing diagonals) fails it.
- Room: a filled outline with stroke (138,138,138) that holds a room number. Its net area is the
  outline minus what is nested in it: the holes of its own compound path and smaller room
  outlines. Fill grey 228 is outdoor, 243 a lift, stair or shaft.
- Apartment: a "Whg. A" / "App. A" label. Its rooms are those inside the red dashed unit outline
  that holds the labelled room; its area leaves out outdoor rooms and fill-243 rooms.

Known misses (prototypes/pdf-extract/README.md): a stair flight with two lines along its long
side reads as a window; an apartment spread over several unit outlines gets only one of them.
"""

import math
import re
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from shapely.geometry import Point as ShapelyPoint
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from app.adapters.vector_pdf import frame
from app.adapters.vector_pdf.frame import Reading
from app.adapters.vector_pdf.objects import (
    FILL_NONE,
    FILL_WINDING,
    Bounds,
    PdfPage,
    PdfPath,
    PdfText,
    Rgb,
)
from app.adapters.vector_pdf.scale import PRINTED_AREA
from app.core.drawing.model import (
    Apartment,
    Element,
    ElementClass,
    Plan,
    ReadClass,
    Room,
    RoomType,
)

BLACK: Rgb = (0, 0, 0)
DOOR_STROKE: Rgb = (68, 68, 68)
ROOM_STROKE: Rgb = (138, 138, 138)
UNIT_STROKE: Rgb = (176, 58, 46)
THIN, SYMBOL, UNIT_WIDTH = 0.37, 0.51, 1.28
OUTDOOR_FILL, SHAFT_FILL = 228, 243
NESTED_SLACK = 0.3  # points: a nested outline may touch the outline around it
PLAN = "p1"
# What the rules below look for. Any other class is not read on these sheets: no count for it.
LOOKS_FOR: tuple[ReadClass, ...] = ("door", "window", "toilet", "sink", "bathtub", "shower", "room")

NUMBER = re.compile(r"[A-Z]*\d+\.\d+")
UNIT_LABEL = re.compile(r"^(?:Whg|Wohnung|App|Appt|Appartement|Alloggio)\.?\s+([A-Z])$")
OUTDOOR_NAMES = {
    "Balkon", "Balcon", "Balcone", "Loggia", "Terrasse", "Terrazza", "Sitzplatz", "Garten",
    "Patio", "Arkade", "Jardin d'hiver", "Wintergarten", "Giardino d'inverno",
}  # fmt: skip
BALCONY_NAMES = {"Balkon", "Balcon", "Balcone"}
SHAFT_NAMES = {"Lift", "Ascenseur", "Ascensore", "Treppenhaus", "Cage d'escalier", "Vano scala"}
ROOM_TYPES: dict[RoomType, set[str]] = {
    "kitchen": {"Küche", "Cuisine", "Cucina", "Küche/Essen"},
    "bathroom": {"Bad", "Bain", "Bagno"},
    "bedroom": {"Schlafzimmer", "Chambre à coucher", "Camera da letto"},
    "living": {
        "Wohnen", "Wohnen/Essen", "Séjour", "Séjour/repas", "Soggiorno", "Soggiorno/pranzo",
        "Essen", "Repas", "Pranzo",
    },
    "hall": {"Korridor", "Couloir", "Corridoio", "Halle", "Hall", "Eingangshalle"},
    "storage": {
        "Reduit", "Réduit", "Ripostiglio", "Kellerabteil", "Vano cantina", "Compartiment cave",
    },
}  # fmt: skip


@dataclass(frozen=True)
class _Outline:
    shape: BaseGeometry
    holes: tuple[BaseGeometry, ...]
    fill: int


@dataclass(frozen=True)
class _RoomFound:
    outline: _Outline
    number: str | None
    name: str | None
    unit: str | None  # the apartment letter written in the room
    net_pt2: float
    cutouts: int
    printed: tuple[float, Bounds] | None  # the area printed in the room, m², and where


def is_room_outline(path: PdfPath) -> bool:
    return path.stroke == ROOM_STROKE and path.width == THIN and path.fill_mode == FILL_WINDING


def matches(page: PdfPage) -> bool:
    return any(is_room_outline(path) for path in page.paths)


def read(page: PdfPage, m_per_pt: float | None) -> Reading:
    found = _rooms(page)
    rooms, apartments = _room_models(found, _unit_outlines(page), page, m_per_pt)
    elements = _elements(page)
    boxes = [room.box for room in rooms] or [element.box for element in elements]
    plans = (Plan(id=PLAN, page=1, box=frame.union_box(boxes)),) if boxes else ()
    return Reading(plans=plans, elements=elements, rooms=rooms, apartments=apartments)


def _pick(page: PdfPage, segments: int, fill_mode: int, stroke: Rgb, width: float) -> list[PdfPath]:
    return [
        path
        for path in page.paths
        if (path.segments, path.fill_mode, path.stroke, path.width)
        == (segments, fill_mode, stroke, width)
    ]


def _holds(outer: PdfPath, inner: PdfPath, slack: float = 1.0) -> bool:
    ox0, oy0, ox1, oy1 = outer.bounds
    ix0, iy0, ix1, iy1 = inner.bounds
    return ix0 >= ox0 - slack and iy0 >= oy0 - slack and ix1 <= ox1 + slack and iy1 <= oy1 + slack


def _centre_distance(a: PdfPath, b: PdfPath) -> float:
    ax0, ay0, ax1, ay1 = a.bounds
    bx0, by0, bx1, by1 = b.bounds
    return math.hypot((ax0 + ax1 - bx0 - bx1) / 2, (ay0 + ay1 - by0 - by1) / 2)


def is_window(rect: PdfPath, lines: Sequence[PdfPath]) -> bool:
    """A rectangle with two or more lines along its long side, about its length, centred."""
    v = rect.points[:4]
    e1 = (v[1][0] - v[0][0], v[1][1] - v[0][1])
    e2 = (v[2][0] - v[1][0], v[2][1] - v[1][1])
    l1, l2 = math.hypot(*e1), math.hypot(*e2)
    if min(l1, l2) < 1e-6:
        return False
    long_edge, length, width = (e1, l1, l2) if l1 >= l2 else (e2, l2, l1)
    ux, uy = long_edge[0] / length, long_edge[1] / length
    cx, cy = sum(p[0] for p in v) / 4, sum(p[1] for p in v) / 4
    parallel = 0
    for line in lines:
        (x0, y0), (x1, y1) = line.points[:2]
        dx, dy = x1 - x0, y1 - y0
        size = math.hypot(dx, dy)
        if size < 1e-6 or abs(dx * uy - dy * ux) / size > 0.05:
            continue
        mx, my = (x0 + x1) / 2 - cx, (y0 + y1) / 2 - cy
        along, across = mx * ux + my * uy, -mx * uy + my * ux
        if (
            abs(along) <= 0.8
            and abs(across) <= width / 2 + 0.3
            and 0.8 * length <= size <= 1.2 * length
        ):
            parallel += 1
    return parallel >= 2


def _elements(page: PdfPage) -> tuple[Element, ...]:
    thin_lines = _pick(page, 2, FILL_NONE, BLACK, THIN)
    basins = _pick(page, 48, FILL_NONE, BLACK, SYMBOL)
    toilets: list[PdfPath] = []
    for tank in _pick(page, 2, FILL_NONE, BLACK, SYMBOL):
        # The tank line claims the basin outline around it, else the nearest one still free.
        free = sorted(basins, key=lambda b: (not _holds(b, tank), _centre_distance(b, tank)))
        toilets.append(free[0] if free else tank)
        basins = [basin for basin in basins if basin is not toilets[-1]]
    by_class: dict[ElementClass, list[PdfPath]] = {
        "door": _pick(page, 5, FILL_NONE, DOOR_STROKE, THIN),
        "window": [
            rect
            for rect in _pick(page, 5, FILL_WINDING, BLACK, SYMBOL)
            if is_window(rect, thin_lines)
        ],
        "toilet": toilets,
        "sink": basins,
        "bathtub": _pick(page, 69, FILL_NONE, BLACK, SYMBOL),
        "shower": _pick(page, 5, FILL_NONE, BLACK, SYMBOL),
    }
    elements: list[Element] = []
    for class_, paths in by_class.items():
        for path in paths:
            elements.append(
                Element(
                    id=f"e{len(elements) + 1}",
                    class_=class_,
                    page=1,
                    plan=PLAN,
                    box=frame.box(path.points, page),
                )
            )
    return tuple(elements)


def _outline(path: PdfPath) -> _Outline | None:
    """A room path as its outline and holes: the largest ring is the outline."""
    shapes = sorted(
        (shape for ring in path.rings if (shape := frame.shape_of(ring)) is not None),
        key=lambda shape: -shape.area,
    )
    if not shapes:
        return None
    around = shapes[0].buffer(NESTED_SLACK)
    return _Outline(shapes[0], tuple(s for s in shapes[1:] if around.contains(s)), path.fill[0])


def _unit_outlines(page: PdfPage) -> list[BaseGeometry]:
    return [
        outline.shape
        for path in page.paths
        if path.stroke == UNIT_STROKE
        and abs(path.width - UNIT_WIDTH) < 0.05
        and (outline := _outline(path)) is not None
    ]


def _rooms(page: PdfPage) -> list[_RoomFound]:
    """Every room outline that holds text, with the words written in it."""
    outlines = [
        outline
        for path in page.paths
        if is_room_outline(path) and (outline := _outline(path)) is not None
    ]
    words: dict[int, list[PdfText]] = defaultdict(list)
    for text in page.texts:
        point = ShapelyPoint(text.centre)
        holding = [
            (outline.shape.area, index)
            for index, outline in enumerate(outlines)
            if outline.shape.contains(point)
        ]
        if holding:  # a text belongs to the smallest outline around it
            words[min(holding)[1]].append(text)
    rooms: list[_RoomFound] = []
    for index, lines in words.items():
        outline = outlines[index]
        # Top to bottom; two texts at one height keep the order the prototype measured with.
        ordered = sorted(lines, key=lambda line: (-line.centre[1], line.text), reverse=True)
        top_down = [line.text for line in ordered]
        printed = next(
            (
                (float(area.group(1).replace(",", ".")), line.bounds)
                for line in ordered
                if (area := PRINTED_AREA.fullmatch(line.text))
            ),
            None,
        )
        number = next((text for text in top_down if NUMBER.fullmatch(text)), None)
        unit = next((m.group(1) for text in top_down if (m := UNIT_LABEL.match(text))), None)
        names = [
            text
            for text in top_down
            if text != number and not UNIT_LABEL.match(text) and "m²" not in text
        ]
        around = outline.shape.buffer(NESTED_SLACK)
        inner_rooms = [
            other.shape
            for at, other in enumerate(outlines)
            if at != index
            and other.shape.area < outline.shape.area
            and around.contains(other.shape)
        ]
        nested = [*outline.holes, *inner_rooms]
        net = outline.shape.difference(unary_union(nested)).area if nested else outline.shape.area
        name = names[0] if names else None
        rooms.append(_RoomFound(outline, number, name, unit, net, len(inner_rooms), printed))
    return rooms


def _numbered(found: Sequence[_RoomFound]) -> list[_RoomFound]:
    """The rooms that are listed, in the order of their ids: r1 has the lowest room number."""
    return sorted((room for room in found if room.number), key=lambda room: room.number or "")


def printed_areas(page: PdfPage) -> list[tuple[str, float, Bounds]]:
    """The area printed in a room, for every listed room that prints one: the room's id as
    `read` gives it, the square metres, and the label's place in points."""
    return [
        (f"r{index}", *room.printed)
        for index, room in enumerate(_numbered(_rooms(page)), start=1)
        if room.printed is not None
    ]


def room_type(name: str | None, fill: int) -> tuple[RoomType, bool]:
    """The room type and whether the room is outdoor, from its label and its fill grey."""
    if name in BALCONY_NAMES:
        return "balcony", True
    if name in OUTDOOR_NAMES or fill == OUTDOOR_FILL:
        return "outdoor", True
    if name in SHAFT_NAMES or (name is None and fill == SHAFT_FILL):
        return "shaft", False
    for kind, names in ROOM_TYPES.items():
        if name in names:
            return kind, False
    return "other", False


def _room_models(
    found: Sequence[_RoomFound],
    units: Sequence[BaseGeometry],
    page: PdfPage,
    m_per_pt: float | None,
) -> tuple[tuple[Room, ...], tuple[Apartment, ...]]:
    """The numbered rooms and the apartments. Without a scale the areas stay unknown."""
    m2_per_pt2 = None if m_per_pt is None else m_per_pt**2
    unit_of_letter: dict[str, BaseGeometry | None] = {}
    for room in sorted((r for r in found if r.unit), key=lambda r: r.unit or ""):
        if room.unit is not None and room.unit not in unit_of_letter:
            point = room.outline.shape.representative_point()
            holding = [unit for unit in units if unit.contains(point)]
            unit_of_letter[room.unit] = min(holding, key=lambda u: u.area) if holding else None

    rooms: list[Room] = []
    indoor_pt2: dict[str, float] = defaultdict(float)
    for index, room in enumerate(_numbered(found), start=1):
        kind, outdoor = room_type(room.name, room.outline.fill)
        point = room.outline.shape.representative_point()
        letter = next(
            (
                key
                for key, unit in unit_of_letter.items()
                if unit is not None and unit.contains(point)
            ),
            None,
        )
        if letter is not None and not outdoor and room.outline.fill != SHAFT_FILL:
            indoor_pt2[letter] += room.net_pt2
        outer = frame.outline_points(room.outline.shape)
        rooms.append(
            Room(
                id=f"r{index}",
                type=kind,
                label=room.name,
                page=1,
                plan=PLAN,
                polygon=frame.polygon(outer, page),
                box=frame.box(outer, page),
                area_m2=None if m2_per_pt2 is None else round(room.net_pt2 * m2_per_pt2, 3),
                apartment=None if letter is None else f"a{letter}",
                outdoor=outdoor,
                attrs={"number": room.number, "fill": room.outline.fill, "cutouts": room.cutouts},
            )
        )
    apartments = tuple(
        Apartment(
            id=f"a{letter}",
            label=letter,
            area_m2=None
            if unit is None or m2_per_pt2 is None
            else round(indoor_pt2[letter] * m2_per_pt2, 3),
        )
        for letter, unit in unit_of_letter.items()
    )
    return tuple(rooms), apartments

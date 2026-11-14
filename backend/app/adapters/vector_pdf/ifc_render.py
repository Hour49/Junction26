"""Reading rules for plan sheets rendered from an IFC model by IfcOpenShell's IfcConvert (the
ifc_models sheets), from the PDF alone. The room rules are ported from
prototypes/pdf-extract/ifc_plan_areas.py.

The renderer draws every shape as a fill and then the same outline again as a stroke, and gives
each IFC class a style. What a style can and cannot tell:

- Room (IfcSpace): fill #e3edf7. One path per room; sub-paths are holes (even-odd). The label is
  the text objects inside it, top to bottom: the name line, then the number line. The area is
  the drawn polygon times the sheet's scale, which is what the dataset's room areas equal.
- Cut solid: fill #4a4a4a. Walls and columns share this style, and so do classes the format has
  no name for (building element parts, coverings). Each one is listed as a wall, and a note says
  so. Calling the small squarish ones columns was tried on the 11 dev sheets of golden v2: it
  found every column but was right only 48% of the time, because short wall pieces look the same.
- Window: white fill with a black 0.1 stroke. A window is several shapes drawn one after the
  other (frame, panes, sill) that lie on or alongside each other. The next window of a strip
  touches too, but at the end. So a shape joins the window drawn before it when their boxes touch
  and at least half of the shape's length along the window lies within the window's length.
- Door: no fill, black 0.13 stroke. A door is drawn as its frame pieces (shapes with several
  sub-paths) and then its leaf and swing (one sub-path each), so a frame piece that follows a
  leaf or swing starts the next door. The two jambs of a door do not touch, and two doors can
  overlap, so position cannot group them.

Not read: stairs, railings, slabs and beams (one shared style, stroke #333333), and anything the
PDF does not draw. Known misses of the room rules: a room whose hole the fill does not show, and
a label that lies outside its small room.
"""

import re
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from shapely.geometry import Point as ShapelyPoint
from shapely.geometry.base import BaseGeometry

from app.adapters.vector_pdf import frame
from app.adapters.vector_pdf.frame import Reading
from app.adapters.vector_pdf.objects import FILL_NONE, Bounds, PdfPage, Point, Rgb, bounds_of
from app.core.drawing.model import (
    Attr,
    Box,
    Element,
    ElementClass,
    Plan,
    Polygon,
    ReadClass,
    Room,
    RoomType,
)

BLACK: Rgb = (0, 0, 0)
WHITE: Rgb = (255, 255, 255)
SPACE_FILL: Rgb = (227, 237, 247)
SOLID_FILL: Rgb = (74, 74, 74)
WINDOW_WIDTH, DOOR_WIDTH = 0.1, 0.13
SAME_WINDOW = 0.5  # share of a shape's length that lies within the window drawn before it
THIN = 0.5  # points: boxes this close touch
PLAN = "p1"
# What the rules above look for. Columns, stairs, railings, slabs and beams are not read: no
# count for them (the cut solids listed as walls include the columns).
LOOKS_FOR: tuple[ReadClass, ...] = ("room", "wall", "window", "door")
# The sheet title ends "<project> — <"Floor plan" in the sheet's language>: <storey>".
STOREY = re.compile(r" — [^:]+: (.+)$")
# A room's type from the words of its label, the first row that matches. The words are those the
# models' authors wrote, in their languages; a label no row knows is "other". Added on 2026-11-14
# from the space names of the nine dev models, each only where a label was "other" before:
# Estonian (tualett, vannituba, magamistuba, elutuba, köök, koridor, fuajee, esik, panipaik,
# saun), Spanish flat codes as in "2IZQ-HAB3" (-hab, -sal, -coc, -bañ, -dist; rellano, portal,
# salón), Dutch (douche, kast), German (Zimmer on its own: a flat's room; Vorraum, "Vorr.";
# Einstellraum) and English (communication).
ROOM_WORDS: tuple[tuple[RoomType, str], ...] = (
    ("wc", r"\bwc\b|toilet|toilette|aseo|wc-|sanit|tualett"),
    (
        "bathroom",
        r"\bbad\b|bath|badkamer|badrum|bagno|baño|łazienk|kylpy|vonn|vannituba|douche|-bañ\b",
    ),
    (
        "bedroom",
        r"schlaf|bedroom|slaap|soverom|sypialn|dormitor|camera|habitaci|makuu|magamistuba"
        r"|-hab\d*\b|\bzimmer\b",
    ),
    ("living", r"elutuba"),  # before the kitchens: "ELUTUBA+KÖÖK" is a living room with its kitchen
    ("kitchen", r"küche|kuche|kitchen|keuken|køkken|kokken|kuchn|cocina|cucina|keitti|köök|-coc\b"),
    ("living", r"wohn|living|woon|stue|salon|salón|soggiorno|olohuone|-sal\b"),
    (
        "hall",
        r"flur|gang\b|hall|corridor|korytarz|pasillo|gang |trappe|vestibul|foyer|koridor|fuajee"
        r"|\besik\b|-dist\b|rellano|portal|vorraum|\bvorr\b|comm?unication",
    ),
    (
        "storage",
        r"abstell|storage|lager|bod\b|berging|depot|boiler|technik|kast\b|panipaik|einstellr",
    ),
    ("shaft", r"schacht|skakt|shaft|schaft"),
    ("balcony", r"balkon|balcon|terras|terrace|loggia"),
    ("sauna", r"sauna|\bsaun\b"),
)


@dataclass(frozen=True)
class _Drawn:
    """One shape as the renderer meant it: its fill and the stroke of its twin."""

    fill: Rgb | None
    stroke: Rgb | None
    width: float | None
    rings: tuple[tuple[Point, ...], ...]

    @property
    def points(self) -> tuple[Point, ...]:
        return tuple(point for ring in self.rings for point in ring)


def matches(page: PdfPage) -> bool:
    return any(
        path.fill_mode != FILL_NONE and path.fill in (SPACE_FILL, SOLID_FILL) for path in page.paths
    )


def read(page: PdfPage, m_per_pt: float | None) -> Reading:
    drawn = _drawn(page)
    rooms = _rooms([shape for shape in drawn if shape.fill == SPACE_FILL], page, m_per_pt)
    by_class: dict[ElementClass, list[list[_Drawn]]] = {
        "wall": [[shape] for shape in drawn if shape.fill == SOLID_FILL],
        "window": _windows(drawn),
        "door": _doors(drawn),
    }
    elements: list[Element] = []
    for class_, groups in by_class.items():
        for group in groups:
            elements.append(
                Element(
                    id=f"e{len(elements) + 1}",
                    class_=class_,
                    page=1,
                    plan=PLAN,
                    box=frame.box([point for shape in group for point in shape.points], page),
                    polygon=_single_ring(group, page),
                )
            )
    solids = len(by_class["wall"])
    notes = (
        (
            f"{solids} cut solids are listed as walls: the sheet draws walls, columns and other "
            "cut parts in one style",
        )
        if solids
        else ()
    )
    boxes: list[Box] = [*(room.box for room in rooms), *(element.box for element in elements)]
    storey = next((m.group(1) for text in page.texts if (m := STOREY.search(text.text))), None)
    plans = (Plan(id=PLAN, page=1, box=frame.union_box(boxes), storey=storey),) if boxes else ()
    return Reading(plans=plans, elements=tuple(elements), rooms=rooms, notes=notes)


def _drawn(page: PdfPage) -> list[_Drawn]:
    """The page's paths with each fill joined to the stroke twin that follows it."""
    drawn: list[_Drawn] = []
    paths = page.paths
    index = 0
    while index < len(paths):
        path = paths[index]
        twin = paths[index + 1] if index + 1 < len(paths) else None
        if path.fill_mode == FILL_NONE:
            drawn.append(_Drawn(None, path.stroke, path.width, path.rings))
        elif (
            not path.stroked
            and twin is not None
            and twin.fill_mode == FILL_NONE
            and twin.rings == path.rings
        ):
            drawn.append(_Drawn(path.fill, twin.stroke, twin.width, path.rings))
            index += 1
        else:
            stroke, width = (path.stroke, path.width) if path.stroked else (None, None)
            drawn.append(_Drawn(path.fill, stroke, width, path.rings))
        index += 1
    return drawn


def _single_ring(group: Sequence[_Drawn], page: PdfPage) -> Polygon | None:
    """The outline of an element drawn as exactly one ring; a box says more than one ring of
    several would."""
    if len(group) == 1 and len(group[0].rings) == 1:
        return frame.polygon(group[0].rings[0], page)
    return None


def _alongside(shape: Bounds, window: Bounds) -> bool:
    """Whether `shape` touches `window` and lies along it, not beyond its end."""
    along = 0 if window[2] - window[0] >= window[3] - window[1] else 1  # the window's long axis
    low, high = shape[along] - THIN, shape[along + 2] + THIN
    shared = min(high, window[along + 2] + THIN) - max(low, window[along] - THIN)
    across = 1 - along
    touches = (
        shape[across] <= window[across + 2] + THIN and window[across] <= shape[across + 2] + THIN
    )
    return touches and shared >= SAME_WINDOW * (high - low)


def _windows(drawn: Sequence[_Drawn]) -> list[list[_Drawn]]:
    """Window-style shapes in drawing order; one that lies on the window before it is part of
    that window."""
    groups: list[list[_Drawn]] = []
    previous_was_window = False
    for shape in drawn:
        is_window = (shape.fill, shape.stroke, shape.width) == (WHITE, BLACK, WINDOW_WIDTH)
        if is_window:
            if previous_was_window and _alongside(
                bounds_of(shape.points),
                bounds_of(tuple(point for other in groups[-1] for point in other.points)),
            ):
                groups[-1].append(shape)
            else:
                groups.append([shape])
        previous_was_window = is_window
    return groups


def _doors(drawn: Sequence[_Drawn]) -> list[list[_Drawn]]:
    """Door-style shapes in drawing order; a frame piece (several sub-paths) that follows a leaf
    or swing (one sub-path) starts the next door."""
    groups: list[list[_Drawn]] = []
    for shape in drawn:
        if (shape.fill, shape.stroke, shape.width) != (None, BLACK, DOOR_WIDTH):
            continue
        starts = not groups or (len(shape.rings) > 1 and len(groups[-1][-1].rings) == 1)
        if starts:
            groups.append([shape])
        else:
            groups[-1].append(shape)
    return groups


def room_type(label: str) -> RoomType:
    low = label.lower()
    for kind, words in ROOM_WORDS:
        if re.search(words, low):
            return kind
    return "other"


def _even_odd(rings: Sequence[Sequence[Point]]) -> BaseGeometry | None:
    """The filled area of a path under the even-odd rule: a ring inside another is a hole."""
    shapes = sorted(
        (shape for ring in rings if (shape := frame.shape_of(ring)) is not None),
        key=lambda shape: -shape.area,
    )
    if not shapes:
        return None
    filled = shapes[0]
    for shape in shapes[1:]:
        filled = filled.symmetric_difference(shape)
    return None if filled.is_empty else filled


def _rooms(spaces: Sequence[_Drawn], page: PdfPage, m_per_pt: float | None) -> tuple[Room, ...]:
    shapes = [(filled, space) for space in spaces if (filled := _even_odd(space.rings)) is not None]
    lines: dict[int, list[tuple[float, float, str]]] = defaultdict(list)
    for text in page.texts:
        point = ShapelyPoint(text.centre)
        holding = [
            (filled.area, index)
            for index, (filled, _) in enumerate(shapes)
            if filled.contains(point)
        ]
        if holding:  # a text belongs to the smallest room around it
            lines[min(holding)[1]].append((text.centre[1], text.centre[0], text.text))
    rooms: list[Room] = []
    for index, (filled, space) in enumerate(shapes):
        words = [" ".join(text.split()) for _, _, text in sorted(lines[index])]
        label = " ".join(words) or None
        attrs: dict[str, Attr] = {}
        if len(words) > 1:  # the name line(s), then the number line
            attrs = {"number": words[-1], "name": " ".join(words[:-1])}
        outer = frame.outline_points(filled) or list(space.points)
        rooms.append(
            Room(
                id=f"r{index + 1}",
                type=room_type(label or ""),
                label=label,
                page=1,
                plan=PLAN,
                polygon=frame.polygon(outer, page),
                box=frame.box(space.points, page),
                area_m2=None if m_per_pt is None else round(filled.area * m_per_pt**2, 3),
                attrs=attrs,
            )
        )
    return tuple(rooms)

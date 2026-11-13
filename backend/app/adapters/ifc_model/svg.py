"""The SVG twin of a plan sheet rendered from an IFC model (IfcOpenShell's IfcConvert writes the
PDF and the SVG from the same drawing). The SVG says which object each shape is: one group per
object, `<g class="[cut ]IfcDoor" data-guid="<GlobalId>" data-name="...">`, holding its paths
(M, L and A commands) or, for round columns, circles. Room labels are `<text>` elements.

The SVG and the PDF page are the same frame: (x - viewBox.x) / viewBox.width is the page fraction
(review-6, checked on 11 sheets), which `fraction` gives.
"""

import math
import re
from dataclasses import dataclass
from xml.etree import ElementTree

from app.core.errors import InvalidInputError

Point = tuple[float, float]

SVG = "{http://www.w3.org/2000/svg}"
NUMBER = re.compile(r"-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
COMMAND = re.compile(r"([MLA])([^MLAZ]*)")
CIRCLE_CORNERS = 16


@dataclass(frozen=True)
class Group:
    """The shape drawn for one object."""

    ifc_class: str  # e.g. IfcWallStandardCase
    name: str | None  # data-name: an element's name, a space's number
    rings: tuple[tuple[Point, ...], ...]  # one per sub-path, in SVG units

    @property
    def points(self) -> tuple[Point, ...]:
        return tuple(point for ring in self.rings for point in ring)


@dataclass(frozen=True)
class Text:
    at: Point  # its anchor, in SVG units
    text: str


@dataclass(frozen=True)
class SheetSvg:
    view_box: tuple[float, float, float, float]  # x, y, width, height
    groups: dict[str, Group]  # by GlobalId, in drawing order
    texts: tuple[Text, ...]

    def fraction(self, point: Point) -> Point:
        """An SVG point as fractions of the sheet."""
        x, y, width, height = self.view_box
        return (point[0] - x) / width, (point[1] - y) / height


def read_svg(data: bytes) -> SheetSvg:
    try:
        root = ElementTree.fromstring(data)
        numbers = [float(value) for value in root.attrib["viewBox"].split()]
    except (ElementTree.ParseError, KeyError, ValueError) as error:
        raise InvalidInputError(f"not an SVG with a viewBox: {error}") from error
    if len(numbers) != 4 or numbers[2] <= 0 or numbers[3] <= 0:
        raise InvalidInputError(f"SVG viewBox {numbers} is not x, y, width, height")
    groups: dict[str, Group] = {}
    for group in root.iter(f"{SVG}g"):
        classes = [name for name in group.get("class", "").split() if name.startswith("Ifc")]
        guid = group.get("data-guid")
        rings = _rings(group)
        if classes and guid and rings:
            groups[guid] = Group(ifc_class=classes[0], name=group.get("data-name"), rings=rings)
    texts = tuple(
        Text(at=(float(text.get("x", 0)), float(text.get("y", 0))), text=content)
        for text in root.iter(f"{SVG}text")
        if (content := "".join(text.itertext()).strip())
    )
    return SheetSvg(
        view_box=(numbers[0], numbers[1], numbers[2], numbers[3]), groups=groups, texts=texts
    )


def _rings(group: ElementTree.Element) -> tuple[tuple[Point, ...], ...]:
    rings: list[tuple[Point, ...]] = []
    for path in group.iter(f"{SVG}path"):
        for sub_path in re.split(r"(?=M)", path.get("d", "")):
            points: list[Point] = []
            for command, arguments in COMMAND.findall(sub_path):
                values = [float(number) for number in NUMBER.findall(arguments)]
                if command == "A":  # an arc: only its end point, the last two numbers
                    values = values[-2:]
                points += zip(values[0::2], values[1::2], strict=False)
            if len(points) >= 2:
                rings.append(tuple(points))
    for circle in group.iter(f"{SVG}circle"):
        cx, cy, r = (float(circle.get(name, 0)) for name in ("cx", "cy", "r"))
        rings.append(
            tuple(
                (
                    cx + r * math.cos(corner * 2 * math.pi / CIRCLE_CORNERS),
                    cy + r * math.sin(corner * 2 * math.pi / CIRCLE_CORNERS),
                )
                for corner in range(CIRCLE_CORNERS)
            )
        )
    return tuple(rings)

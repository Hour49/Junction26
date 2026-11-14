"""The stored services model: the pipes, ducts, cables and terminals of one source file, as one
document every count, length and graph answer is computed from, so an edited copy is recounted
the same way (docs/specs/backend/services-model.md section 1, decision 0017).

Lengths in metres, model coordinates, z up. Ids: `E<n>` elements, `E<n>.p<k>` ports, `L<n>`
storeys (lowest first), `SR<n>` rooms, `SW<n>` walls, `SO<n>` openings, `N<n>` elements a
proposal adds. Page fractions are not stored: a storey's `frame_m` fixes them (`fraction`).
"""

from typing import Literal

from pydantic import ConfigDict, Field

from app.core.drawing.model import Box
from app.core.ifc_facts import Discipline
from app.core.model import Frozen

Point2 = tuple[float, float]
Point3 = tuple[float, float, float]
# A model point; a picture's plan point has no height.
Point = Point3 | Point2
ConnectivityState = Literal["connected", "partial", "none"]
ConnectionState = Literal["stated", "proposed", "unknown"]
Flow = Literal["source", "sink", "both"]


class IfcRef(Frozen):
    guid: str


class PictureRef(Frozen):
    page: int
    box: Box  # page fractions
    reader: str  # "vlm", "template", "paths", "mask"


class Source(Frozen):
    model_config = ConfigDict(
        frozen=True, extra="forbid", serialize_by_alias=True, validate_by_name=True
    )

    kind: Literal["ifc", "picture"]
    sha256: str
    # "schema" in the stored JSON; the attribute name would shadow pydantic's own
    ifc_schema: str | None = Field(default=None, alias="schema")
    architecture_sha256: str | None = None  # the model rooms and walls came from


class Connectivity(Frozen):
    state: ConnectivityState
    reason: str | None = None  # what is loose ("12 distribution boards have no connected port")


class Storey(Frozen):
    id: str
    name: str
    elevation_m: float
    frame_m: tuple[float, float, float, float]  # x0, y0, x1, y1: elements and rooms + 2 m


class Port(Frozen):
    id: str
    at: Point3 | None = None
    flow: Flow | None = None  # None: the file does not say


class Element(Frozen):
    id: str
    ref: IfcRef | PictureRef
    kind: str  # "space_heater", "pipe_segment", ... (facts_mep's kinds)
    group: str  # the generic class: "flow_terminal", "flow_segment", ...
    type: str  # the type name answers count by
    category: str | None = None
    label: str
    typed: bool = False
    predefined: str | None = None
    systems: tuple[str, ...] = ()
    system_type: str | None = None
    discipline: Discipline
    storey: str | None = None  # a storey id
    room: str | None = None  # a room id
    size: str | None = None
    length_m: float | None = None  # segments
    at: Point | None = None  # the placement; a picture without a scale has none
    body_m: Point3 | None = None  # long side, short side, height
    path: tuple[Point, ...] | None = None  # segments: the polyline through its ports
    ports: tuple[Port, ...] = ()
    # What the fact sheet reads besides (derive.facts equals facts_mep.mep_facts with them):
    name: str | None = None  # the element's own Name
    space: str | None = None  # the IfcSpace of the services file it is in, by Name
    length_source: str | None = None  # how `length_m` was read ("Qto_...Length", "geometry")
    classes: dict[str, str] = Field(default_factory=dict)  # {"material": "pvc", ...}
    circuit: str | None = None  # a device's panel and circuit, "<panel>/<circuit>", when stated


class SystemInfo(Frozen):
    """An IfcSystem of the file (zones left out)."""

    name: str
    type: str  # its ObjectType, else its PredefinedType, else its class
    element_count: int  # its members, ports left out


class Connection(Frozen):
    a: str  # port ids
    b: str
    state: ConnectionState = "stated"


class Room(Frozen):
    id: str
    ref: IfcRef
    name: str
    storey: str
    polygon: tuple[Point2, ...]


class Wall(Frozen):
    id: str
    ref: IfcRef
    storey: str
    polygon: tuple[Point2, ...]
    rooms: tuple[str, ...] = ()  # the rooms it bounds


class Opening(Frozen):
    id: str
    ref: IfcRef
    kind: Literal["door", "window"]
    storey: str | None = None
    wall: str | None = None  # the wall it is in, when the file says
    segment: tuple[Point2, Point2]  # across the wall's length, from jamb to jamb
    sill_m: float  # above the storey
    head_m: float


class ServicesModel(Frozen):
    version: Literal[1] = 1
    source: Source
    connectivity: Connectivity
    storeys: tuple[Storey, ...] = ()
    elements: tuple[Element, ...] = ()
    connections: tuple[Connection, ...] = ()
    systems: tuple[SystemInfo, ...] = ()
    rooms: tuple[Room, ...] = ()
    walls: tuple[Wall, ...] = ()
    openings: tuple[Opening, ...] = ()


def fraction(storey: Storey, point: Point) -> Point2:
    """A model point as fractions of the storey's picture, top left origin (SV-6)."""
    x0, y0, x1, y1 = storey.frame_m
    return ((point[0] - x0) / (x1 - x0), (y1 - point[1]) / (y1 - y0))

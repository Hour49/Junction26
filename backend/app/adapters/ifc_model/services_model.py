"""The services model of an IFC file (app/core/services/model.py), built once and stored
(docs/specs/backend/services-model.md section 1).

- Elements are facts_mep's (`mep_elements`), so a count from the model equals the fact sheet's.
  `at` is the element's placement, `body_m` the plan rectangle and height of a terminal's or a
  piece of equipment's body, `path` a segment's polyline through its ports: from its farthest
  pair of ports, inflow first when the file says, the other ports in between.
- Ports in file order; flow from FlowDirection. Connections from IfcRelConnectsPorts, ports to
  elements through ifcopenshell.util.system (IfcRelNests in IFC4, IfcRelConnectsPortToElement in
  IFC2X3).
- Connectivity (SV-4): `none` without port connections; `connected` when every system with
  equipment has its equipment and terminals in one piece; else `partial`, saying what is loose.
- Rooms, walls and openings come from the building model when it lines up with the services
  model (the bench renderer's rule: a storey at the same elevation within 0.05 m and the plans'
  boxes overlapping by half). Spaces are found through aggregation as well as containment;
  walls are those the 1.2 m cut meets.
- Element ids from an append-only map (GlobalId -> `E<n>`): new elements get the next numbers in
  GlobalId order, so a rebuild gives the same bytes and a re-export keeps every old id.
"""

import hashlib
import math
from collections import Counter, defaultdict
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element
import ifcopenshell.util.placement
import ifcopenshell.util.system
import numpy as np
from shapely.geometry import Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from app.adapters.ifc_model.facts_mep import (
    SOURCES,
    MepElement,
    _members,
    _system_type,
    mep_elements,
)
from app.adapters.ifc_model.objects import _unit_scales
from app.core.services.stored import (
    Connection,
    Connectivity,
    Element,
    IfcRef,
    Opening,
    Point2,
    Point3,
    Port,
    Room,
    ServicesModel,
    Source,
    Storey,
    SystemInfo,
    Wall,
)

FLOW = {"SOURCE": "source", "SINK": "sink", "SOURCEANDSINK": "both"}
SAME_ELEVATION_M = 0.05
OVERLAP = 0.5  # of the services plan's box that the building's must cover
CUT_M = 1.2  # walls the cut this high above the storey meets
ROOM_SNAP_M = 0.35  # an element this close outside a room (in its wall) is in it
FRAME_MARGIN_M = 2.0
FRAME_FAR_M = 50.0  # elements further outside the storey's rooms are left out of its frame
BODIED = ("flow_terminal", *SOURCES)  # groups whose body is stored


def build_services_model(
    services: Path, ids: Mapping[str, str], architecture: Path | None = None
) -> tuple[ServicesModel, dict[str, str]]:
    """The model of `services` (and the rooms of `architecture` when it lines up), and the id
    map with this file's new elements added. Raises what ifcopenshell raises on a bad file."""
    model = _open(services)
    scale = _unit_scales(model)["LENGTHUNIT"]
    found = mep_elements(model)
    ids = _assign(ids, [e.guid for e in found])
    storeys = sorted(
        (s for s in model.by_type("IfcBuildingStorey") if s.Name),
        key=lambda s: (_elevation(s, scale), s.GlobalId),
    )
    storey_id = {s.Name: f"L{i}" for i, s in enumerate(storeys, 1)}
    elevations = {storey_id[s.Name]: round(_elevation(s, scale), 4) for s in storeys}
    port_id: dict[int, str] = {}
    elements = []
    bodies = _bodies(model, [model.by_guid(e.guid) for e in found if e.group in BODIED])
    for e in found:  # file order, as facts_mep: derived facts come out in the same order
        entity = model.by_guid(e.guid)
        ports = []
        for k, port in enumerate(ifcopenshell.util.system.get_ports(entity), 1):
            port_id[port.id()] = f"{ids[e.guid]}.p{k}"
            ports.append(
                Port(
                    id=port_id[port.id()],
                    at=_at(port, scale),
                    flow=FLOW.get(getattr(port, "FlowDirection", None) or ""),  # type: ignore[arg-type]
                )
            )
        elements.append(_element(e, ids[e.guid], entity, scale, ports, storey_id, bodies))
    connections = tuple(
        Connection(a=port_id[rel.RelatingPort.id()], b=port_id[rel.RelatedPort.id()])
        for rel in model.by_type("IfcRelConnectsPorts")
        if rel.RelatingPort.id() in port_id and rel.RelatedPort.id() in port_id
    )
    rooms: list[Room] = []
    walls: list[Wall] = []
    openings: list[Opening] = []
    if architecture is not None:
        rooms, walls, openings = _building(architecture, elevations, elements)
    elements = _in_rooms(elements, rooms)
    built = ServicesModel(
        source=Source.model_validate(
            {
                "kind": "ifc",
                "sha256": _sha256(services),
                "schema": model.schema,
                "architecture_sha256": _sha256(architecture) if rooms else None,
            }
        ),
        connectivity=_connectivity(elements, connections),
        storeys=tuple(
            Storey(
                id=storey_id[s.Name],
                name=s.Name,
                elevation_m=elevations[storey_id[s.Name]],
                frame_m=_frame(storey_id[s.Name], elements, rooms),
            )
            for s in storeys
        ),
        elements=tuple(elements),
        connections=connections,
        systems=_systems(model),
        rooms=tuple(rooms),
        walls=tuple(walls),
        openings=tuple(openings),
    )
    return built, ids


def _open(path: Path) -> Any:
    opened: Any = ifcopenshell.open  # lazy: a fraction of the memory on a large model (objects.py)
    return opened(str(path), lazy=True)


def _sha256(path: Path | None) -> str | None:
    return None if path is None else hashlib.sha256(path.read_bytes()).hexdigest()


def _assign(ids: Mapping[str, str], guids: list[str]) -> dict[str, str]:
    """Known GlobalIds keep their id; new ones get the next numbers, in GlobalId order."""
    known = dict(ids)
    n = max((int(i[1:]) for i in known.values()), default=0)
    for guid in sorted(set(guids) - set(known)):
        n += 1
        known[guid] = f"E{n}"
    return known


def _elevation(storey: Any, scale: float) -> float:
    return float(storey.Elevation or 0.0) * scale


def _at(entity: Any, scale: float) -> Point3 | None:
    if getattr(entity, "ObjectPlacement", None) is None:
        return None
    matrix = ifcopenshell.util.placement.get_local_placement(entity.ObjectPlacement)
    x, y, z = (round(float(v) * scale, 4) for v in matrix[:3, 3])
    return (x, y, z)


def _element(
    e: MepElement,
    eid: str,
    entity: Any,
    scale: float,
    ports: list[Port],
    storey_id: Mapping[str, str],
    bodies: Mapping[str, Point3],
) -> Element:
    return Element(
        id=eid,
        ref=IfcRef(guid=e.guid),
        kind=e.kind,
        group=e.group,
        type=e.type_name,
        category=e.category,
        label=e.type_name,
        typed=e.typed,
        predefined=e.predefined,
        systems=e.systems,
        system_type=e.system_type,
        discipline=e.discipline,
        storey=storey_id.get(e.storey or ""),
        size=e.size,
        length_m=e.length_m,  # unrounded: the fact sheet rounds the sums
        at=_at(entity, scale),
        body_m=bodies.get(e.guid),
        path=_path(ports) if e.length_m is not None else None,
        ports=tuple(ports),
        name=e.name,
        space=e.space,
        length_source=e.length_source,
        classes=dict(e.classes),
        circuit=_circuit(entity),  # any device that states one: a boiler or pump too
    )


def _circuit(entity: Any) -> str | None:
    """ "<panel>/<circuit>" as a Revit export states it in a property set."""
    said: dict[str, str] = {}
    for props in ifcopenshell.util.element.get_psets(entity).values():
        for key in ("Panel", "Circuit Number"):
            value = props.get(key)
            if isinstance(value, str | int) and str(value).strip() and str(value) != key:
                said.setdefault(key, str(value))
    if "Panel" not in said:
        return None
    return "/".join(v for v in (said["Panel"], said.get("Circuit Number")) if v)


def _systems(model: Any) -> tuple[SystemInfo, ...]:
    return tuple(
        SystemInfo(
            name=system.Name or "",
            type=_system_type(system),
            element_count=len(_members(system)),
        )
        for system in model.by_type("IfcSystem")
        if not system.is_a("IfcZone")
    )


def _path(ports: list[Port]) -> tuple[Point3, ...] | None:
    placed = [(p, p.at) for p in ports if p.at is not None]
    if len(placed) < 2:
        return None
    (a, start), (b, end) = max(
        ((pa, pb) for i, pa in enumerate(placed) for pb in placed[i + 1 :]),
        key=lambda pair: math.dist(pair[0][1], pair[1][1]),
    )
    if a.flow == "source" and b.flow == "sink":  # the water comes in at the sink port
        start, end = end, start
    axis = np.subtract(end, start)
    along = sorted(placed, key=lambda pa: float(np.dot(np.subtract(pa[1], start), axis)))
    return tuple(at for _, at in along)


def _shapes(model: Any, entities: list[Any]) -> Iterator[tuple[str, np.ndarray, np.ndarray]]:
    """(GlobalId, world vertices in metres (n, 3), triangles (m, 3)) per entity the kernel
    builds."""
    if not entities:
        return
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    settings.set("disable-opening-subtractions", True)
    iterator = ifcopenshell.geom.iterator(settings, model, 1, include=entities)
    if not iterator.initialize():
        return
    while True:
        shape: Any = iterator.get()
        verts = np.asarray(shape.geometry.verts, dtype=float).reshape(-1, 3)
        if len(verts):
            yield shape.guid, verts, np.asarray(shape.geometry.faces, dtype=int).reshape(-1, 3)
        if not iterator.next():
            return


def _footprint(verts: np.ndarray, faces: np.ndarray) -> BaseGeometry | None:
    triangles = [Polygon(t) for t in verts[:, :2][faces]]
    shape = unary_union([t for t in triangles if t.area > 1e-6]).buffer(0)
    return None if shape.is_empty else shape


def _rectangle(shape: BaseGeometry) -> list[tuple[float, float]]:
    return list(shape.minimum_rotated_rectangle.exterior.coords)[:4]  # type: ignore[attr-defined]


def _bodies(model: Any, entities: list[Any]) -> dict[str, Point3]:
    """Per entity: its plan rectangle's long and short side and its height."""
    found = {}
    for guid, verts, faces in _shapes(model, entities):
        shape = _footprint(verts, faces)
        if shape is None:
            continue
        c = _rectangle(shape)
        sides = sorted((math.dist(c[0], c[1]), math.dist(c[1], c[2])), reverse=True)
        height = float(np.ptp(verts[:, 2]))
        found[guid] = (round(sides[0], 3), round(sides[1], 3), round(height, 3))
    return found


def _container(entity: Any) -> Any:
    """The storey an architectural element is in: contained, or aggregated (an IfcSpace)."""
    whole = ifcopenshell.util.element.get_container(entity)
    if whole is None:
        whole = ifcopenshell.util.element.get_aggregate(entity)
    return whole if whole is not None and whole.is_a("IfcBuildingStorey") else None


def _building(
    path: Path, elevations: Mapping[str, float], elements: list[Element]
) -> tuple[list[Room], list[Wall], list[Opening]]:
    """Rooms, walls and openings of the building model, when it lines up with the services."""
    model = _open(path)
    scale = _unit_scales(model)["LENGTHUNIT"]

    def ours(entity: Any) -> tuple[str, float] | None:  # (services storey id, its elevation)
        storey = _container(entity)
        if storey is None:
            return None
        z = _elevation(storey, scale)
        return next(
            ((sid, e) for sid, e in elevations.items() if abs(e - z) <= SAME_ELEVATION_M), None
        )

    spaces = sorted(model.by_type("IfcSpace"), key=lambda s: s.GlobalId)
    shapes = {g: _footprint(v, f) for g, v, f in _shapes(model, spaces)}
    rooms = []
    for space in spaces:
        where, shape = ours(space), shapes.get(space.GlobalId)
        if where is None or shape is None:
            continue
        name = " ".join(t for t in (space.Name, getattr(space, "LongName", None)) if t)
        rooms.append((where, space.GlobalId, name, _polygon(shape)))
    cut = []
    by_wall = sorted(model.by_type("IfcWall"), key=lambda w: w.GlobalId)
    for guid, verts, faces in _shapes(model, by_wall):
        where = ours(model.by_guid(guid))
        if where is None or not verts[:, 2].min() <= where[1] + CUT_M <= verts[:, 2].max():
            continue
        shape = _footprint(verts, faces)
        if shape is not None:
            cut.append((where[0], guid, _polygon(shape)))
    if not _lines_up(elements, [p for *_, poly in rooms for p in poly] + [
        p for *_, poly in cut for p in poly
    ]):  # fmt: skip
        return [], [], []
    room_list = [
        Room(id=f"SR{i}", ref=IfcRef(guid=guid), name=name, storey=sid, polygon=polygon)
        for i, ((sid, _), guid, name, polygon) in enumerate(
            sorted(rooms, key=lambda r: (r[0][1], r[1])), 1
        )
    ]
    shapes_of = [(r, Polygon(r.polygon)) for r in room_list]
    walls = []
    for i, (sid, guid, polygon) in enumerate(sorted(cut, key=lambda w: (w[0], w[1])), 1):
        near = Polygon(polygon).buffer(0.05)
        bounds = tuple(r.id for r, p in shapes_of if r.storey == sid and near.intersects(p))
        walls.append(
            Wall(id=f"SW{i}", ref=IfcRef(guid=guid), storey=sid, polygon=polygon, rooms=bounds)
        )
    return room_list, walls, _openings(model, scale, walls, ours)


def _polygon(shape: BaseGeometry) -> tuple[Point2, ...]:
    shape = shape.simplify(0.01)
    if shape.geom_type == "MultiPolygon":
        # shortcut: keeps the largest part only; a room in two pieces needs a multipolygon
        shape = max(shape.geoms, key=lambda p: p.area)  # type: ignore[attr-defined]
    coords = list(shape.exterior.coords)[:-1]  # type: ignore[attr-defined]
    return tuple((round(x, 3), round(y, 3)) for x, y in coords)


def _lines_up(elements: list[Element], building: list[Point2]) -> bool:
    """The services plan's box (padded 0.5 m) is at least half inside the building's."""
    mine = [e.at[:2] for e in elements if e.at is not None]
    if not mine or not building:
        return False
    (ax0, ay0), (ax1, ay1) = np.min(mine, axis=0) - 0.5, np.max(mine, axis=0) + 0.5
    (bx0, by0), (bx1, by1) = np.min(building, axis=0), np.max(building, axis=0)
    width, height = min(ax1, bx1) - max(ax0, bx0), min(ay1, by1) - max(ay0, by0)
    return width > 0 and height > 0 and width * height >= OVERLAP * (ax1 - ax0) * (ay1 - ay0)


def _openings(model: Any, scale: float, walls: list[Wall], ours: Any) -> list[Opening]:
    wall_id = {w.ref.guid: w.id for w in walls}
    entities = sorted([*model.by_type("IfcDoor"), *model.by_type("IfcWindow")],
                      key=lambda e: e.GlobalId)  # fmt: skip
    found = []
    for guid, verts, faces in _shapes(model, entities):
        entity = model.by_guid(guid)
        where, shape = ours(entity), _footprint(verts, faces)
        if where is None or shape is None:
            continue
        c = _rectangle(shape)
        mids = [((c[i][0] + c[(i + 1) % 4][0]) / 2, (c[i][1] + c[(i + 1) % 4][1]) / 2)
                for i in range(4)]  # fmt: skip
        short = 0 if math.dist(c[0], c[1]) < math.dist(c[1], c[2]) else 1
        a, b = mids[short], mids[short + 2]  # the middles of the short sides: jamb to jamb
        host = next(
            (
                v.RelatingBuildingElement.GlobalId
                for fill in getattr(entity, "FillsVoids", None) or ()
                for v in fill.RelatingOpeningElement.VoidsElements
            ),
            None,
        )
        found.append(
            Opening(
                id=f"SO{len(found) + 1}",
                ref=IfcRef(guid=guid),
                kind="door" if entity.is_a("IfcDoor") else "window",
                storey=where[0],
                wall=wall_id.get(host or ""),
                segment=((round(a[0], 3), round(a[1], 3)), (round(b[0], 3), round(b[1], 3))),
                sill_m=round(float(verts[:, 2].min()) - where[1], 3),
                head_m=round(float(verts[:, 2].max()) - where[1], 3),
            )
        )
    return found


def _in_rooms(elements: list[Element], rooms: list[Room]) -> list[Element]:
    shapes: dict[str, list[tuple[str, Polygon]]] = defaultdict(list)
    for room in rooms:
        shapes[room.storey].append((room.id, Polygon(room.polygon)))
    placed = []
    for e in elements:
        points = e.path or ((e.at,) if e.at is not None else ())
        if not points or e.storey not in shapes:
            placed.append(e)
            continue
        middle = Point(np.mean([p[:2] for p in points], axis=0))
        distance, room = min((p.distance(middle), rid) for rid, p in shapes[e.storey])
        placed.append(e.model_copy(update={"room": room}) if distance <= ROOM_SNAP_M else e)
    return placed


def _frame(
    storey: str, elements: list[Element], rooms: list[Room]
) -> tuple[float, float, float, float]:
    points = [p[:2] for e in elements if e.storey == storey for p in (e.path or (e.at,)) if p]
    walls = [p for r in rooms if r.storey == storey for p in r.polygon]
    if walls:  # a stray element far off would stretch the picture to nothing (SV-29)
        (ax, ay), (bx, by) = np.min(walls, axis=0), np.max(walls, axis=0)
        f = FRAME_FAR_M
        points = [p for p in points if ax - f <= p[0] <= bx + f and ay - f <= p[1] <= by + f]
    points += walls
    if not points:
        return (-FRAME_MARGIN_M, -FRAME_MARGIN_M, FRAME_MARGIN_M, FRAME_MARGIN_M)
    (x0, y0), (x1, y1) = np.min(points, axis=0), np.max(points, axis=0)
    m = FRAME_MARGIN_M
    return (round(x0 - m, 3), round(y0 - m, 3), round(x1 + m, 3), round(y1 + m, 3))


def _connectivity(elements: list[Element], connections: tuple[Connection, ...]) -> Connectivity:
    if not connections:
        return Connectivity(state="none", reason="the file states no port connections")
    owner = {p.id: e.id for e in elements for p in e.ports}
    parent = {e.id: e.id for e in elements}

    def root(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for c in connections:
        parent[root(owner[c.a])] = root(owner[c.b])
    by_system: dict[str, list[Element]] = defaultdict(list)
    for e in elements:
        for system in e.systems:
            by_system[system].append(e)
    loose: Counter[str] = Counter()
    systems_with_equipment = 0
    for members in by_system.values():
        equipment = [e for e in members if _is_equipment(e)]
        if not equipment:
            continue
        systems_with_equipment += 1
        main = root(equipment[0].id)
        for e in members:
            if (_is_equipment(e) or _is_terminal(e)) and root(e.id) != main:
                loose[e.kind.replace("_", " ")] += 1
    if not systems_with_equipment:
        return Connectivity(
            state="partial",
            reason="no system has its equipment (a boiler, pump, fan or board) in this model",
        )
    if loose:
        said = ", ".join(f"{n} {kind}{'s' if n > 1 else ''}" for kind, n in loose.most_common())
        return Connectivity(state="partial", reason=f"not connected to their system's equipment: "
                            f"{said}")  # fmt: skip
    return Connectivity(state="connected")


def _is_equipment(e: Element) -> bool:
    return e.group in SOURCES or e.kind.startswith("electric_distribution")


def _is_terminal(e: Element) -> bool:
    return e.group == "flow_terminal"

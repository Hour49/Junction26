"""SV-13..SV-21: edits of the stored services model, pure. Each operation takes a model and ids,
works on a copy and returns a `ServicesChange` (the patch, what moved, was removed and added in
page fractions, the facts before and after, the checks, flags and unknowns) or raises
`EditRefusedError` with a plain reason (SV-19). The input model is never changed; `apply` replays
a patch, so a chat's model is its source plus the accepted patches in order (SV-13).

The geometry of the reroute rule (SV-18) is route.py; here the model becomes its shapes and the
routed runs become elements: segments of the old branch's type and size, joined by elbows when
the old branch had one, with new ports and `proposed` connections. A main is tapped by giving it
one more port (a tapped segment, SV-1), not by cutting it, so the facts of the main do not move.
New elements get the next free `N<n>` id and an empty guid (nothing in the file is theirs).
"""

import math
from collections import Counter, deque
from collections.abc import Iterable, Sequence
from itertools import pairwise
from typing import Any, Literal

from pydantic import ConfigDict, Field
from shapely.geometry import LineString, Polygon
from shapely.geometry import Point as Spot

from app.core.model import Frozen
from app.core.plan_edit.model import Flag
from app.core.services.ops import ServicesGraph, unconnected
from app.core.services.route import (
    CLEAR_M,
    Edge,
    Leg,
    Main,
    Opening,
    Routed,
    blocked_spans,
    door_zones,
    place,
    reroute,
    room_edges,
)
from app.core.services.stored import (
    Connection,
    Element,
    Point2,
    Point3,
    Room,
    ServicesModel,
    Storey,
    fraction,
)

NOT_TERMINAL = "This is not a terminal."
NO_ROOM = "This element is in no room of the model."
SAME_WALL = "It is already on that wall."
TOO_SHORT = "This wall is too short for it."
NO_FREE = "No free place on this wall: a door or another terminal is in the way."
TAKEN = "Another terminal is already there."
DOORS = "Both ways round this room pass a door."
NO_RUN = "No {run} of this circuit in or next to this room."
NO_JUNCTION = "Its branch does not end at a junction: a valve or equipment is in the way."
CROSS = "Supply and return would cross."
NOT_ITS_WALL = "This wall is not a wall of its room."
NO_SIZE = "No element of this system has that size."

NOT_SIZED = "Sizes are copied from the old branch. Flow, pressure and clashes with other services are not checked."  # noqa: E501
UNKNOWN_CLASH = "Whether the new run clashes with other services: not checked."

LONG_K, LONG_PLUS_M = 3.0, 2.0  # long_reroute: added > 3 x removed + 2 m (SV-20)
MAIN_DZ_M = 0.3  # a main is tapped at the old height +- this
DEFAULT_OFFSET_M, DEFAULT_PAIR_M = 0.05, 0.06
WALL_COVER_M = 0.3  # a wall is on a room edge when it covers this much of it
RUN_GROUPS = ("flow_segment", "flow_fitting")
WET_WORDS = ("bath", "wc", "toilet", "shower", "sauna", "kylpy", "pesu", "bad", "dusch", "wasch")
_WET = Flag(code="wet_room", text="A wet room changes: its waterproofing is redone and inspected.")

Position = Literal["centre", "start", "end", "under_window"] | Point2
Op = Literal["move_terminal", "remove_element", "add_terminal", "resize"]


class EditRefusedError(Exception):
    """The edit the rule cannot make; its text is the plain reason the person reads (SV-19)."""


class Patch(Frozen):
    """An edit as data (SV-13): elements as they are after (`moved`, `changed`) or new (`added`),
    ids that go (`removed`), and the connections that go or come."""

    moved: tuple[Element, ...] = ()
    removed: tuple[str, ...] = ()
    added: tuple[Element, ...] = ()
    connections_removed: tuple[Connection, ...] = ()
    connections_added: tuple[Connection, ...] = ()
    changed: tuple[Element, ...] = ()


def apply(model: ServicesModel, patch: Patch) -> ServicesModel:
    """The model with the patch applied; the model itself is not changed (SV-13)."""
    replaced = {e.id: e for e in (*patch.moved, *patch.changed)}
    gone = set(patch.removed)
    elements = tuple(replaced.get(e.id, e) for e in model.elements if e.id not in gone)
    dropped = {frozenset((c.a, c.b)) for c in patch.connections_removed}
    kept = tuple(c for c in model.connections if frozenset((c.a, c.b)) not in dropped)
    return model.model_copy(
        update={
            "elements": elements + patch.added,
            "connections": kept + patch.connections_added,
        }
    )


class Moved(Frozen):
    model_config = ConfigDict(
        frozen=True, extra="forbid", serialize_by_alias=True, validate_by_name=True
    )

    id: str
    label: str
    from_: Point2 | None = Field(default=None, alias="from")  # page fractions (SV-6)
    to: Point2 | None = None
    to_m: Point3 | None = None  # the new place in model metres


class RunChange(Frozen):
    id: str
    polyline: tuple[Point2, ...]  # page fractions; one point for an element with no path
    label: str
    system: str | None = None


class FactChange(Frozen):
    what: str  # "pipe length", "space_heater count", ...
    system: str | None = None
    size: str | None = None
    unit: str
    before: float
    after: float


class Check(Frozen):
    code: str
    ok: bool
    text: str


class ServicesChange(Frozen):
    """What one edit proposes (SV-28's `services`); the adapter adds `picture` and `based_on`."""

    op: Op
    storey: str | None
    moved: tuple[Moved, ...] = ()
    removed: tuple[RunChange, ...] = ()
    added: tuple[RunChange, ...] = ()
    facts: tuple[FactChange, ...] = ()
    checks: tuple[Check, ...] = ()
    flags: tuple[Flag, ...] = ()
    unknowns: tuple[str, ...] = ()
    patch: Patch
    based_on: tuple[str, ...] = ()
    picture: str | None = None


# --- operations ---------------------------------------------------------------------------------


def move_terminal(
    model: ServicesModel, element_id: str, wall_id: str, position: Position = "centre"
) -> ServicesChange:
    """SV-14: the terminal onto that wall of its own room, at its old distance from the wall and
    its old height, turned to the wall; its branches rerouted by SV-18."""
    work = _Work(model)
    term = work.terminal(element_id)
    room = _room_of(model, term)
    storey = _storey(model, term)
    _put(work, model, term, room, room, wall_id, position)
    flags = _reroute(work, term, room, storey, model, None)
    flags.append(Flag(code="not_sized", text=NOT_SIZED))
    if _wet(room):
        flags.append(_WET)
    return _change(work, "move_terminal", term, flags, (UNKNOWN_CLASH,), "reroute")


def add_terminal(
    model: ServicesModel,
    like_element_id: str,
    wall_id: str,
    position: Position = "centre",
    room_id: str | None = None,
) -> ServicesChange:
    """SV-16: a copy of that terminal's type on the wall (of `room_id`, else of the like
    element's room, else of the wall's only room), at the like element's distance from its wall
    and height above its storey, connected by the reroute rule to the nearest mains of the same
    system types."""
    work = _Work(model)
    like = work.terminal(like_element_id)
    like_room = _room_of(model, like)
    wall = next((w for w in model.walls if w.id == wall_id), None)
    if room_id is None and wall is not None:
        rooms = wall.rooms if like_room.id not in wall.rooms else (like_room.id,)
        room_id = rooms[0] if len(rooms) == 1 else None
    room = next((r for r in model.rooms if r.id == room_id), None)
    if room is None:
        raise EditRefusedError(NOT_ITS_WALL)
    like_storey, storey = _storey(model, like), _storey(model, {"storey": room.storey})
    probe = _Work(model)  # the like element's branches, read without touching `work`
    polygon = Polygon(like_room.polygon)
    branches = [_Branch(probe, p["id"], polygon) for p in _supply_first(like["ports"])]
    nid = work.new_id()
    term: dict[str, Any] = {
        **like,
        "id": nid,
        "ref": {"guid": ""},
        "label": f"{like['type']} (new)",
        "room": room.id,
        "storey": room.storey,
        "ports": [
            {**p, "id": f"{nid}.p{k}"} for k, p in enumerate(_supply_first(like["ports"]), 1)
        ],
    }
    work.el[nid] = term
    _put(work, model, term, like_room, room, wall_id, position)
    dz = storey.elevation_m - like_storey.elevation_m
    term["at"] = (term["at"][0], term["at"][1], term["at"][2] + dz)
    term["ports"] = [{**p, "at": (p["at"][0], p["at"][1], p["at"][2] + dz)} for p in term["ports"]]
    for branch in branches:
        x, y, z = branch.junction_at
        branch.junction_at, branch.junction_xy = (x, y, z + dz), None  # no old junction here
    work.removed_m = probe.removed_m  # long_reroute compares with the like element's branches
    taken = {i for b in branches for i in b.chain}
    flags = _reroute(work, term, room, storey, model, (branches, taken))
    flags.append(Flag(code="not_sized", text=NOT_SIZED))
    if _wet(room):
        flags.append(_WET)
    return _change(work, "add_terminal", term, flags, (UNKNOWN_CLASH,), "reroute")


def _put(
    work: "_Work",
    model: ServicesModel,
    term: dict[str, Any],
    from_room: Room,
    room: Room,
    wall_id: str,
    position: Position,
) -> None:
    """SV-18 step 1: the terminal onto the wall's edge of `room`, at its distance from its wall in
    `from_room` and its height, turned to the wall; refused when there is no place."""
    from_edges, edges = room_edges(from_room.polygon), room_edges(room.polygon)
    old_xy, _ = _centre(term)
    old = min(range(len(from_edges)), key=lambda i: from_edges[i].line.distance(Spot(old_xy)))
    target = _edge_of_wall(model, wall_id, room, edges)
    if from_room is room and target == old:
        raise EditRefusedError(SAME_WALL)
    edge, distance = edges[target], from_edges[old].line.distance(Spot(old_xy))
    body_len = _body_len(term)
    if edge.length < body_len + 2 * CLEAR_M:
        raise EditRefusedError(TOO_SHORT)
    top = term["at"][2] - _storey(model, {"storey": from_room.storey}).elevation_m + _height(term)
    openings = [_opening(o) for o in model.openings if o.storey in (None, room.storey)]
    others = [b for e in work.terminals(room.storey, skip=term["id"]) if (b := _body(e))]
    spans = blocked_spans(edge, openings, others, top, distance)
    k = _place(edge, body_len, spans, position, openings, top, others)
    centre = edge.point(k, distance)
    turn = math.atan2(edge.n[1], edge.n[0]) - math.atan2(from_edges[old].n[1], from_edges[old].n[0])
    dx, dy = term["at"][0] - old_xy[0], term["at"][1] - old_xy[1]  # placement off the centre
    c, s = math.cos(turn), math.sin(turn)
    work.move(term, (centre[0] + dx * c - dy * s, centre[1] + dx * s + dy * c), turn)
    body = _body(term)
    if body and any(Polygon(body).intersects(Polygon(b)) for b in others):
        raise EditRefusedError(TAKEN)


def _supply_first(ports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(ports, key=lambda p: p["flow"] != "sink")


def remove_element(model: ServicesModel, element_id: str) -> ServicesChange:
    """SV-15: a terminal goes with its branches back to their junctions, which are closed."""
    work = _Work(model)
    term = work.terminal(element_id)
    for port in term["ports"]:
        chain, junction = work.chain(port["id"])
        for eid in chain:
            work.remove(eid)
        work.close(junction)
    work.remove(element_id)
    return _change(work, "remove_element", term, [], (), "removal")


def resize(model: ServicesModel, element_id: str, size: str) -> ServicesChange:
    """SV-17: an element to a size some element of its system already has."""
    work = _Work(model)
    element = work.el.get(element_id)
    if element is None:
        raise EditRefusedError(NOT_TERMINAL)
    systems = set(element["systems"])
    sizes = {e.size for e in model.elements if systems & set(e.systems) and e.size}
    if size not in sizes:
        raise EditRefusedError(NO_SIZE)
    element["size"] = size
    flags = [Flag(code="not_sized", text="Flow and pressure are not checked.")]
    return _change(work, "resize", None, flags, (), "change")


# --- the working copy ---------------------------------------------------------------------------


def _owner(port_id: str) -> str:
    return port_id.rsplit(".", 1)[0]


class _Work:
    """A mutable copy of the model's elements and connections (dicts), with the bookkeeping."""

    def __init__(self, model: ServicesModel) -> None:
        self.model = model
        self.el: dict[str, dict[str, Any]] = {e.id: e.model_dump() for e in model.elements}
        self.peer: dict[str, str] = {}
        for c in model.connections:
            self.peer[c.a], self.peer[c.b] = c.b, c.a
        used = [int(i[1:]) for i in self.el if i.startswith("N") and i[1:].isdigit()]
        self.next = max(used, default=0) + 1
        self.removed_m = self.added_m = 0.0

    def terminal(self, element_id: str) -> dict[str, Any]:
        term = self.el.get(element_id)
        if term is None or term["group"] != "flow_terminal":
            raise EditRefusedError(NOT_TERMINAL)
        return term

    def terminals(self, storey: str | None, skip: str) -> list[dict[str, Any]]:
        return [
            e
            for e in self.el.values()
            if e["group"] == "flow_terminal" and e["storey"] == storey and e["id"] != skip
        ]

    def new_id(self) -> str:
        self.next += 1
        return f"N{self.next - 1}"

    def port(self, port_id: str) -> dict[str, Any]:
        return next(p for p in self.el[_owner(port_id)]["ports"] if p["id"] == port_id)

    def disconnect(self, port_id: str) -> None:
        other = self.peer.pop(port_id, None)
        if other is not None:
            self.peer.pop(other, None)

    def remove(self, element_id: str) -> None:
        element = self.el.pop(element_id)
        for port in element["ports"]:
            self.disconnect(port["id"])
        if element["group"] == "flow_segment":
            self.removed_m += element["length_m"] or 0.0

    def move(self, term: dict[str, Any], to: Point2, turn: float) -> None:
        """Turn the terminal by `turn` about its placement and put it at `to` (same height)."""
        at = term["at"]
        c, s = math.cos(turn), math.sin(turn)

        def moved(q: Sequence[float]) -> Point3:
            dx, dy = q[0] - at[0], q[1] - at[1]
            return (to[0] + dx * c - dy * s, to[1] + dx * s + dy * c, q[2])

        term["ports"] = [{**p, "at": moved(p["at"])} for p in term["ports"]]
        term["at"] = (to[0], to[1], at[2])

    def chain(self, port_id: str) -> tuple[list[str], str]:
        """The 2-port segments and fittings from a port back to its junction (an element with
        three or more ports), and the junction's port; refused when anything else is first."""
        out: list[str] = []
        current = port_id
        while True:
            other = self.peer.get(current)
            element = self.el.get(_owner(other)) if other else None
            if other is None or element is None or element["group"] not in RUN_GROUPS:
                raise EditRefusedError(NO_JUNCTION)
            if len(element["ports"]) >= 3:
                return out, other
            if len(element["ports"]) != 2 or element["id"] in out:
                raise EditRefusedError(NO_JUNCTION)
            out.append(element["id"])
            current = next(p["id"] for p in element["ports"] if p["id"] != other)

    def close(self, junction_port: str) -> None:
        """SV-18 step 2: a tee left with two ports becomes a straight piece between its two
        neighbours (none when they meet); a tapped segment or a manifold loses the port."""
        junction = self.el[_owner(junction_port)]
        self.disconnect(junction_port)
        rest = [self.peer.get(p["id"]) for p in junction["ports"] if p["id"] != junction_port]
        if junction["group"] == "flow_fitting" and len(rest) == 2 and all(rest):
            a, b = (r for r in rest if r)
            self.remove(junction["id"])
            ends = self.port(a)["at"], self.port(b)["at"]
            if math.dist(*ends) < 1e-3:
                _connect(self, a, b)
                return
            like = next(
                (
                    self.el[_owner(r)]
                    for r in (a, b)
                    if self.el[_owner(r)]["group"] == "flow_segment"
                ),
                None,
            )
            piece = self.segment(like or junction, ends[0], ends[1])
            _connect(self, a, piece["ports"][0]["id"])
            _connect(self, piece["ports"][1]["id"], b)
            return
        junction["ports"] = [p for p in junction["ports"] if p["id"] != junction_port]

    def segment(self, like: dict[str, Any], a: Point3, b: Point3) -> dict[str, Any]:
        """A new straight segment of `like`'s kind, type, size and systems from a to b."""
        nid = self.new_id()
        length = math.dist(a, b)
        self.added_m += length
        kind = like["kind"] if like["group"] == "flow_segment" else "pipe_segment"
        element = {
            **like,
            "id": nid,
            "ref": {"guid": ""},
            "kind": kind,
            "group": "flow_segment",
            "label": f"{like['type']} (new)",
            "length_m": length,
            "at": a,
            "path": (a, b),
            "body_m": None,
            "ports": [
                {"id": f"{nid}.p1", "at": a, "flow": None},
                {"id": f"{nid}.p2", "at": b, "flow": None},
            ],
        }
        self.el[nid] = element
        return element

    def fitting(self, like: dict[str, Any], at: Point3) -> dict[str, Any]:
        nid = self.new_id()
        element = {
            **like,
            "id": nid,
            "ref": {"guid": ""},
            "label": f"{like['type']} (new)",
            "at": at,
            "ports": [{"id": f"{nid}.p{k}", "at": at, "flow": None} for k in (1, 2)],
        }
        self.el[nid] = element
        return element

    def tap(self, main_id: str, at: Point2) -> str:
        """A new port on the main at its plan point `at`; its id."""
        main = self.el[main_id]
        (ax, ay, az), (bx, by, bz) = main["path"][0], main["path"][-1]
        span = math.dist((ax, ay), (bx, by)) or 1.0
        z = az + (bz - az) * math.dist((ax, ay), at) / span
        k = max(int(p["id"].rsplit(".p", 1)[1]) for p in main["ports"]) + 1
        port_id = f"{main_id}.p{k}"
        main["ports"] = [*main["ports"], {"id": port_id, "at": (at[0], at[1], z), "flow": None}]
        return port_id


def _connect(work: _Work, a: str, b: str) -> None:
    work.disconnect(a)
    work.disconnect(b)
    work.peer[a], work.peer[b] = b, a


# --- the reroute (SV-18) ------------------------------------------------------------------------


def _reroute(
    work: _Work,
    term: dict[str, Any],
    room: Room,
    storey: Storey,
    model: ServicesModel,
    added: tuple[list["_Branch"], set[str]] | None,
) -> list[Flag]:
    """Steps 2-6 for a moved terminal (its own branches are taken out here) or an added one
    (`added`: the like element's branches and the ids of their pieces, matched by system type)."""
    polygon = Polygon(room.polygon)
    ports = _supply_first(term["ports"])
    if added is None:
        branches, skip = [_Branch(work, p["id"], polygon) for p in ports], set[str]()
    else:
        branches, skip = added
    legs = [
        Leg(
            port=_xy(p["at"]),
            offset=b.offset,
            mains=tuple(_mains(work, b, term["storey"], skip, by_type=added is not None)),
            junction=b.junction_xy,
        )
        for p, b in zip(ports, branches, strict=True)
    ]
    run_z = branches[0].junction_at[2] - storey.elevation_m
    doors = door_zones(
        [
            _opening(o)
            for o in model.openings
            if o.kind == "door" and o.storey in (None, term["storey"]) and o.head_m > run_z
        ]
    )
    spacing = _spacing(branches) if len(branches) == 2 else DEFAULT_PAIR_M
    routed = reroute(polygon, doors, legs[0], legs[1] if len(legs) > 1 else None, spacing)
    if routed == "no_main":
        raise EditRefusedError(NO_RUN.format(run=_run_word(term)))
    if routed == "doors":
        raise EditRefusedError(DOORS)
    if routed == "cross":
        raise EditRefusedError(CROSS)
    return _build(work, room, ports, branches, routed, close=added is None)


def _build(
    work: _Work,
    room: Room,
    ports: list[dict[str, Any]],
    branches: list["_Branch"],
    routed: Routed,
    close: bool,
) -> list[Flag]:
    flags: list[Flag] = []
    for port, branch, run in zip(ports, branches, routed.runs, strict=True):
        if run.tap.main is None:
            start = branch.junction_port
            z = branch.junction_at[2]
        else:
            if close:
                work.close(branch.junction_port)
            start = work.tap(run.tap.main, run.tap.at)
            z = work.port(start)["at"][2]
        if run.tap.tier == "outside":
            flags.append(
                Flag(
                    code="through_wall",
                    text="The connection goes through a wall: it needs a core drill.",
                )
            )
        points = [work.port(start)["at"], *((x, y, z) for x, y in run.path[1:]), port["at"]]
        _emit(work, branch, room.id, _dedupe(points), start, port["id"])
    if routed.crossover_m is not None:
        flags.append(
            Flag(code="crossover", text="Supply and return cross at the terminal's connection.")
        )
    if work.added_m > LONG_K * work.removed_m + LONG_PLUS_M:
        text = f"Long reroute: {work.added_m:.2f} m of new pipe replaces {work.removed_m:.2f} m."
        flags.append(Flag(code="long_reroute", text=text))
    return flags


class _Branch:
    """One port's old branch, taken out of the working copy: where it met the network and what
    its new run copies (type, size, systems, distance from the wall)."""

    def __init__(self, work: _Work, port_id: str, room: Polygon) -> None:
        self.chain, self.junction_port = work.chain(port_id)
        chain = self.chain
        pieces = [work.el[i] for i in chain]
        x, y, z = work.port(self.junction_port)["at"]
        self.junction_at: Point3 = (x, y, z)
        self.junction_xy: Point2 | None = _xy(self.junction_at)
        junction = work.el[_owner(self.junction_port)]
        segments = [e for e in pieces if e["group"] == "flow_segment"]
        self.like = segments[0] if segments else junction
        self.elbow = next((e for e in pieces if e["group"] == "flow_fitting"), None)
        sizes: Counter[str] = Counter()  # metres per size, rounded to mm for the Counter
        for e in segments:
            sizes[e["size"] or ""] += round((e["length_m"] or 0.0) * 1000)
        self.size: str | None = sizes.most_common(1)[0][0] or None if sizes else junction["size"]
        self.systems = set(self.like["systems"])
        self.flat = [
            LineString([_xy(e["path"][0]), _xy(e["path"][-1])])
            for e in segments
            if e["path"] and abs(e["path"][0][2] - e["path"][-1][2]) < 0.01
        ]
        inside = [
            (room.exterior.distance(line.interpolate(0.5, normalized=True)), line.length)
            for line in self.flat
            if line.length > 0.02 and room.contains(line.interpolate(0.5, normalized=True))
        ]
        self.offset = _weighted_median(inside) if inside else DEFAULT_OFFSET_M
        for eid in chain:
            work.remove(eid)


def _mains(
    work: _Work, branch: _Branch, storey: str | None, skip: set[str], by_type: bool
) -> Iterable[Main]:
    """The runs the branch's new run may tap: straight horizontal segments of its system (of its
    system type, `by_type`), at least its cross-section, near the old junction's height."""
    need = _area(branch.size) or 0.0
    z = branch.junction_at[2]
    for e in work.el.values():
        path = e["path"]
        if e["group"] != "flow_segment" or e["storey"] != storey or not path or len(path) != 2:
            continue
        a, b = path
        if len(a) < 3 or abs(a[2] - b[2]) > 0.02 or abs(a[2] - z) > MAIN_DZ_M:
            continue
        if by_type:
            if e["id"] in skip or e["system_type"] != branch.like["system_type"]:
                continue
        elif not branch.systems & set(e["systems"]):
            continue
        if (_area(e["size"]) or 0.0) < need:
            continue
        yield Main(e["id"], _xy(a), _xy(b))


def _emit(
    work: _Work,
    branch: _Branch,
    room_id: str,
    points: list[Point3],
    start: str,
    end: str,
) -> None:
    like = {**branch.like, "room": room_id, "size": branch.size}
    previous = start
    for i, (a, b) in enumerate(pairwise(points)):
        if i and branch.elbow is not None:
            elbow = work.fitting({**branch.elbow, "room": room_id}, a)
            _connect(work, previous, elbow["ports"][0]["id"])
            previous = elbow["ports"][1]["id"]
        piece = work.segment(like, a, b)
        _connect(work, previous, piece["ports"][0]["id"])
        previous = piece["ports"][1]["id"]
    _connect(work, previous, end)


# --- checks, facts and the change (SV-20, SV-21) ------------------------------------------------


class _Net:
    """What SV-21's checks read from a model's graph (graph.py's `ServicesGraph`, so "reaches"
    means what `feeds` means: equipment reached, not passed)."""

    def __init__(self, elements: Iterable[dict[str, Any]], peer: dict[str, str]) -> None:
        pairs = {frozenset(p) for p in peer.items()}
        connections = [dict(zip(("a", "b"), sorted(p), strict=True)) for p in pairs]
        self.graph = ServicesGraph({"elements": list(elements), "connections": connections})
        self.el = self.graph.el
        ports = [p["id"] for e in self.el.values() for p in e["ports"]]
        self.open = sum(p not in self.graph.linked for p in ports)
        self.orphans = set(unconnected(self.graph)["elements"])

    def components(self) -> int:
        seen: set[str] = set()
        count = 0
        for start in self.el:
            if start in seen:
                continue
            count += 1
            seen.add(start)
            queue = deque([start])
            while queue:
                for nxt in self.graph.adj.get(queue.popleft(), set()) - seen:
                    seen.add(nxt)
                    queue.append(nxt)
        return count

    def equipment(self, start: str) -> frozenset[str]:
        if start not in self.el:
            return frozenset()
        return frozenset(self.graph.reach({start}) & self.graph.equipment)


def _checks(work: _Work, term: dict[str, Any] | None, what: str) -> tuple[Check, ...]:
    before = _Net((e.model_dump() for e in work.model.elements), _peers(work.model.connections))
    after = _Net(work.el.values(), work.peer)
    terminals = [i for i, e in before.el.items() if e["group"] == "flow_terminal"]
    moved = term["id"] if term and term["id"] in after.el else None
    others = [i for i in terminals if i != (term and term["id"])]
    label = term["label"] if term else "it"
    rows = [
        (
            "connected",
            after.components() <= before.components(),
            "The network is still in one piece.",
            "the network",
        ),
        (
            "same_equipment",
            moved is None
            or (
                before.equipment(moved) == after.equipment(moved)
                if moved in before.el
                else bool(after.equipment(moved))  # an added terminal: it reaches some
            ),
            "The terminal reaches the same equipment as before.",
            f"{label} from its equipment",
        ),
        (
            "others_unchanged",
            all(before.equipment(i) == after.equipment(i) for i in others),
            "No other terminal loses or changes its supply.",
            "other terminals from their supply",
        ),
        (
            "no_orphans",
            after.orphans <= before.orphans,
            "No element is left unconnected.",
            "an element from the network",
        ),
        (
            "open_ports",
            after.open == before.open,
            "Open connections are as before.",
            "a connection",
        ),
    ]
    if what == "reroute":
        rows += [
            ("no_cross", True, "Supply and return do not cross away from the terminal.", ""),
            ("no_door", True, "The new runs pass no door.", ""),
        ]
    for _, ok, _, broken in rows:
        if not ok:
            raise EditRefusedError(f"The {what} would disconnect {broken}.")
    return tuple(Check(code=code, ok=ok, text=text) for code, ok, text, _ in rows)


def _peers(connections: Iterable[Connection]) -> dict[str, str]:
    peer: dict[str, str] = {}
    for c in connections:
        peer[c.a], peer[c.b] = c.b, c.a
    return peer


def _facts(before: Iterable[dict[str, Any]], after: Iterable[dict[str, Any]]) -> list[FactChange]:
    """Run length per system and size, and counts per kind, where they changed."""

    def tally(elements: Iterable[dict[str, Any]]) -> Counter[tuple[str, str, str, str]]:
        out: Counter[tuple[str, str, str, str]] = Counter()
        for e in elements:
            out[("count", e["kind"], "", "")] += 1
            if e["group"] == "flow_segment" and e["length_m"]:
                for system in e["systems"] or [""]:
                    out[("length", _run_word(e), system, e["size"] or "")] += e["length_m"]
        return out

    b, a = tally(before), tally(after)
    rows: list[FactChange] = []
    for key in sorted(set(b) | set(a)):
        if abs(a[key] - b[key]) < 1e-9:
            continue
        kind, name, system, size = key
        rows.append(
            FactChange(
                what=f"{name} length" if kind == "length" else f"{name} count",
                system=system or None,
                size=size or None,
                unit="m" if kind == "length" else "count",
                before=round(b[key], 2),
                after=round(a[key], 2),
            )
        )
    return rows


def _change(
    work: _Work,
    op: Op,
    term: dict[str, Any] | None,
    flags: list[Flag],
    unknowns: tuple[str, ...],
    what: str,
) -> ServicesChange:
    checks = _checks(work, term, what)
    model = work.model
    original = {e.id: e for e in model.elements}
    storey_id = term["storey"] if term else None
    storey = next((s for s in model.storeys if s.id == storey_id), None)
    pairs = {frozenset(p) for p in work.peer.items()}
    old_pairs = {frozenset((c.a, c.b)) for c in model.connections}
    moved_id = term["id"] if term and op == "move_terminal" else None
    changed = [
        Element.model_validate(e)
        for i, e in work.el.items()
        if i in original and i != moved_id and e != original[i].model_dump()
    ]
    patch = Patch(
        moved=(Element.model_validate(work.el[moved_id]),) if moved_id else (),
        removed=tuple(i for i in original if i not in work.el),
        added=tuple(Element.model_validate(e) for i, e in work.el.items() if i not in original),
        connections_removed=tuple(
            c for c in model.connections if frozenset((c.a, c.b)) not in pairs
        ),
        connections_added=tuple(
            Connection(a=a, b=b, state="proposed")
            for a, b in sorted({tuple(sorted(p)) for p in pairs - old_pairs})
        ),
        changed=tuple(changed),
    )
    moved: tuple[Moved, ...] = ()
    if term:
        before = original.get(term["id"])
        to = tuple(work.el[term["id"]]["at"]) if term["id"] in work.el else None
        placed = op in ("move_terminal", "add_terminal")
        moved = (
            Moved.model_validate(
                {
                    "id": term["id"],
                    "label": term["label"],
                    "from": _frac(storey, before.at) if before else None,
                    "to": _frac(storey, to) if placed else None,
                    "to_m": to if placed else None,
                }
            ),
        )
    return ServicesChange(
        op=op,
        storey=storey_id,
        moved=moved,
        removed=tuple(_run(storey, original[i].model_dump()) for i in patch.removed),
        added=tuple(_run(storey, e.model_dump()) for e in patch.added if e.path),
        facts=tuple(_facts((e.model_dump() for e in model.elements), work.el.values())),
        checks=checks,
        flags=tuple(flags),
        unknowns=unknowns,
        patch=patch,
    )


def _run(storey: Storey | None, e: dict[str, Any]) -> RunChange:
    points = e["path"] or ((e["at"],) if e["at"] else ())
    label = e["label"]
    if e["length_m"] is not None:
        label = f"{e['type']}, {e['length_m']:.2f} m"
    polyline = tuple(p for q in points if (p := _frac(storey, q)) is not None)
    return RunChange(id=e["id"], polyline=polyline, label=label, system=(e["systems"] or [None])[0])


def _frac(storey: Storey | None, point: Sequence[float] | None) -> Point2 | None:
    if storey is None or point is None:
        return None
    x, y = fraction(storey, (point[0], point[1]))
    return (round(x, 4), round(y, 4))


# --- small helpers ------------------------------------------------------------------------------


def _xy(point: Sequence[float]) -> Point2:
    return (point[0], point[1])


def _room_of(model: ServicesModel, term: dict[str, Any]) -> Room:
    room = next((r for r in model.rooms if r.id == term["room"]), None)
    if room is None or term["at"] is None or len(room.polygon) < 3:
        raise EditRefusedError(NO_ROOM)
    return room


def _storey(model: ServicesModel, term: dict[str, Any]) -> Storey:
    storey = next((s for s in model.storeys if s.id == term["storey"]), None)
    if storey is None:
        raise EditRefusedError(NO_ROOM)
    return storey


def _edge_of_wall(model: ServicesModel, wall_id: str, room: Room, edges: list[Edge]) -> int:
    """The room edge the wall covers most; refused when it is not a wall of this room."""
    wall = next((w for w in model.walls if w.id == wall_id), None)
    if wall is None or (wall.rooms and room.id not in wall.rooms):
        raise EditRefusedError(NOT_ITS_WALL)
    area = Polygon(wall.polygon).buffer(0.1)
    cover = [edge.line.intersection(area).length for edge in edges]
    best = max(range(len(edges)), key=cover.__getitem__)
    if cover[best] < WALL_COVER_M:
        raise EditRefusedError(NOT_ITS_WALL)
    return best


def _body_len(term: dict[str, Any]) -> float:
    if term["body_m"]:
        return term["body_m"][0]
    spread = [_xy(p["at"]) for p in term["ports"] if p["at"]]
    return max((math.dist(a, b) for a in spread for b in spread), default=0.3) + 0.3


def _height(term: dict[str, Any]) -> float:
    # shortcut: `at` taken as the body's bottom (IFC radiators are placed there); use a stored
    # top when the model has one.
    return term["body_m"][2] if term["body_m"] else 0.6


def _centre(term: dict[str, Any]) -> tuple[Point2, Point2]:
    """The plan centre of a terminal's body and its long axis. The axis runs from the farthest
    port to the placement (IFC radiators are placed at one end, ports at the other), else along
    the ports, else x; the centre is the middle of what placement and ports span on it, which is
    the placement itself when the ports sit either side of it."""
    at = _xy(term["at"])
    xs = [_xy(p["at"]) for p in term["ports"] if p["at"]]
    far = max(xs, key=lambda q: math.dist(q, at), default=at)
    if math.dist(far, at) > 0.2:
        ux, uy = at[0] - far[0], at[1] - far[1]
    elif len(xs) > 1 and math.dist(xs[0], xs[-1]) > 1e-6:
        ux, uy = xs[-1][0] - xs[0][0], xs[-1][1] - xs[0][1]
    else:
        ux, uy = 1.0, 0.0
    norm = math.hypot(ux, uy)
    ux, uy = ux / norm, uy / norm
    ts = [(q[0] - at[0]) * ux + (q[1] - at[1]) * uy for q in (at, *xs)]
    mid = (min(ts) + max(ts)) / 2
    return (at[0] + ux * mid, at[1] + uy * mid), (ux, uy)


def _body(term: dict[str, Any]) -> list[Point2] | None:
    """The plan rectangle of a terminal's body (`_centre`), when the model gives its size."""
    if not term["body_m"] or not term["at"]:
        return None
    long, short = term["body_m"][0] / 2, term["body_m"][1] / 2
    (cx, cy), (ux, uy) = _centre(term)
    return [
        (cx + sa * long * ux - sb * short * uy, cy + sa * long * uy + sb * short * ux)
        for sa, sb in ((-1, -1), (1, -1), (1, 1), (-1, 1))
    ]


def _place(
    edge: Edge,
    body_len: float,
    spans: list[tuple[float, float]],
    position: Position,
    openings: list[Opening],
    top: float,
    others: list[list[Point2]],
) -> float:
    if isinstance(position, tuple):
        k = edge.line.project(Spot(position))
        k = min(max(k, body_len / 2 + CLEAR_M), edge.length - body_len / 2 - CLEAR_M)
        if any(a < k + body_len / 2 and k - body_len / 2 < b for a, b in spans):
            free = blocked_spans(edge, openings, [], top, 0.0)
            hits_opening = any(a < k + body_len / 2 and k - body_len / 2 < b for a, b in free)
            raise EditRefusedError(NO_FREE if hits_opening or not others else TAKEN)
        return k
    near = {"centre": None, "start": 0.0, "end": edge.length}.get(position)
    if position == "under_window":
        windows = [
            o
            for o in openings
            if o.kind == "window" and edge.line.distance(LineString(o.segment)) < 0.4
        ]
        if not windows:
            raise EditRefusedError(NO_FREE)
        near = edge.line.project(LineString(windows[0].segment).centroid)
        spans = [s for s in spans if not _over(s, near)]  # the window it goes under
    k = place(edge, body_len, spans, near)
    if k is None:
        raise EditRefusedError(NO_FREE)
    return k


def _over(span: tuple[float, float], k: float) -> bool:
    return span[0] <= k <= span[1]


def _opening(o: Any) -> Opening:
    return Opening(kind=o.kind, segment=o.segment, sill_m=o.sill_m, head_m=o.head_m)


def _wet(room: Room) -> bool:
    name = room.name.lower()
    return any(word in name for word in WET_WORDS)


def _run_word(element: dict[str, Any]) -> str:
    return {"ventilation": "duct", "electrical": "cable"}.get(element["discipline"], "pipe")


def _area(size: str | None) -> float | None:
    """A size's cross-section, to compare sizes: DN15, ø160, 400x200."""
    if not size:
        return None
    text = size.strip().lower().replace("ø", "").replace("dn", "")
    parts = [p for p in text.replace("\u00d7", "x").replace("/", "x").split("x") if p.strip()]
    try:
        numbers = [float(p.strip().split()[0]) for p in parts]
    except ValueError:
        return None
    if len(numbers) >= 2:
        return numbers[0] * numbers[1]
    return math.pi * numbers[0] ** 2 / 4 if numbers else None


def _weighted_median(pairs: list[tuple[float, float]]) -> float:
    pairs = sorted(pairs)
    total, acc = sum(w for _, w in pairs), 0.0
    for value, weight in pairs:
        acc += weight
        if acc >= total / 2:
            return value
    return pairs[-1][0]


def _spacing(branches: list[_Branch]) -> float:
    """The old pair spacing: the median distance from the supply's flat pieces to the return's."""
    supply, ret = branches[0].flat, branches[1].flat
    if not supply or not ret:
        return DEFAULT_PAIR_M
    gaps = sorted(min(s.interpolate(0.5, normalized=True).distance(r) for r in ret) for s in supply)
    gap = gaps[len(gaps) // 2]
    return min(max(gap, 0.03), 0.3) if gap > 0.005 else DEFAULT_PAIR_M


def _dedupe(points: list[Point3]) -> list[Point3]:
    out = [tuple(points[0])]
    for p in points[1:]:
        if math.dist(p, out[-1]) > 0.005:
            out.append(tuple(p))
    return out  # pyright: ignore[reportReturnType]

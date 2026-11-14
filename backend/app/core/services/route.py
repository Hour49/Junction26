"""SV-18: the reroute rule's plan geometry, on plain shapes in model metres (pure: shapely only).

edit.py turns the model into these shapes (the room polygon, its doors, the candidate mains per
port) and back. Here: where a terminal goes on a wall (step 1), where the new pair taps a main
(step 3), and the wall-following route of supply and return (steps 4-5). Refusals come back as
short codes; edit.py words them (SV-19).
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from shapely.geometry import LinearRing, LineString, Point, Polygon
from shapely.geometry.base import BaseGeometry

type XY = tuple[float, float]

SLIDE_STEP_M = 0.25  # a taken place slides in these steps (SV-18 step 1)
CLEAR_M = 0.1  # free wall on each side of a body; also the gap kept to other bodies
WINDOW_CLEAR_M = 0.05  # a window is in the way when its sill is below the top + this
OPENING_NEAR_M = 0.4  # an opening this close to a wall edge is on that wall
RING_NEAR_M = 0.3  # a main this close to the route line runs along a wall of the room
MAIN_NEAR_M = 1.0  # a main at most this far outside the room may be tapped (flagged)
SPLIT_END_M = 0.1  # a tap stays this far from a main segment's ends
MIN_MAIN_M = 0.2  # shorter pieces of a main are not tapped
# A door blocks a run this far from its centreline: half a wall plus 0.3 m in front of the face.
# shortcut: walls taken as 0.2 m thick; use the wall's own thickness when the model stores it.
DOOR_REACH_M = 0.4
MIN_OFFSET_M = 0.02  # a run closer to the wall than this is not routed


@dataclass(frozen=True)
class Edge:
    """One side of a room polygon: from `a` to `b`, unit tangent `t`, unit normal `n` into the
    room."""

    a: XY
    b: XY
    length: float
    t: XY
    n: XY

    @property
    def line(self) -> LineString:
        return LineString([self.a, self.b])

    def point(self, along: float, off: float) -> XY:
        """The point `along` metres from `a` and `off` metres into the room."""
        return (
            self.a[0] + self.t[0] * along + self.n[0] * off,
            self.a[1] + self.t[1] * along + self.n[1] * off,
        )


def room_edges(polygon: Sequence[XY]) -> list[Edge]:
    """The room's sides in order, each with its inward normal, whatever the winding."""
    room = Polygon(polygon)
    edges: list[Edge] = []
    for i, a in enumerate(polygon):
        b = polygon[(i + 1) % len(polygon)]
        length = math.dist(a, b)
        if length < 1e-9:
            continue
        t = ((b[0] - a[0]) / length, (b[1] - a[1]) / length)
        n = (-t[1], t[0])
        mid = ((a[0] + b[0]) / 2 + n[0] * 0.01, (a[1] + b[1]) / 2 + n[1] * 0.01)
        if not room.contains(Point(mid)):
            n = (t[1], -t[0])
        edges.append(Edge(a=(a[0], a[1]), b=(b[0], b[1]), length=length, t=t, n=n))
    return edges


@dataclass(frozen=True)
class Opening:
    """A door or window as the model stores it: its plan segment and heights above the storey."""

    kind: Literal["door", "window"]
    segment: tuple[XY, XY]
    sill_m: float
    head_m: float


def blocked_spans(
    edge: Edge,
    openings: Sequence[Opening],
    bodies: Sequence[Sequence[XY]],
    top_m: float,
    wall_distance: float,
) -> list[tuple[float, float]]:
    """The stretches of `edge` (distances from `edge.a`, clearance included) a terminal whose top is
    `top_m` above the storey may not cover: doors, windows with a sill below its top + 0.05 m, and
    the plan bodies of other terminals mounted on this wall."""
    spans: list[tuple[float, float]] = []
    line = edge.line
    for opening in openings:
        segment = LineString(opening.segment)
        if segment.distance(line) > OPENING_NEAR_M:
            continue
        if opening.kind == "window" and opening.sill_m >= top_m + WINDOW_CLEAR_M:
            continue  # a radiator under a window is how engineers place them
        ts = sorted(line.project(Point(c)) for c in segment.coords)
        spans.append((ts[0] - CLEAR_M, ts[-1] + CLEAR_M))
    for body in bodies:
        if Polygon(body).distance(line) >= wall_distance + 0.2:
            continue
        ts = sorted(line.project(Point(c)) for c in body)
        spans.append((ts[0] - CLEAR_M, ts[-1] + CLEAR_M))
    return spans


def place(
    edge: Edge, body_len: float, spans: Sequence[tuple[float, float]], near: float | None = None
) -> float | None:
    """Where the middle of a body `body_len` long goes along `edge`: at `near` (metres from
    `edge.a`, kept off the ends; the edge's middle when None), else the nearest free spot in
    0.25 m steps either way; None when no step is free."""
    half = body_len / 2
    lo, hi = half + CLEAR_M, edge.length - half - CLEAR_M
    centre = edge.length / 2 if near is None else min(max(near, lo), hi)
    for i in range(int(edge.length / SLIDE_STEP_M) + 2):
        for k in (centre,) if i == 0 else (centre + i * SLIDE_STEP_M, centre - i * SLIDE_STEP_M):
            if lo <= k <= hi and not any(a < k + half and k - half < b for a, b in spans):
                return k
    return None


def inset_ring(room: Polygon, offset: float) -> LinearRing | None:
    """The line `offset` metres inside the room's walls; None when the room is too narrow for it
    (nothing left, or it falls apart in pieces)."""
    inner = room.buffer(-offset, join_style="mitre")
    if inner.is_empty or inner.geom_type != "Polygon":  # the stubs say Polygon; it may be Multi
        return None
    return inner.exterior


def door_zones(doors: Sequence[Opening]) -> list[Polygon]:
    """The plan areas a run may not pass: each door's segment widened to both sides. Give only the
    doors whose head is above the run (a run under the floor passes every door)."""
    return [LineString(d.segment).buffer(DOOR_REACH_M, cap_style="flat") for d in doors]


@dataclass(frozen=True)
class Main:
    """A straight run the new pipe may tap, already filtered by edit.py (same system, at least the
    branch's cross-section, horizontal, near the old height): its id and plan ends."""

    id: str
    a: XY
    b: XY


Tier = Literal["along", "room", "junction", "outside"]


@dataclass(frozen=True)
class Tap:
    """Where a new run starts: on `main` at `along` metres from its `a` end, or at the old junction
    (`main` None)."""

    tier: Tier
    main: str | None
    at: XY
    along: float


@dataclass(frozen=True)
class Leg:
    """One port of the moved terminal: its new plan place, the old branch's distance from the wall,
    the mains it may tap, and the old junction's plan place (None when it is gone)."""

    port: XY
    offset: float
    mains: tuple[Main, ...]
    junction: XY | None


@dataclass(frozen=True)
class Run:
    tap: Tap
    path: tuple[XY, ...]  # from the tap to the port


@dataclass(frozen=True)
class Routed:
    runs: tuple[Run, ...]  # supply first
    crossover_m: float | None  # the pair crosses this far from the ports (allowed), else None


Refusal = Literal["no_main", "doors", "cross"]


def reroute(
    room: Polygon,
    doors: Sequence[Polygon],
    supply: Leg,
    ret: Leg | None,
    spacing: float,
    cross_at_ports_m: float = 0.0,
) -> Routed | Refusal:
    """SV-18 steps 3-5. The supply taps the nearest main by tier and runs along the ring at its
    offset, the shorter way round unless that passes a door. The return runs on the ring `spacing`
    further into the room (the wall side if that crosses), the same way round. A crossing of the
    pair is allowed only within `cross_at_ports_m` of the ports. Codes: `no_main` (nothing to
    tap), `doors` (both ways pass a door), `cross` (the pair crosses)."""
    ring = inset_ring(room, max(supply.offset, MIN_OFFSET_M))
    tap = _tap(room, ring, supply.mains, supply.port, supply.junction) if ring else None
    if ring is None or tap is None:
        return "no_main"
    first = _way(ring, tap.at, supply.port, None)
    way = next(
        (w for w in (first, _way(ring, tap.at, supply.port, -first[1])) if not _hits(w[0], doors)),
        None,
    )
    if way is None:
        return "doors"
    run = Run(tap, tuple(way[0]))
    if ret is None:
        return Routed((run,), None)
    taken = {tap.main} if tap.main else set[str]()
    mains = tuple(m for m in ret.mains if m.id not in taken)
    found, allowed = False, list[Routed]()
    for off in (supply.offset + spacing, supply.offset - spacing):
        ring_r = inset_ring(room, off) if off >= MIN_OFFSET_M else None
        tap_r = _tap(room, ring_r, mains, ret.port, ret.junction) if ring_r else None
        if ring_r is None or tap_r is None:
            continue
        found = True
        path, _ = _way(ring_r, tap_r.at, ret.port, way[1])
        if _hits(path, doors):
            continue
        crossing = _crossing(run.path, path, (supply.port, ret.port))
        routed = Routed((run, Run(tap_r, tuple(path))), crossing)
        if crossing is None:
            return routed
        if crossing <= cross_at_ports_m:
            allowed.append(routed)  # only when no clean variant is left
    if allowed:
        return allowed[0]
    return "cross" if found else "no_main"


def _tap(
    room: Polygon, ring: LinearRing, mains: Sequence[Main], port: XY, junction: XY | None
) -> Tap | None:
    """The nearest tap point to `port`, by tier: a main along a wall of the room (both ends of its
    part in the room within 0.3 m of the ring), any main in the room, the old junction in the room,
    a main at most 1.0 m outside."""
    inside = room.buffer(0.05)
    tiers: dict[Tier, list[tuple[Main, LineString, LineString]]] = {
        "along": [],
        "room": [],
        "outside": [],
    }
    for main in mains:
        line = LineString([main.a, main.b])
        if line.length < max(MIN_MAIN_M, 2 * SPLIT_END_M):
            continue
        part = line.intersection(inside)
        if isinstance(part, LineString) and part.length >= MIN_MAIN_M:
            near = all(ring.distance(Point(c)) <= RING_NEAR_M for c in part.coords)
            tiers["along" if near else "room"].append((main, line, part))
        elif room.distance(line) <= MAIN_NEAR_M:
            tiers["outside"].append((main, line, line))
    for tier in ("along", "room", "junction", "outside"):
        if tier == "junction":
            if junction is not None and inside.contains(Point(junction)):
                return Tap("junction", None, junction, 0.0)
            continue
        best: tuple[float, Tap] | None = None
        for main, line, part in tiers[tier]:
            near = part.interpolate(part.project(Point(port)))
            along = min(max(line.project(near), SPLIT_END_M), line.length - SPLIT_END_M)
            at = line.interpolate(along)
            gap = at.distance(Point(port))
            if best is None or gap < best[0]:
                best = (gap, Tap(tier, main.id, (at.x, at.y), along))
        if best:
            return best[1]
    return None


def _way(ring: LinearRing, start: XY, end: XY, direction: int | None) -> tuple[list[XY], int]:
    """start → its foot on the ring → along the ring (+1 forward, -1 back, None the shorter way)
    → the foot of end → end."""
    a, b = ring.project(Point(start)), ring.project(Point(end))
    total = ring.length
    if direction is None:
        forward = (b - a) % total
        direction = 1 if forward <= total - forward else -1
    span = (b - a) % total if direction > 0 else (a - b) % total
    corners = [ring.project(Point(c)) for c in list(ring.coords)[:-1]]
    steps = sorted(((v - a) * direction % total, v) for v in corners)
    path = [start, _at(ring, a)]
    path += [_at(ring, v) for k, v in steps if 1e-6 < k < span - 1e-6]
    path += [_at(ring, b), end]
    return _clean(path), direction


def _at(ring: LinearRing, distance: float) -> XY:
    p = ring.interpolate(distance)
    return (p.x, p.y)


def _clean(path: list[XY]) -> list[XY]:
    """Drop legs under 5 mm and points on a straight line."""
    out = [path[0]]
    for p in path[1:]:
        if math.dist(p, out[-1]) > 0.005:
            out.append(p)
    i = 1
    while i < len(out) - 1:
        (x0, y0), (x1, y1), (x2, y2) = out[i - 1], out[i], out[i + 1]
        cross = (x1 - x0) * (y2 - y1) - (y1 - y0) * (x2 - x1)
        dot = (x1 - x0) * (x2 - x1) + (y1 - y0) * (y2 - y1)
        if abs(cross) < 1e-9 and dot > 0:
            out.pop(i)
        else:
            i += 1
    return out


def _hits(path: Sequence[XY], zones: Sequence[Polygon]) -> bool:
    line = LineString(path)
    return any(line.intersects(zone) for zone in zones)


def _crossing(a: Sequence[XY], b: Sequence[XY], ports: Sequence[XY]) -> float | None:
    """How far from the nearer port the two runs cross, at the worst crossing; None when they do
    not cross."""
    la, lb = LineString(a), LineString(b)
    if not la.crosses(lb):
        return None
    meet: BaseGeometry = la.intersection(lb)
    points = [Point(c) for g in getattr(meet, "geoms", [meet]) for c in g.coords]
    return max(min(p.distance(Point(q)) for q in ports) for p in points)

"""What a plan edit does to each service discipline (docs/specs/services-follow.md, SF-1..SF-12).

Pure geometry and graph work over a proposal's removed and added pieces: no model file is read
here and nothing is drawn. Everything is in the plan page's metres (walls.PlanPage); heights are
the model's own.

A removed wall strip:
- a terminal on it (a connection port or its point within 0.15 m) is re-seated on the nearest
  free kept wall face of the merged room, with a right-angle estimate of each new connection;
  one that drains (a waste system) is offered the same place but left to a person;
- a run inside it goes with the wall, and every terminal that is then no longer connected to
  the rest of one of its systems is named as cut off;
- a run through it stays; a fire damper there says the wall is probably a fire boundary;
- a vertical run in it that goes on to another storey cannot follow a one-storey edit.

An added partition: the runs it crosses need openings, a run along it and a terminal under it
need a person.

A new room: what it has and what the room it was cut from keeps; and what it lacks, measured
against this floor's rooms of its own type (a kind of terminal that at least 80% of them have),
with a right-angle estimate of a connection from the nearest run of such a system.

Nothing is ever called approved or blocked: the facts are stated.
"""

import math
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

import shapely
from shapely.geometry import LineString, Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import nearest_points

from app.core.drawing.model import words
from app.core.ifc_facts import Discipline
from app.core.plan_edit.law_check import ROOM_WORDS
from app.core.plan_edit.model import Proposal
from app.core.plan_edit.walls import PlanPage, length_of
from app.core.services.graph import ServiceGraph
from app.core.services.model import (
    Code,
    DisciplineFollow,
    Lane,
    Path,
    Point2,
    ServiceAction,
    ServiceElement,
    ServiceMark,
    ServicesFollow,
    Status,
    Summary,
)

ON_M = 0.15  # a terminal this close to a wall strip hangs on it
IN_M = 0.02  # tolerance of "inside the strip"
VERTICAL_M = 0.05  # a run this short on the plan stands upright
RISER_M = 1.0  # an upright run at least this tall is a riser candidate
COLUMN_M = 0.15  # pieces this close on the plan are one upright column
STOREY_SLACK_M = 0.2  # a column that passes the storey's heights by this much goes on
CLEAR_M = 0.5  # between two wall-mounted terminals
DOOR_M = 0.15  # kept clear on each side of a door
ROOM_REACH_M = 0.4  # a wall-mounted terminal's room is the nearest one within this
NEAR_M = 3.0  # how far around the edit the overlay shows the discipline
BELOW_M = 1.0  # a new connection may start from a run this far under the floor
PASSAGE_M = 0.5  # pipework this long inside a wall runs along it; shorter, it only crosses
USUAL_SHARE = 0.8  # a kind of terminal this share of a type's rooms have is usual for the type
COMPARED_MIN = 2  # fewer rooms of a type say nothing about the type
IN_WALL_KINDS = {"air_terminal"}  # on a wall only when in it: most hang from the ceiling

LETTER: Mapping[Discipline, str] = {
    "plumbing": "P",
    "ventilation": "V",
    "heating": "H",
    "electrical": "E",
}
_PLAIN = {
    "TOILETPAN": "toilet",
    "URINAL": "urinal",
    "WASHHANDBASIN": "washbasin",
    "SINK": "sink",
    "BATH": "bath",
    "SHOWER": "shower",
    "BIDET": "bidet",
    "RADIATOR": "radiator",
    "CONVECTOR": "convector",
    "FIREDAMPER": "fire damper",
}
_KINDS = {
    "pipe_segment": "pipe",
    "duct_segment": "duct",
    "cable_segment": "cable",
    "cable_carrier_segment": "cable tray",
    "pipe_fitting": "pipe fitting",
    "duct_fitting": "duct fitting",
    "air_terminal": "air terminal",
    "space_heater": "radiator",
    "sanitary_terminal": "sanitary fixture",
    "waste_terminal": "drain",
    "outlet": "socket",
    "light_fixture": "light",
    "switching_device": "switch",
}
# A system that drains by gravity: a fixture on it cannot simply be moved along a wall.
_DRAINS = re.compile(
    r"schmutz|abwasser|waste|sewage|sewer|soil|drain|sanitary|regen|rain|storm|avlopp|viem|jätev",
    re.IGNORECASE,
)
UNKNOWNS = (
    "The services are not checked against each other in 3D (a pipe against a duct).",
    "New connections are right-angle estimates on the plan, not a routed design; pipe sizes, "
    "flow rates and waste falls are not checked.",
)


def plain(element: ServiceElement) -> str:
    return (
        _PLAIN.get(element.predefined or "")
        or _KINDS.get(element.kind)
        or element.kind.replace("_", " ")
    )


def _one(count: int, one: str, many: str) -> str:
    return one if count == 1 else many


def counted(count: int, word: str) -> str:
    if count == 1:
        return f"1 {word}"
    return f"{count} {word}{'es' if word.endswith(('ch', 's', 'x')) else 's'}"


@dataclass(frozen=True)
class _Found:
    """An action before its elements have overlay refs."""

    status: Status
    code: Code
    label: str
    guids: tuple[str, ...] = ()
    system: str | None = None
    moved_to: Point2 | None = None  # page metres
    paths: tuple[tuple[Point2, ...], ...] = ()  # page metres
    terminals_lost: int = 0
    new_run_m: float = 0.0


@dataclass
class _Edit:
    page: PlanPage
    removed: BaseGeometry
    added: BaseGeometry
    before: dict[str, tuple[str, Polygon]]  # room id -> label, shape
    after: list[tuple[str, Polygon, tuple[str, ...]]]  # label, shape, the rooms it was
    doors: BaseGeometry
    new: list[tuple[str, Polygon, tuple[str, ...]]]  # rooms the edit makes: as `after`
    taken: list[BaseGeometry] = field(default_factory=list[BaseGeometry])  # wall spots in use

    @classmethod
    def of(cls, page: PlanPage, proposal: Proposal) -> "_Edit":
        labels = {room.id: room.label for room in page.rooms}
        gone = {item.id for item in proposal.removed}
        doors = [
            page.box_shape(o.box).buffer(DOOR_M)
            for o in page.openings
            if o.kind == "door" and o.id not in gone
        ]
        return cls(
            page=page,
            removed=shapely.unary_union([page.shape(i.polygon) for i in proposal.removed]),
            added=shapely.unary_union([page.shape(i.polygon) for i in proposal.added]),
            before={rid: (labels[rid], shape) for rid, shape in page.room_shapes().items()},
            after=[(r.label, page.shape(r.polygon), r.was) for r in proposal.rooms],
            doors=shapely.unary_union(doors),
            new=[
                (r.label, page.shape(r.polygon), r.was)
                for r in proposal.rooms
                if r.area_before_m2 == 0 and r.was
            ],
        )

    def room_id_of(self, element: ServiceElement) -> str | None:
        """The room a terminal is in before the edit: the one holding its point, else the
        nearest within reach (a wall-mounted terminal's point is in the wall)."""
        at = Point(element.at[:2])
        near = min(
            ((shape.distance(at), rid) for rid, (_, shape) in self.before.items()), default=None
        )
        return near[1] if near is not None and near[0] <= ROOM_REACH_M else None

    def room_of(self, element: ServiceElement) -> str | None:
        """That room's label."""
        room = self.room_id_of(element)
        return None if room is None else self.before[room][0]

    def fraction(self, point: Point2) -> Point2:
        return (round(point[0] / self.page.width_m, 5), round(point[1] / self.page.height_m, 5))


def follow(
    page: PlanPage,
    proposal: Proposal,
    lanes: Sequence[Lane],
    heights: tuple[float, float],
    storey: str | None = None,
    credits: Sequence[str] = (),
) -> ServicesFollow:
    """The proposal followed through every lane. `heights`: the storey's floor and the floor
    above, in the model's metres: what stands between them meets the walls of this page."""
    edit = _Edit.of(page, proposal)
    # the overlay shows what is around the changed walls and in the rooms the edit makes
    changed = shapely.unary_union([edit.removed, edit.added, *(shape for _, shape, _ in edit.new)])
    on_storey = {
        lane.discipline: [e for e in lane.elements if _between(e, heights)] for lane in lanes
    }
    # wall spots already in use: every terminal of every lane that stays where it is
    edit.taken = [
        Point(e.at[:2]).buffer(CLEAR_M)
        for elements in on_storey.values()
        for e in elements
        if e.is_terminal and not _hangs_on(e, edit.removed)
    ]
    found = [_lane(edit, lane, on_storey[lane.discipline], heights, changed) for lane in lanes]
    return ServicesFollow(
        storey=storey,
        disciplines=tuple(found),
        unknowns=UNKNOWNS if any(lane.status == "checked" for lane in lanes) else (),
        credits=tuple(dict.fromkeys(credits)),
    )


def not_followed(lanes: Sequence[Lane]) -> ServicesFollow:
    """The follow-up when nothing could be laid over the plan: every lane with its reason."""
    return ServicesFollow(storey=None, disciplines=tuple(_unchecked(lane) for lane in lanes))


def _unchecked(lane: Lane) -> DisciplineFollow:
    name = lane.discipline.capitalize()
    if lane.status == "no_model":
        why = lane.reason or f"this project has no {lane.discipline} model"
    else:
        why = lane.reason or "the model does not line up with this plan"
    return DisciplineFollow(
        discipline=lane.discipline,
        status="no_model" if lane.status == "no_model" else "not_aligned",
        source=lane.source,
        reason=why,
        line=f"{name}: not checked, {why}.",
    )


def _lane(
    edit: _Edit,
    lane: Lane,
    here: list[ServiceElement],
    heights: tuple[float, float],
    changed: BaseGeometry,
) -> DisciplineFollow:
    if lane.status != "checked":
        return _unchecked(lane)
    name = lane.discipline.capitalize()
    found: list[_Found] = []
    if not edit.removed.is_empty:
        found += _removed_wall(edit, lane, here, heights)
    if not edit.added.is_empty:
        found += _added_wall(edit, here)
    if edit.new:
        found += _new_rooms(edit, here)
    marks, refs = _marks(edit, lane.discipline, here, found, changed)
    actions = tuple(
        ServiceAction(
            id=f"a{n}",
            status=f.status,
            code=f.code,
            label=f.label,
            refs=tuple(refs[g] for g in f.guids if g in refs),
            system=f.system,
            moved_to=None if f.moved_to is None else edit.fraction(f.moved_to),
            paths=tuple(tuple(edit.fraction(p) for p in path) for path in f.paths),
        )
        for n, f in enumerate(found, start=1)
    )
    by_status = Counter(f.status for f in found)
    summary = Summary(
        follows=by_status["follows"],
        stays=by_status["stays"],
        needs_decision=by_status["needs_decision"],
        cut_off=sum(f.terminals_lost for f in found),
        new_run_m=round(sum(f.new_run_m for f in found), 1),
    )
    return DisciplineFollow(
        discipline=lane.discipline,
        status="checked",
        source=lane.source,
        elements=len(here),
        line=f"{name}: {_line(found, summary)}",
        summary=summary,
        marks=marks,
        actions=actions,
    )


def _line(found: list[_Found], summary: Summary) -> str:
    codes = Counter(f.code for f in found)
    if not codes.keys() - {"tally"}:
        return "nothing of this model is on, in or through the changed walls."
    parts = [
        f"{codes['reseat']} to re-seat" if codes["reseat"] else "",
        f"{codes['in_wall']} system{'s' if codes['in_wall'] > 1 else ''} with pipework inside "
        "the wall"
        if codes["in_wall"]
        else "",
        f"{counted(summary.cut_off, 'terminal')} cut off" if summary.cut_off else "",
        counted(codes["riser"], "riser") if codes["riser"] else "",
        counted(codes["fire_damper"], "fire damper") if codes["fire_damper"] else "",
        f"{counted(codes['opening'], 'system')} needing openings" if codes["opening"] else "",
        f"{codes['under']} under or along the new wall" if codes["under"] else "",
        f"{counted(codes['missing'], 'kind')} of terminal missing in the new room"
        if codes["missing"]
        else "",
        f"{counted(codes['through'], 'system')} passing through" if codes["through"] else "",
        f"{summary.needs_decision} for a person to decide" if summary.needs_decision else "",
    ]
    return ", ".join(part for part in parts if part) + "."


# --- a removed wall strip ------------------------------------------------------------------------


def _removed_wall(
    edit: _Edit, lane: Lane, here: list[ServiceElement], heights: tuple[float, float]
) -> list[_Found]:
    strip = edit.removed
    graph = ServiceGraph(lane.elements)
    touching: dict[str, tuple[ServiceElement, str]] = {}  # in the strip or ending in it
    through: list[ServiceElement] = []
    risers: list[ServiceElement] = []
    hosted: list[ServiceElement] = []
    dampers: list[ServiceElement] = []
    for element in here:
        if element.is_terminal:
            if _hangs_on(element, strip):
                hosted.append(element)
            continue
        relation = _relation(element, strip)
        if relation == "riser":
            risers.append(element)
        elif relation in ("inside", "ends_in"):
            touching[element.guid] = (element, relation)
        elif relation == "through":
            through.append(element)
        if "FIRE" in (element.predefined or "").upper() and _reach(element, strip) <= 2 * ON_M:
            dampers.append(element)
    inside: list[ServiceElement] = []  # go with the wall
    stubs: list[ServiceElement] = []  # end in the wall: the last piece to a terminal on it
    for chain in _chains(touching, graph):
        if _crosses(edit, chain, strip, graph):
            through += [element for element, _ in chain]
        else:
            inside += [element for element, relation in chain if relation == "inside"]
            stubs += [element for element, relation in chain if relation == "ends_in"]
    # a fire damper is said once, as the damper in this wall, not again as a run passing through
    through = [e for e in through if e not in dampers]
    gone = {e.guid for e in (*inside, *stubs, *hosted)}
    trunks = {
        system: (graph.largest(system), graph.largest(system, gone))
        for system in sorted({s for g in gone for e in [graph.get(g)] if e for s in e.systems})
    }
    found: list[_Found] = []
    for column in _columns(risers, lane.elements):
        found.append(_riser(column, heights))
    for damper in dampers:
        found.append(
            _Found(
                "needs_decision",
                "fire_damper",
                "A fire damper sits in this wall: the wall is probably a fire compartment "
                "boundary, which this check cannot confirm.",
                (damper.guid,),
            )
        )
    for system, pieces in _by_system(inside).items():
        runs = [e for e in pieces if e.is_run]
        n = len(pieces)
        what = counted(n, f"{plain(runs[0])} piece" if runs else plain(pieces[0]))
        metres = f" ({round(sum(_length(e) for e in runs), 1)} m of run)" if runs else ""
        found.append(
            _Found(
                "needs_decision",
                "in_wall",
                f"{what} of {system}{metres} {_one(n, 'is', 'are')} inside the removed wall and "
                f"{_one(n, 'goes', 'go')} with it: {_one(n, 'it has', 'they have')} to be "
                "rebuilt somewhere else.",
                tuple(e.guid for e in pieces),
                system,
            )
        )
    for system, (before, after) in trunks.items():
        lost = list(graph.terminals(before - gone - after))
        if lost:
            found.append(
                _Found(
                    "cut_off",
                    "cut_off",
                    f"{_listed(edit, lost)} would no longer be connected to the rest of {system}.",
                    tuple(e.guid for e in lost),
                    system,
                    terminals_lost=len(lost),
                )
            )
    for terminal in hosted:
        found.append(_reseat(edit, terminal, lane.elements, trunks, gone, heights))
    for system, pieces in _by_system(through).items():
        runs = [e for e in pieces if e.is_run] or pieces
        word = plain(runs[0])
        found.append(
            _Found(
                "stays",
                "through",
                f"{counted(len(runs), word)} of {system} {_one(len(runs), 'passes', 'pass')} "
                "through the removed wall and "
                f"{_one(len(runs), 'stays where it is', 'stay where they are')}"
                ", now open to the merged room.",
                tuple(e.guid for e in pieces),
                system,
            )
        )
    tally = _tally(edit, here, hosted)
    if tally is not None:
        found.append(tally)
    return found


def _relation(element: ServiceElement, strip: BaseGeometry) -> str | None:
    """How a piece that is no terminal meets the strip: "inside", "ends_in", "through", "riser"
    (an upright run in it) or None."""
    near = strip.buffer(IN_M)
    if not element.is_run:
        return "inside" if near.covers(Point(element.at[:2])) else None
    (ax, ay, az), (bx, by, bz) = element.ports
    a, b = Point(ax, ay), Point(bx, by)
    if a.distance(b) < VERTICAL_M:
        if not near.covers(a):
            return None
        return "riser" if abs(az - bz) >= RISER_M else "inside"
    a_in, b_in = near.covers(a), near.covers(b)
    if a_in and b_in:
        return "inside"
    if a_in or b_in:
        return "ends_in"
    return "through" if LineString([a, b]).intersects(strip) else None


def _columns(
    risers: list[ServiceElement], elements: Sequence[ServiceElement]
) -> list[list[ServiceElement]]:
    """Each riser with the other pieces of its lane standing on the same spot, one column per
    spot and system."""
    seen: set[tuple[int, int, tuple[str, ...]]] = set()
    columns: list[list[ServiceElement]] = []
    for riser in risers:
        x, y = riser.ports[0][:2]
        key = (round(x / COLUMN_M), round(y / COLUMN_M), riser.systems)
        if key in seen:
            continue
        seen.add(key)
        columns.append(
            [
                e
                for e in elements
                if set(e.systems) & set(riser.systems)
                and all(math.hypot(p[0] - x, p[1] - y) <= COLUMN_M for p in (e.ports or (e.at,)))
            ]
        )
    return columns


def _riser(column: list[ServiceElement], heights: tuple[float, float]) -> _Found:
    low = min(e.heights[0] for e in column)
    high = max(e.heights[1] for e in column)
    head = next(e for e in column if e.is_run)
    system = ", ".join(head.systems) or "an unnamed system"
    size = f" ({head.size})" if head.size else ""
    goes_on = low < heights[0] - STOREY_SLACK_M or high > heights[1] + STOREY_SLACK_M
    tail = (
        "It goes on to another storey, so it cannot move with an edit of this storey."
        if goes_on
        else "It stays within this storey."
    )
    return _Found(
        "needs_decision",
        "riser",
        f"An upright {plain(head)} of {system}{size}, {round(high - low, 1)} m tall, stands in "
        f"the removed wall. {tail}",
        tuple(e.guid for e in column),
        head.systems[0] if head.systems else None,
    )


def _chains(
    touching: Mapping[str, tuple[ServiceElement, str]], graph: ServiceGraph
) -> list[list[tuple[ServiceElement, str]]]:
    """The pieces in or ending in the strip, grouped by how they connect to each other there."""
    left = set(touching)
    chains: list[list[tuple[ServiceElement, str]]] = []
    while left:
        start = min(left)
        edge, seen = [start], {start}
        while edge:
            for other in graph.neighbours(edge.pop()):
                if other in left and other not in seen:
                    seen.add(other)
                    edge.append(other)
        left -= seen
        chains.append([touching[guid] for guid in sorted(seen)])
    return chains


def _crosses(
    edit: _Edit, chain: list[tuple[ServiceElement, str]], strip: BaseGeometry, graph: ServiceGraph
) -> bool:
    """Whether a chain only passes through the wall: it leaves the strip on two sides (towards
    two rooms) and has no more run inside it than a wall is thick. Such a run stays; pipework
    that runs along inside the wall, or enters from one side only, goes with it."""
    along = sum(
        _length(element) for element, relation in chain if relation == "inside" and element.is_run
    )
    thick = strip.area / length_of(strip) if strip.area else 0.0
    if along > max(2 * thick, PASSAGE_M):
        return False
    near = strip.buffer(IN_M)
    members = {element.guid for element, _ in chain}
    leaving: list[tuple[float, float, float]] = []  # where the chain goes on outside the strip
    for element, _ in chain:
        leaving += [p for p in element.ports if not near.covers(Point(p[0], p[1]))]
        for other in graph.neighbours(element.guid):
            beyond = None if other in members else graph.get(other)
            if beyond is not None:  # its point farthest from the wall: the side it goes to
                leaving.append(
                    max((*beyond.ports, beyond.at), key=lambda p: strip.distance(Point(p[0], p[1])))
                )
    sides: set[str] = set()
    for x, y, _ in leaving:
        at = Point(x, y)
        if near.covers(at):
            continue
        side = min(edit.before.items(), key=lambda room: room[1][1].distance(at), default=None)
        if side is not None:
            sides.add(side[0])
    return len(sides) >= 2


def _hangs_on(terminal: ServiceElement, strip: BaseGeometry) -> bool:
    """A terminal on the wall strip: a port or its point within 0.15 m; an air terminal only
    when it is in the wall itself (most hang from the ceiling, wherever the wall is)."""
    return _reach(terminal, strip) <= (IN_M if terminal.kind in IN_WALL_KINDS else ON_M)


def _reseat(
    edit: _Edit,
    terminal: ServiceElement,
    elements: Sequence[ServiceElement],
    trunks: Mapping[str, tuple[frozenset[str], frozenset[str]]],
    gone: set[str],
    heights: tuple[float, float],
) -> _Found:
    word = plain(terminal)
    where = edit.room_of(terminal)
    what = f"The {word}" + (f" in {where}" if where else "") + " hangs on the removed wall"
    at = Point(terminal.at[:2])
    rooms = [shape for _, shape, _ in edit.after]
    room = min(rooms, key=lambda shape: shape.distance(at), default=None)
    free = (
        None
        if room is None
        else room.exterior.difference(shapely.unary_union([edit.doors, *edit.taken]))
    )
    if free is None or free.is_empty:
        return _Found(
            "needs_decision",
            "reseat",
            f"{what}: no free wall face was found for it in the merged room.",
            (terminal.guid,),
        )
    target = nearest_points(free, at)[0]
    edit.taken.append(target.buffer(CLEAR_M))
    paths: list[tuple[Point2, ...]] = []
    metres = 0.0
    for system in terminal.systems:
        kept = trunks[system][1] if system in trunks else None
        anchors = [
            e
            for e in elements
            if system in e.systems
            and e.guid not in gone
            and (kept is None or e.guid in kept)
            and e.heights[0] < heights[1]
            and e.heights[1] > heights[0] - BELOW_M
        ]
        if not anchors:
            continue
        shapes = [_shape(e) for e in anchors]
        nearest = shapes[int(shapely.distance(shapes, target).argmin())]  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
        start = nearest_points(nearest, target)[0]
        metres += abs(start.x - target.x) + abs(start.y - target.y)
        paths.append(((start.x, start.y), (target.x, start.y), (target.x, target.y)))
    moved = round(at.distance(target), 1)
    new = round(metres, 1)
    systems = ", ".join(terminal.systems)
    place = f"its nearest free place on a kept wall is {moved} m away"
    run = f", with about {new} m of new connection ({systems})" if paths else ""
    drains = [s for s in terminal.systems if _DRAINS.search(s)]
    if drains:
        return _Found(
            "needs_decision",
            "reseat",
            f"{what}: {place}{run}. It drains into {', '.join(drains)}: the fall and venting of "
            "a new waste branch are not checked here.",
            (terminal.guid,),
            moved_to=(target.x, target.y),
            paths=tuple(paths),
            new_run_m=new,
        )
    return _Found(
        "follows",
        "reseat",
        f"{what}: re-seated on the nearest free kept wall, {moved} m away{run}. An estimate, "
        "not a routed design.",
        (terminal.guid,),
        moved_to=(target.x, target.y),
        paths=tuple(paths),
        new_run_m=new,
    )


def _tally(edit: _Edit, here: list[ServiceElement], hosted: list[ServiceElement]) -> _Found | None:
    """The merged room's terminals by kind, and how many came from each room."""
    merged = next(((label, was) for label, _, was in edit.after if len(was) >= 2), None)
    if merged is None:
        return None
    labels = [edit.before[rid][0] for rid in merged[1] if rid in edit.before]
    counts: dict[str, Counter[str]] = {}
    for element in here:
        if element.is_terminal and (room := edit.room_of(element)) in labels:
            counts.setdefault(plain(element), Counter())[room or ""] += 1
    if not counts:
        return None
    parts = [
        f"{counted(sum(rooms.values()), word)} ("
        + " + ".join(f"{rooms[label]} from {label}" for label in labels if rooms[label])
        + ")"
        for word, rooms in sorted(counts.items())
    ]
    moving = (
        f"; {len(hosted)} of them {_one(len(hosted), 'hangs', 'hang')} on the removed wall"
        if hosted
        else ""
    )
    return _Found("stays", "tally", f"The merged room has {', '.join(parts)}{moving}.")


# --- an added partition --------------------------------------------------------------------------


def _added_wall(edit: _Edit, here: list[ServiceElement]) -> list[_Found]:
    wall = edit.added
    near = wall.buffer(IN_M)
    crossing: list[ServiceElement] = []
    along: list[ServiceElement] = []
    under: list[ServiceElement] = []
    for element in here:
        if element.is_terminal:
            if near.buffer(ON_M / 2).covers(Point(element.at[:2])):
                under.append(element)
            continue
        if not element.is_run:
            continue
        (ax, ay, _), (bx, by, _) = element.ports
        a, b = Point(ax, ay), Point(bx, by)
        if a.distance(b) < VERTICAL_M:
            if near.covers(a):
                along.append(element)
        elif near.covers(a) and near.covers(b):
            along.append(element)
        elif LineString([a, b]).intersects(wall):
            crossing.append(element)
    found: list[_Found] = []
    for system, pieces in _by_system(crossing).items():
        word = plain(pieces[0])
        sizes = sorted({e.size for e in pieces if e.size})
        size = f" ({', '.join(sizes)})" if sizes else ""
        found.append(
            _Found(
                "follows",
                "opening",
                f"{counted(len(pieces), word)} of {system}{size} "
                f"{_one(len(pieces), 'crosses the new wall: it', 'cross the new wall: each')} "
                "needs an opening in it.",
                tuple(e.guid for e in pieces),
                system,
            )
        )
    for system, pieces in _by_system(along).items():
        word = plain(pieces[0])
        found.append(
            _Found(
                "needs_decision",
                "under",
                f"{counted(len(pieces), word)} of {system} {_one(len(pieces), 'runs', 'run')} "
                "where the new wall goes: the wall or the run has to move.",
                tuple(e.guid for e in pieces),
                system,
            )
        )
    for terminal in under:
        where = edit.room_of(terminal)
        found.append(
            _Found(
                "needs_decision",
                "under",
                f"The {plain(terminal)}" + (f" in {where}" if where else "") + " sits where the "
                "new wall goes: it has to move.",
                (terminal.guid,),
            )
        )
    return found


# --- a new room ----------------------------------------------------------------------------------


def room_type(name: str) -> str:
    """A room's type from its name, as the plan edit's law check reads a new room's."""
    low = name.lower()
    return next((kind for kind, pattern in ROOM_WORDS if re.search(pattern, low)), "other")


def _new_rooms(edit: _Edit, here: list[ServiceElement]) -> list[_Found]:
    """Per room the edit makes: the terminals it has and the room it was cut from keeps, and
    each kind of terminal that is usual for this floor's rooms of its type and that it lacks."""
    terminals = [e for e in here if e.is_terminal]
    if not terminals:
        return []
    home = {e.guid: edit.room_id_of(e) for e in terminals}
    types = {r.id: r.type for r in edit.page.rooms if not r.outdoor and r.id in edit.before}
    found: list[_Found] = []
    for label, shape, was in edit.new:
        others = [other for name, other, of in edit.after if of == was and name != label]
        from_parent = [e for e in terminals if home[e.guid] in was]
        mine = [e for e in from_parent if _nearer(e, shape, others)]
        kept = [e for e in from_parent if e not in mine]
        parent = edit.before[was[0]][0] if was[0] in edit.before else "the room it was cut from"
        kind = room_type(label)
        peers = [rid for rid, of_type in types.items() if of_type == kind]
        if mine or kept:
            has = _counts(mine) or "none of this model's terminals"
            keeps = f"; {parent} keeps {_counts(kept)}" if kept else ""
            found.append(_Found("stays", "tally", f"{label} has {has}{keeps}."))
        if len(peers) < COMPARED_MIN:
            continue
        rooms_with: dict[str, set[str]] = {}
        systems: dict[str, set[str]] = {}
        for element in terminals:
            if (room := home[element.guid]) in peers:
                rooms_with.setdefault(plain(element), set()).add(room or "")
                systems.setdefault(plain(element), set()).update(element.systems)
        had = {plain(e) for e in mine}
        for word, rooms in sorted(rooms_with.items()):
            if word in had or len(rooms) < USUAL_SHARE * len(peers):
                continue
            usual = (
                f"{label} has no {word}: {len(rooms)} of the {len(peers)} rooms of its type on "
                f"this floor ({words(kind)}) have one."
            )
            found.append(_missing(edit, here, shape, usual, systems[word]))
    return found


def _nearer(element: ServiceElement, shape: Polygon, others: Sequence[Polygon]) -> bool:
    at = Point(element.at[:2])
    return all(shape.distance(at) <= other.distance(at) for other in others)


def _counts(terminals: Sequence[ServiceElement]) -> str:
    kinds = Counter(plain(e) for e in terminals)
    return ", ".join(counted(count, word) for word, count in sorted(kinds.items()))


def _missing(
    edit: _Edit, here: list[ServiceElement], room: Polygon, usual: str, systems: set[str]
) -> _Found:
    """What the room lacks, and where the nearest run of such a system is: the estimate of a
    connection from there to the room's nearest wall face, right-angled, with the walls it
    passes. Always for a person: whether the room needs it is not this check's to say."""
    runs = [e for e in here if e.is_run and systems & set(e.systems) and _length(e) > VERTICAL_M]
    if not runs:
        return _Found("needs_decision", "missing", f"{usual} No run to connect one to was found.")
    shapes = [_shape(e) for e in runs]
    nearest = int(shapely.distance(shapes, room).argmin())  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
    run = runs[nearest]
    system = ", ".join(sorted(systems & set(run.systems)))
    what = f"{plain(run)} of {system}"
    waste = (
        " The fall and venting of a waste branch are not checked here."
        if _DRAINS.search(system)
        else ""
    )
    start, target = nearest_points(shapes[nearest], room)
    apart = start.distance(target)
    if apart <= IN_M:
        return _Found(
            "needs_decision",
            "missing",
            f"{usual} A {what} already runs through the room: one could connect to it there."
            f"{waste}",
            (run.guid,),
            system,
        )
    path = ((start.x, start.y), (target.x, start.y), (target.x, target.y))
    metres = round(abs(start.x - target.x) + abs(start.y - target.y), 1)
    crossed = LineString(path).intersection(
        shapely.unary_union([edit.page.wall_mass(), edit.added])
    )
    walls = len([part for part in shapely.get_parts(crossed) if part.length > IN_M])
    passing = f" and pass {counted(walls, 'wall')}" if walls else ""
    return _Found(
        "needs_decision",
        "missing",
        f"{usual} The nearest {what} is {apart:.1f} m from the room: a connection to it would "
        f"be about {metres} m{passing}. An estimate, not a routed design.{waste}",
        (run.guid,),
        system,
        paths=(path,),
        new_run_m=metres,
    )


# --- shared --------------------------------------------------------------------------------------


def _between(element: ServiceElement, heights: tuple[float, float]) -> bool:
    low, high = element.heights
    return low < heights[1] and high > heights[0]


def _reach(element: ServiceElement, strip: BaseGeometry) -> float:
    """The distance from the strip to the nearest of the element's ports and its own point."""
    if strip.is_empty:
        return math.inf
    return min(strip.distance(Point(p[0], p[1])) for p in (*element.ports, element.at))


def _shape(element: ServiceElement) -> BaseGeometry:
    if element.is_run and element.ports[0][:2] != element.ports[1][:2]:
        return LineString([element.ports[0][:2], element.ports[1][:2]])
    return Point(element.at[:2])


def _length(run: ServiceElement) -> float:
    return math.dist(run.ports[0], run.ports[1])


def _by_system(elements: Iterable[ServiceElement]) -> dict[str, list[ServiceElement]]:
    found: dict[str, list[ServiceElement]] = {}
    for element in elements:
        found.setdefault(", ".join(element.systems) or "an unnamed system", []).append(element)
    return dict(sorted(found.items()))


def _listed(edit: _Edit, terminals: list[ServiceElement]) -> str:
    """ "3 urinals in WC 1 and 2 washbasins in WC 2"."""
    groups = Counter((plain(e), edit.room_of(e)) for e in terminals)
    parts = [
        counted(count, word) + (f" in {room}" if room else "")
        for (word, room), count in sorted(groups.items(), key=lambda g: (g[0][1] or "", g[0][0]))
    ]
    return (", ".join(parts[:-1]) + " and " + parts[-1]) if len(parts) > 1 else parts[0]


def _marks(
    edit: _Edit,
    discipline: Discipline,
    here: list[ServiceElement],
    found: list[_Found],
    changed: BaseGeometry,
) -> tuple[tuple[ServiceMark, ...], dict[str, str]]:
    """The overlay's marks: what an action names, and the runs and terminals around the edit."""
    named = {g for f in found for g in f.guids}
    around = changed.buffer(NEAR_M)
    shown = [
        e
        for e in here
        if e.guid in named or ((e.is_run or e.is_terminal) and _shape(e).intersects(around))
    ]
    shown.sort(key=lambda e: (round(e.at[1], 2), round(e.at[0], 2), e.guid))
    letter = LETTER.get(discipline, "S")
    refs = {e.guid: f"{letter}{n}" for n, e in enumerate(shown, start=1)}
    marks: list[ServiceMark] = []
    for element in shown:
        shape = _shape(element)
        line: Path = (
            tuple(edit.fraction((x, y)) for x, y in shape.coords)
            if isinstance(shape, LineString)
            else ()
        )
        word = plain(element)
        marks.append(
            ServiceMark(
                ref=refs[element.guid],
                global_id=element.guid,
                kind=word,
                label=", ".join(filter(None, (word, element.size, *element.systems))),
                line=line,
                at=None if line else edit.fraction(element.at[:2]),
            )
        )
    return tuple(marks), refs

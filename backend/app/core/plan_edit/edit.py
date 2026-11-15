"""Plan edits as proposals: remove a wall between two rooms, place a room in a drawn region
(spec AC-17..AC-20). Pure geometry; nothing here writes a drawing."""

import shapely
from shapely.geometry import LineString, Polygon
from shapely.geometry.base import BaseGeometry

from app.core.plan_edit.model import Flag, Item, Proposal, RoomChange
from app.core.plan_edit.walls import REACH_M, PlanPage, PlanRoom, Wall, length_of, parts, walls_of

SNAP_M = 0.15  # a drawn side this close to a wall face moves onto it
PARTITION_M = 0.10  # a new wall's thickness
CLOSE_M = 0.01  # closes slivers left between a removed wall and the rooms
SLIVER_M2 = 0.05  # a leftover this small is a drawing slip, not a room part
CROSSES_M2 = 0.5  # a drawn region's piece past a wall bigger than this is not a slip of the hand
WET = {"bathroom", "wc", "sauna"}
NOT_TWO_SIDES = "these rooms are not on two sides of one inside wall"


class EditRefusedError(Exception):
    """The edit cannot be made on this plan; the message is the reason in plain words."""


def remove_wall(
    page: PlanPage,
    proposal_id: str,
    wall_id: str | None = None,
    rooms: tuple[str, str] | None = None,
) -> Proposal:
    """Merge the two rooms on the sides of one inside wall (by its id or by its two rooms)."""
    walls = walls_of(page)
    wall = _wall(walls, page, wall_id, rooms)
    by_id = {room.id: room for room in page.rooms}
    a, b = (by_id[rid] for rid in wall.rooms)
    if a.outdoor or b.outdoor:
        raise EditRefusedError(
            f"{NOT_TWO_SIDES}: {_outdoor(a, b).label} is outside, so this is the façade"
        )
    shapes = page.room_shapes()
    sa, sb = shapes[a.id], shapes[b.id]
    between = sa.buffer(REACH_M).intersection(sb.buffer(REACH_M)).difference(sa).difference(sb)
    doors = [o for o in page.openings if o.kind == "door" and o.id in wall.doors]
    # the door gap is not in the wall mass: it goes with the wall, or the merged room has a hole
    gap = shapely.unary_union([page.box_shape(d.box).intersection(between) for d in doors])
    removed = shapely.unary_union([wall.strip, gap])
    merged = shapely.unary_union([sa, sb, removed]).buffer(CLOSE_M).buffer(-CLOSE_M)
    pieces = parts(merged)
    if len(pieces) != 1:
        raise EditRefusedError(NOT_TWO_SIDES)
    after = pieces[0]
    label = f"{a.label} + {b.label}"
    flags = [_STRUCTURAL]
    if {a.type, b.type} & WET:
        flags.append(_WET)
    flags += _lost(page, label, [sa, sb], after, gone={d.id for d in doors})
    return Proposal(
        proposal_id=proposal_id,
        drawing_id=page.drawing_id,
        page=page.page,
        removed=(
            *_items(
                page,
                wall.id,
                removed,
                f"Wall {wall.id}, {wall.length_m} m, {wall.thickness_m} m thick",
            ),
            *(
                Item(
                    id=d.id,
                    polygon=page.ring(page.box_shape(d.box)),
                    label="door, no longer needed",
                )
                for d in doors
            ),
        ),
        rooms=(
            RoomChange(
                id=f"{a.id}+{b.id}",
                label=label,
                polygon=page.ring(after),
                area_before_m2=round(sa.area + sb.area, 2),
                area_after_m2=round(after.area, 2),
                was=(a.id, b.id),
            ),
        ),
        unknowns=(f"Whether wall {wall.id} is load-bearing: this drawing does not say.",),
        flags=tuple(flags),
    )


def place_room(
    page: PlanPage, proposal_id: str, region: tuple[float, float, float, float], name: str
) -> Proposal:
    """A new room in a drawn rectangle (page fractions): its sides snap to wall faces within
    0.15 m, it is clipped to the rooms, the rooms it covers shrink, and 0.10 m partitions close
    it where no wall is."""
    if region[2] <= region[0] or region[3] <= region[1]:  # a click or a sideways drag (robust-1)
        raise EditRefusedError(
            "the area drawn is a line, not an area: drag a rectangle over the room"
        )
    shapes = page.room_shapes()
    inside = shapely.unary_union(list(shapes.values()))
    faces = shapely.unary_union([s.boundary for s in shapes.values()] + [page.wall_mass().boundary])
    drawn = _snapped(page.box_shape(region), faces)
    pieces = parts(drawn.intersection(inside).buffer(CLOSE_M).buffer(-CLOSE_M))
    if not pieces:
        raise EditRefusedError("the area is outside the rooms")
    if pieces[0].area < CROSSES_M2:  # edits-4
        raise EditRefusedError(
            f"the area is too small for a room (under {CROSSES_M2} m²): draw a larger area"
        )
    if len(pieces) > 1 and pieces[1].area >= CROSSES_M2:
        raise EditRefusedError("the area crosses a wall into another room: draw it inside one room")
    region_m = pieces[0]
    lines = region_m.boundary.difference(faces.buffer(0.02))
    new_walls = lines.buffer(PARTITION_M / 2, cap_style="square").intersection(inside)
    room = region_m.difference(new_walls)
    room = parts(room)[0] if parts(room) else region_m
    taken = [r for r in page.rooms if shapes[r.id].intersection(region_m).area > CLOSE_M]
    changes = [
        RoomChange(
            id="N1",
            label=name,
            polygon=page.ring(room),
            area_before_m2=0.0,
            area_after_m2=round(room.area, 2),
            was=tuple(r.id for r in taken),
        )
    ]
    flags = _lost(page, name, [], room, gone=set())
    for host in taken:
        before = shapes[host.id]
        after = before.difference(region_m).difference(new_walls)
        changes += _shrunk(page, host, before, after, name)
        flags += _lost(page, _label(host), [before], after, gone=set())
    if any(r.type in WET for r in taken):
        flags.append(_WET)
    return Proposal(
        proposal_id=proposal_id,
        drawing_id=page.drawing_id,
        page=page.page,
        added=tuple(
            Item(
                id=f"NW{n}",
                polygon=page.ring(piece),
                label=f"New wall, {round(length_of(piece), 2)} m, {PARTITION_M:.2f} m thick",
            )
            for n, piece in enumerate(parts(new_walls), start=1)
        ),
        rooms=tuple(changes),
        flags=tuple(_unique(flags)),
    )


def _wall(
    walls: list[Wall], page: PlanPage, wall_id: str | None, rooms: tuple[str, str] | None
) -> Wall:
    known = {room.id for room in page.rooms}
    if wall_id is not None:
        found = next((w for w in walls if w.id == wall_id), None)
        if found is None:
            raise EditRefusedError(
                f"there is no inside wall {wall_id} on this page; list_walls gives them"
            )
        return found
    if rooms is None:
        raise EditRefusedError("name a wall or two rooms")
    missing = [rid for rid in rooms if rid not in known]
    if missing:
        raise EditRefusedError(f"there is no room {', '.join(missing)} on this page")
    found = next((w for w in walls if set(w.rooms) == set(rooms)), None)
    if found is None:
        raise EditRefusedError(NOT_TWO_SIDES)
    return found


def _snapped(drawn: Polygon, faces: BaseGeometry) -> Polygon:
    """Each side of an axis-aligned rectangle moves to the nearest parallel wall face within
    SNAP_M that runs along it. shortcut: axis-aligned faces only; a rotated plan does not snap."""
    x0, y0, x1, y1 = drawn.bounds
    segments = [
        seg for line in _lines(faces) for seg in zip(line.coords[:-1], line.coords[1:], strict=True)
    ]

    def near(value: float, vertical: bool, lo: float, hi: float) -> float:
        """value: the side's x (vertical) or y; lo..hi: its extent along the other axis."""
        faces = [
            (a[0], (a[1], b[1])) if vertical else (a[1], (a[0], b[0]))
            for a, b in segments
            if abs(a[0] - b[0] if vertical else a[1] - b[1]) <= 0.02  # parallel to the side
        ]
        found = [
            at
            for at, (s, e) in faces
            if abs(at - value) <= SNAP_M and max(s, e) >= lo and min(s, e) <= hi
        ]
        return min(found, key=lambda at: abs(at - value), default=value)

    return shapely.box(
        near(x0, True, y0, y1),
        near(y0, False, x0, x1),
        near(x1, True, y0, y1),
        near(y1, False, x0, x1),
    )


def _lines(geometry: BaseGeometry) -> list[LineString]:
    if isinstance(geometry, LineString):
        return [geometry]
    return [line for g in getattr(geometry, "geoms", ()) for line in _lines(g)]


def _shrunk(
    page: PlanPage, host: PlanRoom, before: Polygon, after: BaseGeometry, name: str
) -> list[RoomChange]:
    pieces = [piece for piece in parts(after) if piece.area >= SLIVER_M2]
    if not pieces:
        return [
            RoomChange(
                id=host.id,
                label=f"{_label(host)} (all of it taken by {name})",
                polygon=page.ring(before),
                area_before_m2=round(before.area, 2),
                area_after_m2=0.0,
                was=(host.id,),
            )
        ]
    return [
        RoomChange(
            id=host.id if n == 1 else f"{host.id}.{n}",
            label=_label(host) if len(pieces) == 1 else f"{_label(host)} (part {n})",
            polygon=page.ring(piece),
            area_before_m2=round(before.area, 2) if n == 1 else 0.0,
            area_after_m2=round(piece.area, 2),
            was=(host.id,),
        )
        for n, piece in enumerate(pieces, start=1)
    ]


def _lost(
    page: PlanPage, label: str, before: list[Polygon], after: BaseGeometry, gone: set[str]
) -> list[Flag]:
    """A room that had a door (or window) and has none after the edit; a new room without a door."""
    flags: list[Flag] = []
    for kind in ("door", "window"):
        openings = [o for o in page.openings if o.kind == kind and o.id not in gone]

        def near(shape: BaseGeometry) -> bool:
            reach = shape.buffer(REACH_M / 2)
            return any(page.box_shape(o.box).intersects(reach) for o in openings)  # noqa: B023

        had = any(near(s) for s in before) if before else kind == "door"
        if had and not near(after):
            flags.append(
                Flag(
                    code=f"no_{kind}",
                    text=f"{label} would have no {kind}{' left' if before else ''}.",
                )
            )
    return flags


def _items(page: PlanPage, wid: str, strip: BaseGeometry, label: str) -> list[Item]:
    """A strip in several pieces names each piece's part, as a room cut in two does."""
    pieces = parts(strip)
    return [
        Item(
            id=wid if n == 1 else f"{wid}.{n}",
            polygon=page.ring(piece),
            label=label if len(pieces) == 1 else f"{label} (part {n})",
        )
        for n, piece in enumerate(pieces, start=1)
    ]


def _outdoor(a: PlanRoom, b: PlanRoom) -> PlanRoom:
    return a if a.outdoor else b


def _label(room: PlanRoom) -> str:
    return room.label or room.id


def _unique(flags: list[Flag]) -> list[Flag]:
    return list({(f.code, f.text): f for f in flags}.values())


_STRUCTURAL = Flag(
    code="structural",
    text="Before removing a wall, a structural engineer has to confirm it does not carry load.",
)
_WET = Flag(code="wet_room", text="A wet room changes: its waterproofing is redone and inspected.")

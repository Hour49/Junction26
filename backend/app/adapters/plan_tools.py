"""Plan edits as tools for the agent chat (decision 0013, spec AC-12, AC-16..AC-21): OpenAI
function-calling JSON in `PLAN_TOOLS`, and `run_plan_tool(store, name, arguments)` that returns
JSON text and never raises, as `run_pipeline_tool` does.

    list_walls           the inside walls of one page with ids W1..Wn, and its rooms R-ids
    propose_remove_wall  merge the rooms on both sides of one wall (by wall id or two room ids)
    propose_room         a new room in the area the user drew (a region selection)

The model names ids only (walls, rooms, selections); the geometry comes from the drawing
(app/core/plan_edit). A proposal changes no drawing: the store collects it for the chat.
A plan that cannot be edited is `{"status": "cannot_edit" | "unknown", "reason": ...}`; an edit
the geometry refuses is `{"status": "refused", "reason": ...}`.
"""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import Field, ValidationError

# Private helpers of pipeline_tools, imported so both tool sets read a page and answer a bad
# call the same way.
from app.adapters.pipeline_tools import (
    PipelineStore,
    ToolError,
    _Args,  # pyright: ignore[reportPrivateUsage]
    _decoded,  # pyright: ignore[reportPrivateUsage]
    _done,  # pyright: ignore[reportPrivateUsage]
    _entry,  # pyright: ignore[reportPrivateUsage]
    _error,  # pyright: ignore[reportPrivateUsage]
    _fills,  # pyright: ignore[reportPrivateUsage]
    _tool,  # pyright: ignore[reportPrivateUsage]
    _why,  # pyright: ignore[reportPrivateUsage]
)
from app.core.drawing.model import Room
from app.core.errors import DomainError
from app.core.plan_edit.edit import EditRefusedError, place_room, remove_wall
from app.core.plan_edit.model import Proposal, Selection
from app.core.plan_edit.walls import Opening, PlanPage, PlanRoom, walls_of

log = logging.getLogger(__name__)


@dataclass
class PlanStore:
    """The project (through the pipeline store), this turn's selections by id, and the
    proposals the tools made (ids p1, p2... go on from the ones already there)."""

    pipeline: PipelineStore
    selections: dict[str, Selection] = field(default_factory=dict[str, Selection])
    proposals: list[Proposal] = field(default_factory=list[Proposal])

    @classmethod
    def of_app(
        cls, app: Any, project_id: str, selections: list[Selection] | tuple[Selection, ...] = ()
    ) -> "PlanStore":
        return cls(PipelineStore.of_app(app, project_id), {s.id: s for s in selections})

    def describe(self, selection: Selection) -> str:
        """The selection in one line for the model (AC-12), from the drawing's geometry."""
        try:
            name = _entry(_done(self.pipeline, self.pipeline.project_id), selection.drawing_id).name
        except (DomainError, ToolError):
            missing = f"drawing {selection.drawing_id}, which this project does not have"
            return f"{selection.id}: {selection.kind} on {missing}"
        where = f"{name} page {selection.page}"
        try:
            page = plan_page(self.pipeline, selection.drawing_id, selection.page)
        except (CannotEditError, DomainError, ToolError):
            page = None
        if selection.kind == "room":
            room = None if page is None else picked_room(page, selection)
            if page is not None and room is None and selection.ref is None:
                return f"{selection.id}: a click on {where} that is in no room"
            if room is None or page is None:
                return f"{selection.id}: room {selection.ref or '(not known)'} on {where}"
            area = page.shape(room.polygon).area
            return f"{selection.id}: room {room.id} {room.label} ({area:.2f} m²) on {where}"
        if page is None or selection.box is None:
            unsized = "its size is not known: the plan has no scale or rooms"
            return f"{selection.id}: region on {where} ({unsized})"
        region = page.box_shape(selection.box)
        x0, y0, x1, y1 = region.bounds
        shares = sorted(
            (
                (page.shape(r.polygon).intersection(region).area / region.area, r.label)
                for r in page.rooms
            ),
            reverse=True,
        )
        over = [f"{label} ({share:.0%})" for share, label in shares if share >= 0.01]
        overlaps = " and ".join(over) if over else "no room"
        size = f"about {x1 - x0:.1f} m by {y1 - y0:.1f} m"
        return f"{selection.id}: region on {where}, {size}, overlaps {overlaps}"


def picked_room(page: PlanPage, selection: Selection) -> PlanRoom | None:
    """A room selection's room: by its id, or (a click the browser could not hit-test, no
    `ref`) the room holding its box's centre. None: no such room."""
    if selection.ref is not None:
        return next((r for r in page.rooms if r.id == selection.ref), None)
    if selection.box is None:
        return None
    x0, y0, x1, y1 = selection.box
    return page.room_at((x0 + x1) / 2, (y0 + y1) / 2)


class CannotEditError(Exception):
    """This page cannot be edited by geometry; `status` and the reason go back to the model."""

    def __init__(self, status: str, reason: str) -> None:
        super().__init__(reason)
        self.status = status


def plan_page(store: PipelineStore, drawing_id: str, page: int) -> PlanPage:
    """One page of a drawing of the project as geometry in metres, or CannotEditError."""
    entry = _entry(_done(store, store.project_id), drawing_id)
    drawing = store.ingest.drawing(entry.drawing_id)
    if not drawing.pages:  # a bare building model: no sheet to draw an edit on
        raise CannotEditError("cannot_edit", "this building model has no drawn plan to edit")
    shown = next((p for p in drawing.pages if p.page == page), None)
    if shown is None:
        raise ToolError(f"drawing {drawing_id} has no page {page}")
    if entry.route == "raster":
        scan = "photo" if entry.kind == "photo_plan" else "scan"
        raise CannotEditError("cannot_edit", f"this plan is a {scan}: its walls are not geometry")
    m = drawing.scale.m_per_unit
    if m is None:
        raise CannotEditError("unknown", "this drawing has no scale")
    rooms = [r for r in drawing.rooms if r.page == page and r.polygon]
    if not rooms:
        raise CannotEditError("cannot_edit", "the rooms on this page have no outlines")
    fills = _fills(store, drawing, entry, page) or []
    mass = [(f.polygon, f.holes) for f in fills]
    if not mass and entry.route == "bim":  # a building model's sheet: its walls are sure
        walls = drawing.elements
        mass = [
            (e.polygon, ()) for e in walls if e.page == page and e.class_ == "wall" and e.polygon
        ]
    if not mass:
        raise CannotEditError("cannot_edit", "no walls are drawn as geometry on this page")
    return PlanPage(
        drawing_id=entry.drawing_id,
        page=page,
        width_m=shown.width * m,
        height_m=shown.height * m,
        rooms=tuple(PlanRoom(r.id, _label(r), r.type, r.polygon or (), r.outdoor) for r in rooms),
        mass=tuple(mass),
        openings=tuple(
            Opening(e.id, e.class_, e.box)
            for e in drawing.elements
            if e.page == page and e.class_ in ("door", "window")
        ),
    )


def _label(room: Room) -> str:
    """The room as the plan writes it: name and number ("Bagno 1.01")."""
    number = room.attrs.get("number")
    name = room.label or room.id
    return f"{name} {number}" if number and str(number) not in name else name


class _PageArgs(_Args):
    drawing_id: str = Field(
        pattern=r"^[0-9a-f]{16}$", description="a drawing id (16 hex characters) from list_drawings"
    )
    page: int = Field(ge=1, le=10_000, description="the page number, 1 for a single sheet")


class _RemoveArgs(_PageArgs):
    wall_id: str = Field(
        default="", pattern=r"^(W\d{1,4})?$", description="the wall's id from list_walls (W1...)"
    )
    room_a: str = Field(
        default="", max_length=32, description="or: one room's id from list_walls (with room_b)"
    )
    room_b: str = Field(default="", max_length=32, description="the room on the wall's other side")


class _RoomArgs(_Args):
    selection_id: str = Field(
        pattern=r"^sel_\d{1,4}$", description="the area the user drew on the plan (sel_1...)"
    )
    name: str = Field(min_length=1, max_length=60, description="the new room's name, e.g. Storage")


_TOOLS: list[tuple[str, str, type[_Args]]] = [
    (
        "list_walls",
        "The inside walls of one page of a drawing (ids W1...): the two rooms each separates, "
        "length, thickness, the doors in it, whether it is load-bearing (usually unknown), "
        "and the rooms of the page with their ids and areas. Use before proposing an edit.",
        _PageArgs,
    ),
    (
        "propose_remove_wall",
        "Propose removing one inside wall, merging the rooms on its two sides. Name the wall "
        "(wall_id) or its two rooms (room_a and room_b), ids from list_walls. Gives the merged "
        "room's area before and after, what is unknown and what to look out for. Changes no "
        "drawing: the person accepts or rejects the proposal.",
        _RemoveArgs,
    ),
    (
        "propose_room",
        "Propose a new room in the area the user drew on the plan (selection_id). Its sides "
        "snap to nearby walls, the rooms it covers shrink and new partitions close it. Changes "
        "no drawing: the person accepts or rejects the proposal.",
        _RoomArgs,
    ),
]
PLAN_TOOLS: list[dict[str, Any]] = [_tool(*tool) for tool in _TOOLS]
_MODELS: dict[str, type[_Args]] = {name: model for name, _, model in _TOOLS}


def run_plan_tool(store: PlanStore, name: str, arguments: str | dict[str, Any]) -> str:
    """Run the plan tool `name`; JSON text back. Never raises: a bad call is {"error": "..."}."""
    try:
        run = _RUNNERS.get(name)
        if run is None:
            raise ToolError(f"unknown tool {name!r}; the plan tools are {', '.join(_RUNNERS)}")
        args = _MODELS[name].model_validate(_decoded(arguments))
        return json.dumps(run(store, args), ensure_ascii=False)
    except json.JSONDecodeError as error:
        return _error(f"the arguments are not valid JSON ({error})")
    except ValidationError as error:
        return _error(f"bad arguments for {name}: {_why(error)}")
    except CannotEditError as error:
        return json.dumps({"status": error.status, "reason": str(error)}, ensure_ascii=False)
    except EditRefusedError as error:
        return json.dumps({"status": "refused", "reason": str(error)}, ensure_ascii=False)
    except ToolError as error:
        return _error(str(error))
    except DomainError as error:
        return _error(str(error) or type(error).__name__)
    except Exception as error:  # a bug: the model gets no internals, the server log the traceback
        log.exception("plan tool %s failed", name)
        return _error(f"{name} failed ({type(error).__name__})")


def _list_walls(store: PlanStore, args: Any) -> dict[str, Any]:
    page = plan_page(store.pipeline, args.drawing_id, args.page)
    labels = {room.id: room.label for room in page.rooms}
    return {
        "status": "ok",
        "drawing_id": page.drawing_id,
        "page": page.page,
        "walls": [
            {
                "id": wall.id,
                "rooms": [{"id": rid, "label": labels[rid]} for rid in wall.rooms],
                "length_m": wall.length_m,
                "thickness_m": wall.thickness_m,
                "page": page.page,
                "box": list(page.frame_box(wall.strip)),
                "doors": list(wall.doors),
                "load_bearing": "unknown",
                "load_bearing_source": None,
            }
            for wall in walls_of(page)
        ],
        "rooms": [
            {
                "id": room.id,
                "label": room.label,
                "type": room.type,
                "area_m2": round(page.shape(room.polygon).area, 2),
                "page": page.page,
                "box": list(page.frame_box(page.shape(room.polygon))),
            }
            for room in page.rooms
        ],
        "unknowns": ["Which walls are load-bearing: this drawing does not say."],
    }


def _remove_wall(store: PlanStore, args: Any) -> dict[str, Any]:
    if not args.wall_id and not (args.room_a and args.room_b):
        raise ToolError("name the wall (wall_id) or the rooms on its two sides (room_a and room_b)")
    page = plan_page(store.pipeline, args.drawing_id, args.page)
    rooms = None if args.wall_id else (args.room_a, args.room_b)
    return _proposed(store, remove_wall(page, _next_id(store), args.wall_id or None, rooms))


def _place_room(store: PlanStore, args: Any) -> dict[str, Any]:
    selection = store.selections.get(args.selection_id)
    if selection is None:
        known = ", ".join(store.selections) or "none this turn"
        raise ToolError(f"there is no selection {args.selection_id} (selections: {known})")
    page = plan_page(store.pipeline, selection.drawing_id, selection.page)
    if selection.kind == "room":
        room = picked_room(page, selection)
        picked = f"{room.id} {room.label}" if room else "a click in no room"
        raise EditRefusedError(
            f"a new room needs an area drawn on the plan; {selection.id} is {picked}"
        )
    if selection.box is None:
        raise ToolError(f"{selection.id} has no area")
    return _proposed(store, place_room(page, _next_id(store), selection.box, args.name))


def _next_id(store: PlanStore) -> str:
    return f"p{len(store.proposals) + 1}"


def _proposed(store: PlanStore, proposal: Proposal) -> dict[str, Any]:
    store.proposals.append(proposal)
    return {"status": "ok", "proposal": proposal.model_dump(mode="json")}


_RUNNERS: dict[str, Callable[[PlanStore, Any], dict[str, Any]]] = {
    "list_walls": _list_walls,
    "propose_remove_wall": _remove_wall,
    "propose_room": _place_room,
}

__all__ = ["PLAN_TOOLS", "PlanStore", "picked_room", "plan_page", "run_plan_tool"]

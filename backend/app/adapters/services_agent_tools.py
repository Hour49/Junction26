"""The services model as tools for the agent chat (spec services-model.md SV-22..SV-27, decision
0017), in decision 0013's tool form: OpenAI function-calling JSON in `SERVICES_TOOLS`, and
`run_services_tool(store, name, arguments)` that returns JSON text and never raises.

    list_services           storeys, systems, terminals and equipment; a room's walls
    ask_services            one graph operation of ops.py (what feeds, what is cut off, ...)
    propose_move_terminal   a terminal onto another wall of its room, rerouted (edit.py)
    propose_add_terminal    a copy of a terminal's type onto a wall
    propose_remove_element  a terminal and its branches
    propose_resize          an element to a size its system already has

The model names ids only (elements, walls, rooms, selections); a place in a result is the
storey's page (1 = lowest) and a box in page fractions (SV-6). A proposal changes no model: the
store keeps it (with its patch) for the chat, and the model reads a short view of it.
Not registered in agent_tools.py yet (waits for #333); `ServicesToolStore` is filled by the
caller with the model each drawing's chat edits (its source plus the accepted patches).
"""

import json
import logging
import re
from collections import Counter
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any, Literal, get_args

from pydantic import Field, ValidationError
from shapely.geometry import LineString, Point, Polygon

from app.adapters.pipeline_tools import (
    PipelineStore,
    ToolError,
    _Args,  # pyright: ignore[reportPrivateUsage]
    _decoded,  # pyright: ignore[reportPrivateUsage]
    _error,  # pyright: ignore[reportPrivateUsage]
    _tool,  # pyright: ignore[reportPrivateUsage]
    _why,  # pyright: ignore[reportPrivateUsage]
)
from app.adapters.plan_tools import ONE_AT_A_TIME
from app.adapters.service_tools import _models  # pyright: ignore[reportPrivateUsage]
from app.adapters.services_store import ServicesBuilds, ServicesStore
from app.core.errors import DomainError
from app.core.ingest.model import FileStatus
from app.core.plan_edit.model import Flag as PlanFlag
from app.core.plan_edit.model import Proposal, Selection
from app.core.services.derive import discipline_of, graph
from app.core.services.edit import (
    EditRefusedError,
    Position,
    ServicesChange,
    add_terminal,
    apply,
    move_terminal,
    remove_element,
    resize,
)
from app.core.services.ops import EQUIPMENT_CATEGORIES, EQUIPMENT_GROUPS, OPERATIONS, ask
from app.core.services.route import MAIN_NEAR_M, Edge, room_edges
from app.core.services.stored import Element, Point2, Room, ServicesModel, Storey, fraction

log = logging.getLogger(__name__)

LIMIT = 3900  # characters of one result (SV-23: under 4,000)
# what a person reads in the chat when a project's IFC files have no stored services model
NOT_READ = (
    "none of this project's IFC files has been read into a services model yet, so its pipes, "
    "ducts and cables cannot be followed"
)
MAX_ITEMS = 60
MAX_GROUPS = 30  # of each by_ count before a result is cut to LIMIT
NO_ROOMS = (
    "this services model has no rooms: its building model is missing or does not line up with it"
)
FROM_PICTURE = "a services model read from a picture is listed and counted, not edited"
BUILDING = "being built from its file now, which takes a minute or a few; ask again then"
# German exports name heating systems H_* (Heizung) or Heiz-/Wärme-: words facts_mep's table lacks
HEATING_MARKS = ("heiz", "wärme", "waerme")
WALL_COVER_M = 0.3  # a wall is on a room side when it covers this much of it (edit.py's rule)
MOUNTED_M = 0.5  # a terminal this close to a room side is mounted on its wall

Op = Literal[
    "terminals_served",
    "farthest_terminal",
    "feeds",
    "trace",
    "run_length",
    "controllers_between",
    "cut_off",
    "system_storeys",
    "systems_crossing_storeys",
    "open_ends",
    "unconnected",
    "circuit_of",
    "system_info",
]
assert set(get_args(Op)) == set(OPERATIONS), "Op must list ops.OPERATIONS"


class CannotEditError(Exception):
    """This model is not one an edit can run on (a picture, no rooms, no connections)."""


@dataclass
class ServicesToolStore:
    """The services model of each drawing (what this chat edits: its source plus the chat's
    accepted services patches), this turn's selections by id, and the chat's proposals: the plan
    tools' own list when the chat has them, so ids (p1, p2...) and one-per-turn hold for both.
    `accepted`: per drawing, the accepted services proposals its model is built on (SV-13)."""

    models: Mapping[str, ServicesModel]
    selections: dict[str, Selection] = field(default_factory=dict[str, Selection])
    proposals: list[Proposal] = field(default_factory=list[Proposal])
    project_id: str | None = None  # for the picture's path (SV-28)
    accepted: Mapping[str, tuple[str, ...]] = field(default_factory=dict[str, tuple[str, ...]])
    building: tuple[str, ...] = ()  # the models being built from their files now (SV-8)
    made_before: int = field(init=False, default=0)

    def __post_init__(self) -> None:
        self.made_before = len(self.proposals)

    def model(self, drawing_id: str) -> ServicesModel:
        try:
            found = self.models.get(drawing_id)
        except DomainError as error:  # the project could not be read
            raise ToolError(f"no services model: {error}") from error
        if found is None:
            if not self.models:  # an upload's IFC files have no model until one is built (SV-8)
                raise ToolError(f"{NOT_READ}{self.building_note()}")
            have = ", ".join(self.models)
            raise ToolError(
                f"drawing {drawing_id!r} has no services model; the project's services models: "
                f"{have}{self.building_note()}"
            )
        return found

    def building_note(self) -> str:
        """What is being built, for a tool that found no model: so "none" is not read as final."""
        return f"; {BUILDING}: {', '.join(self.building)}" if self.building else ""


class _ProjectModels(Mapping[str, ServicesModel]):
    """The stored services models of a project's IFC files by drawing id (the files #333's
    follow-up reads, `service_tools._models`), each with the chat's accepted services patches
    applied in proposal order. Read when first asked for, never built here (SV-8: models are built
    off the request by `ServicesBuilds` or by `python -m app.cli services build`)."""

    def __init__(
        self, pipeline: PipelineStore, cache: ServicesStore, accepted: list[Proposal]
    ) -> None:
        self._pipeline, self._cache, self._accepted = pipeline, cache, accepted
        self._sha: dict[str, str] | None = None
        self._read: dict[str, ServicesModel | None] = {}

    def _files(self) -> dict[str, str]:
        if self._sha is None:
            self._sha = _project_files(self._pipeline)
        return self._sha

    def __getitem__(self, drawing_id: str) -> ServicesModel:
        if drawing_id not in self._read:
            sha256 = self._files().get(drawing_id)
            model = None if sha256 is None else self._cache.load(sha256)
            for proposal in self._accepted:
                if model is not None and proposal.drawing_id == drawing_id:
                    assert proposal.services_change is not None
                    model = apply(model, proposal.services_change.patch)
            self._read[drawing_id] = model
        found = self._read[drawing_id]
        if found is None:
            raise KeyError(drawing_id)
        return found

    def __iter__(self) -> Iterator[str]:
        """The drawings with a stored model, from the files that exist: none is read."""
        return iter(d for d, sha256 in self._files().items() if self._cache.path(sha256).is_file())

    def __len__(self) -> int:
        return sum(1 for _ in self)


def model_id(file: FileStatus) -> str | None:
    """The id a services model goes by: its file's drawing id, else (an IFC set aside at upload,
    which has no drawing) the first 16 characters of its sha256, the same shape as a drawing id."""
    return file.drawing_id or (file.sha256[:16] if file.sha256 else None)


def _project_files(pipeline: PipelineStore) -> dict[str, str]:
    """Model id -> sha256 of the project's IFC files (`service_tools._models`), drawn or not."""
    files, _ = _models(pipeline.ingest.status(pipeline.project_id), None)
    return {i: f.sha256 for f in files if (i := model_id(f)) and f.sha256}


def offers_services(pipeline: PipelineStore) -> bool:
    """Whether a chat turn offers the services tools: SERVICES_FOLLOW is on (the services flag,
    decision 0016) and the project has an IFC file a services model can be stored for."""
    return pipeline.settings.services_follow == "on" and bool(_project_files(pipeline))


def project_services(
    pipeline: PipelineStore,
    selections: Sequence[Selection],
    proposals: list[Proposal],
    chat: Mapping[str, Proposal],
    builds: ServicesBuilds | None = None,
) -> ServicesToolStore:
    """The services tools' store for one chat turn: the project's stored models plus the chat's
    accepted services proposals (`chat`), sharing `proposals` with the plan tools. `builds`:
    a file of the project with no stored model starts its build (SV-8), and the tools say it is
    being built; None: none is built here."""
    accepted = sorted(
        (p for p in chat.values() if p.state == "accepted" and p.services_change is not None),
        key=lambda p: int(p.proposal_id[1:]) if p.proposal_id[1:].isdigit() else 0,
    )
    by_drawing: dict[str, tuple[str, ...]] = {}
    for p in accepted:
        by_drawing[p.drawing_id] = (*by_drawing.get(p.drawing_id, ()), p.proposal_id)
    models = _ProjectModels(pipeline, ServicesStore(pipeline.settings.services_cache_dir), accepted)
    return ServicesToolStore(
        models,
        {s.id: s for s in selections},
        proposals,
        project_id=pipeline.project_id,
        accepted=by_drawing,
        building=() if builds is None else _building(pipeline, builds),
    )


def _building(pipeline: PipelineStore, builds: ServicesBuilds) -> tuple[str, ...]:
    """The ids of the project's model files whose services model is being built, each missing
    one's build started. A file read as a model listing no wall, door, window or room (a
    services model) starts first, an architecture model (one listing some) last; with exactly
    one architecture model in the project, every other build gets it for its rooms and walls
    (#475 review S2, C1). Never raises: the tools then say what they find, as before."""
    try:
        files, _ = _models(pipeline.ingest.status(pipeline.project_id), None)
        listed = {f.id: _listed(pipeline, f) for f in files}
        plans = [f for f in files if listed[f.id]]
        arc = _bytes_of(pipeline, plans[0].id) if len(plans) == 1 else None
        first = sorted(files, key=lambda f: 0 if listed[f.id] == () else 2 if listed[f.id] else 1)
        return tuple(
            i
            for f in first
            if (i := model_id(f))
            and f.sha256
            and builds.building(
                f.sha256,
                PurePosixPath(f.path).name,
                _bytes_of(pipeline, f.id),
                None if listed[f.id] else arc,
            )
        )
    except Exception:
        log.warning("services models not started", exc_info=True)
        return ()


def _listed(pipeline: PipelineStore, file: FileStatus) -> tuple[object, ...] | None:
    """The plan objects (walls, doors, windows, spaces) the file's model drawing lists; None: no
    drawing read (set aside at upload, or not readable now)."""
    if file.drawing_id is None:
        return None
    try:
        return pipeline.ingest.drawing(file.drawing_id).model_objects
    except DomainError:
        return None


def _bytes_of(pipeline: PipelineStore, file_id: str) -> Callable[[], bytes]:
    """The file's bytes, read only when a build runs."""
    return lambda: pipeline.ingest.upload_bytes(pipeline.project_id, file_id)


@dataclass(frozen=True)
class Resolved:
    """A selection on a storey picture (SV-22): the room it is in, the nearest wall of that room
    and the point (model metres) the person meant."""

    room_id: str
    wall_id: str | None
    point: Point2


def resolve_selection(model: ServicesModel, selection: Selection) -> Resolved | None:
    """The room, nearest wall and point of a region the person drew on a storey's picture
    (`selection.page` is the storey's ordinal); None when it is on no storey or in no room."""
    storeys = _storeys(model)
    if selection.box is None or not 1 <= selection.page <= len(storeys):
        return None
    storey = storeys[selection.page - 1]
    x0, y0, x1, y1 = storey.frame_m
    fx, fy = (selection.box[0] + selection.box[2]) / 2, (selection.box[1] + selection.box[3]) / 2
    point = (x0 + fx * (x1 - x0), y1 - fy * (y1 - y0))
    here = Point(point)
    room = next(
        (
            r
            for r in model.rooms
            if r.storey == storey.id and Polygon(r.polygon).buffer(0.05).contains(here)
        ),
        None,
    )
    if room is None:
        return None
    walls = [w for w in model.walls if room.id in w.rooms]
    wall = min(walls, key=lambda w: Polygon(w.polygon).distance(here), default=None)
    return Resolved(room.id, wall.id if wall else None, point)


# --- arguments and schemas ------------------------------------------------------------------

_ID = r"^[A-Z]{1,2}\d{1,6}$"


class _DrawingArgs(_Args):
    drawing_id: str = Field(min_length=1, max_length=64, description="the services model's drawing")


class _ListArgs(_Args):
    drawing_id: str | None = Field(
        default=None,
        max_length=64,
        description="the services model's drawing (default: the only one)",
    )
    storey: str | None = Field(default=None, max_length=60, description="storey id (L1...) or name")
    system: str | None = Field(default=None, max_length=120, description="a system's name")
    room_id: str | None = Field(
        default=None,
        max_length=80,
        description="a room: its id (SR...) or its name, e.g. 1-3 Küche",
    )
    kind: str | None = Field(default=None, max_length=60, description="a by_kind key; narrows all")
    predefined: str | None = Field(
        default=None, max_length=40, description="a by_predefined key (IFC type)"
    )
    selection_id: str | None = Field(
        default=None, pattern=r"^sel_\d{1,4}$", description="or: the room the user drew in"
    )


class _AskArgs(_DrawingArgs):
    op: Op
    element_id: str | None = Field(default=None, pattern=_ID)
    to_element_id: str | None = Field(default=None, pattern=_ID)
    system: str | None = Field(default=None, max_length=120)
    storey: str | None = Field(default=None, max_length=60)
    kind: str | None = Field(default=None, max_length=60)
    size: str | None = Field(default=None, max_length=30)


class _PlaceArgs(_DrawingArgs):
    wall_id: str | None = Field(default=None, pattern=r"^SW\d{1,5}$", description="a wall (SW...)")
    selection_id: str | None = Field(
        default=None, pattern=r"^sel_\d{1,4}$", description="or: where the user drew (sel_1...)"
    )
    position: Literal["centre", "start", "end", "under_window"] = "centre"


class _MoveArgs(_PlaceArgs):
    element_id: str = Field(pattern=_ID, description="the terminal (E...)")


class _AddArgs(_PlaceArgs):
    like_element_id: str = Field(pattern=_ID, description="a terminal whose type is copied")


class _RemoveArgs(_DrawingArgs):
    element_id: str = Field(pattern=_ID, description="the terminal (E...)")


class _ResizeArgs(_DrawingArgs):
    element_id: str = Field(pattern=_ID)
    size: str = Field(min_length=1, max_length=30, description="a size its system has, e.g. DN20")


_CHANGES = " Changes nothing until accepted."
_TOOLS: list[tuple[str, str, type[_Args]]] = [
    (
        "list_services",
        "Pipes, ducts, cables: storeys, systems, connectivity, terminals and equipment "
        "(ids E...) with room. count, by_kind, by_predefined, by_type, by_room: all matches (items "
        "may be cut); state totals and breakdowns from them. room_id (id or name): its "
        "walls (SW...), what hangs on them, if a pipe is in reach. Use before proposing.",
        _ListArgs,
    ),
    (
        "ask_services",
        "What feeds an element, what it serves, what is cut off when it closes, run lengths, "
        "open ends, ...",
        _AskArgs,
    ),
    (
        "propose_move_terminal",
        "Propose moving a terminal (radiator, air terminal) to another wall of its room "
        "(wall_id or selection_id), pipes rerouted along walls." + _CHANGES,
        _MoveArgs,
    ),
    (
        "propose_add_terminal",
        "Propose a new terminal of the same type as like_element_id on a wall (wall_id or "
        "selection_id), connected to the nearest pipe of its system." + _CHANGES,
        _AddArgs,
    ),
    (
        "propose_remove_element",
        "Propose removing a terminal with its connecting pipes." + _CHANGES,
        _RemoveArgs,
    ),
    (
        "propose_resize",
        "Propose another size for a pipe or duct, one its system already has." + _CHANGES,
        _ResizeArgs,
    ),
]
SERVICES_TOOLS: list[dict[str, Any]] = [_tool(*tool) for tool in _TOOLS]
_MODELS: dict[str, type[_Args]] = {name: model for name, _, model in _TOOLS}


def run_services_tool(store: ServicesToolStore, name: str, arguments: str | dict[str, Any]) -> str:
    """Run the services tool `name`; JSON text back. Never raises: a bad call is {"error": ...}."""
    try:
        run = _RUNNERS.get(name)
        if run is None:
            raise ToolError(f"unknown tool {name!r}; the tools are {', '.join(_RUNNERS)}")
        args = _MODELS[name].model_validate(_decoded(arguments))
        return _short(run(store, args))
    except json.JSONDecodeError as error:
        return _error(f"the arguments are not valid JSON ({error})")
    except ValidationError as error:
        return _error(f"bad arguments for {name}: {_why(error)}"[:LIMIT])
    except CannotEditError as error:
        return json.dumps({"status": "cannot_edit", "reason": str(error)}, ensure_ascii=False)
    except EditRefusedError as error:
        return json.dumps({"status": "refused", "reason": str(error)}, ensure_ascii=False)
    except ToolError as error:
        return _error(str(error)[:LIMIT])
    except Exception as error:  # a tool never raises; the log has the trace
        log.exception("services tool %s failed", name)
        return _error(f"{name} failed ({type(error).__name__})")


# --- the tools ------------------------------------------------------------------------------


def _list(store: ServicesToolStore, args: Any) -> dict[str, Any]:
    if args.drawing_id is None:  # the project's only model: a set-aside IFC is in no drawing list
        have = list(store.models)
        if not have:
            raise ToolError(f"{NOT_READ}{store.building_note()}")
        if len(have) != 1:
            raise ToolError(
                f"name the drawing_id; the project's services models: {', '.join(have)}"
                f"{store.building_note()}"
            )
        args = args.model_copy(update={"drawing_id": have[0]})
    model = store.model(args.drawing_id)
    pages = {s.id: i for i, s in enumerate(_storeys(model), 1)}
    storey = _storey_of(model, args.storey) if args.storey else None
    room = _room_named(model, args.room_id) if args.room_id else None
    if args.selection_id and room is None:  # SV-22: the selection's room, else its storey
        selection = _selection(store, args.drawing_id, args.selection_id)
        resolved = resolve_selection(model, selection)
        if resolved is not None:
            room = _room(model, resolved.room_id)
        elif storey is None and 1 <= selection.page <= len(pages):
            storey = _storeys(model)[selection.page - 1]
    systems = _systems(model)
    found: dict[str, Any] = {
        "drawing_id": args.drawing_id,
        "storeys": [{"id": s.id, "name": s.name, "page": pages[s.id]} for s in _storeys(model)],
        "connectivity": model.connectivity.model_dump(mode="json"),
        "systems": systems[:10],
        "systems_more": max(0, len(systems) - 10),
    }
    if room is not None:
        found |= _walls(model, room)
    names = {r.id: r.name for r in model.rooms}
    matched = [
        e
        for e in model.elements
        if (e.group == "flow_terminal" or _equipment(e))
        and (storey is None or e.storey == storey.id)
        and (args.system is None or args.system in e.systems)
        and (room is None or e.room == room.id)
        and (args.kind is None or args.kind in (e.kind, e.group))
    ]
    if args.predefined is not None:  # R5: a WC, a basin and its frame are one IFC class
        found["untyped"] = sum(e.predefined is None for e in matched)
        matched = [e for e in matched if (e.predefined or "").upper() == args.predefined.upper()]
    items = [
        {
            "id": e.id,
            "kind": e.kind,
            "label": e.label[:40],
            "room": e.room,
            "room_name": names.get(e.room or ""),
            "system": e.systems[0] if e.systems else None,
            "page": pages.get(e.storey or ""),
            "box": _box(model, e),
        }
        for e in matched
    ]
    found["count"] = len(items)
    found["items"], found["more"] = items[:MAX_ITEMS], max(0, len(items) - MAX_ITEMS)
    kinds, types = Counter(e.kind for e in matched), Counter(e.type for e in matched)
    predefined = Counter(e.predefined or "untyped" for e in matched)
    rooms = Counter(f"{e.room} {names.get(e.room, '')}".strip() if e.room else "no room"
                    for e in matched)  # fmt: skip
    top = MAX_GROUPS
    while True:  # the groups count every match: items go first, then the smallest groups
        found["by_kind"], found["by_type"] = _groups(kinds, top), _groups(types, top)
        found["by_predefined"] = _groups(predefined, top)
        found["by_room"] = _groups(rooms, top)
        short = len(json.dumps(found, ensure_ascii=False)) <= LIMIT
        if short or (top == 1 and not found["items"]):
            break
        if found["items"]:
            found["items"].pop()
            found["more"] += 1
        else:
            top //= 2
    return found


def _groups(counts: Counter[str], top: int) -> dict[str, int]:
    """The `top` largest groups, the rest summed under "and K more groups"."""
    kept = dict(counts.most_common(top))
    if len(counts) > top:
        kept[f"and {len(counts) - top} more groups"] = sum(counts.values()) - sum(kept.values())
    return kept


def _ask(store: ServicesToolStore, args: Any) -> dict[str, Any]:
    model = store.model(args.drawing_id)
    given = args.model_dump(exclude={"drawing_id", "op"}, exclude_none=True)
    answer = ask(graph(model), args.op, **given)
    by_id = {e.id: e for e in model.elements}
    pages = {s.id: i for i, s in enumerate(_storeys(model), 1)}
    elements = [
        {"id": i, "page": pages.get(by_id[i].storey or ""), "box": _box(model, by_id[i])}
        for i in answer.get("elements") or []
        if i in by_id
    ]
    return (
        {"drawing_id": args.drawing_id, **answer, "elements": elements}
        if elements
        else {
            "drawing_id": args.drawing_id,
            **answer,
        }
    )


def _move(store: ServicesToolStore, args: Any) -> dict[str, Any]:
    model = _editable(store, args.drawing_id, rooms=True)
    wall_id, position, _ = _place(store, model, args)
    return _proposed(
        store, args.drawing_id, move_terminal(model, args.element_id, wall_id, position)
    )


def _add(store: ServicesToolStore, args: Any) -> dict[str, Any]:
    model = _editable(store, args.drawing_id, rooms=True)
    wall_id, position, room_id = _place(store, model, args)
    change = add_terminal(model, args.like_element_id, wall_id, position, room_id=room_id)
    return _proposed(store, args.drawing_id, change)


def _remove(store: ServicesToolStore, args: Any) -> dict[str, Any]:
    model = _editable(store, args.drawing_id, rooms=False)
    return _proposed(store, args.drawing_id, remove_element(model, args.element_id))


def _resize(store: ServicesToolStore, args: Any) -> dict[str, Any]:
    model = _editable(store, args.drawing_id, rooms=False)
    return _proposed(store, args.drawing_id, resize(model, args.element_id, args.size))


_RUNNERS: dict[str, Callable[[ServicesToolStore, Any], dict[str, Any]]] = {
    "list_services": _list,
    "ask_services": _ask,
    "propose_move_terminal": _move,
    "propose_add_terminal": _add,
    "propose_remove_element": _remove,
    "propose_resize": _resize,
}


# --- helpers --------------------------------------------------------------------------------


def _editable(store: ServicesToolStore, drawing_id: str, rooms: bool) -> ServicesModel:
    """The drawing's model when an edit can run on it (SV-25), and this turn's first proposal."""
    model = store.model(drawing_id)
    if model.source.kind == "picture":
        raise CannotEditError(FROM_PICTURE)
    if model.connectivity.state == "none":
        raise CannotEditError(model.connectivity.reason or "the model has no port connections")
    if rooms and not model.rooms:
        raise CannotEditError(NO_ROOMS)
    if len(store.proposals) > store.made_before:
        raise EditRefusedError(ONE_AT_A_TIME)
    return model


def _place(
    store: ServicesToolStore, model: ServicesModel, args: Any
) -> tuple[str, Position, str | None]:
    """The wall, position and room an edit goes to: a wall id with a position word, or the
    user's selection (its nearest wall and the point)."""
    if args.selection_id:
        found = resolve_selection(model, _selection(store, args.drawing_id, args.selection_id))
        if found is None or found.wall_id is None:
            raise ToolError(f"{args.selection_id} is in no room of this services model")
        return found.wall_id, found.point, found.room_id
    if not args.wall_id:
        raise ToolError(
            "name the wall (wall_id, from list_services with room_id) or a selection_id"
        )
    return args.wall_id, args.position, None


def _selection(store: ServicesToolStore, drawing_id: str, selection_id: str) -> Selection:
    selection = store.selections.get(selection_id)
    if selection is None:
        raise ToolError(f"no selection {selection_id} in this turn")
    if selection.drawing_id != drawing_id:
        raise ToolError(f"{selection_id} is on another drawing, not {drawing_id}")
    return selection


def _proposed(store: ServicesToolStore, drawing_id: str, change: ServicesChange) -> dict[str, Any]:
    """Keep the proposal (with its patch) and give the model a short view of it."""
    page = next(
        (i for i, s in enumerate(_storeys(store.model(drawing_id)), 1) if s.id == change.storey), 1
    )
    storey = change.storey or ""
    picture = (
        f"/api/projects/{store.project_id}/drawings/{drawing_id}/services/{storey}.png"
        if store.project_id
        else None
    )
    change = change.model_copy(
        update={"based_on": store.accepted.get(drawing_id, ()), "picture": picture}
    )
    proposal = Proposal(
        proposal_id=f"p{len(store.proposals) + 1}",
        drawing_id=drawing_id,
        page=page,
        unknowns=change.unknowns,
        flags=tuple(PlanFlag(code=f.code, text=f.text) for f in change.flags),
        services_change=change,
    )
    store.proposals.append(proposal)
    shown = change.model_dump(mode="json", by_alias=True, exclude={"patch", "removed", "added"})
    shown["facts"] = shown["facts"][:12]
    for moved in shown["moved"]:
        moved.pop("to_m", None)  # the model reads places as page fractions only
    added_m = sum(e.length_m or 0 for e in change.patch.added)
    return {
        "status": "ok",
        "proposal": {
            "proposal_id": proposal.proposal_id,
            "drawing_id": drawing_id,
            "page": page,
            **shown,
            "removed": {"count": len(change.removed), "ids": [r.id for r in change.removed][:10]},
            "added": {"count": len(change.added), "length_m": round(added_m, 2)},
        },
    }


def _short(found: dict[str, Any]) -> str:
    text = json.dumps(found, ensure_ascii=False)
    if len(text) <= LIMIT:
        return text
    trimmed = {k: v for k, v in found.items() if not isinstance(v, list)}  # keep the scalars
    return json.dumps({**trimmed, "cut": "the result was too long; ask narrower"})[:LIMIT]


def _storeys(model: ServicesModel) -> list[Storey]:
    return sorted(model.storeys, key=lambda s: s.elevation_m)


def _storey_of(model: ServicesModel, name: str) -> Storey:
    found = next(
        (s for s in model.storeys if name in (s.id, s.name) or s.name.lower() == name.lower()), None
    )
    if found is None:
        raise ToolError(
            f"no storey {name!r}; the storeys are {', '.join(s.id for s in model.storeys)}"
        )
    return found


def _room(model: ServicesModel, room_id: str) -> Room:
    found = next((r for r in model.rooms if r.id == room_id), None)
    if found is None:
        raise ToolError(f"no room {room_id} in this services model")
    return found


def _room_named(model: ServicesModel, named: str) -> Room:
    """The room an id or a name gives, in any case and word order ("küche 1-3" is "1-3 Küche");
    else the one room whose name holds all its words. Several, or none: said, with the rooms."""
    by_id = next((r for r in model.rooms if r.id.casefold() == named.strip().casefold()), None)
    if by_id is not None:
        return by_id
    asked = set(_room_words(named))
    exact = [r for r in model.rooms if set(_room_words(r.name)) == asked]
    found = exact or [r for r in model.rooms if asked and asked <= set(_room_words(r.name))]
    if len(found) == 1:
        return found[0]
    if found:
        listed = "; ".join(f"{r.id} {r.name!r}" for r in found[:10])
        raise ToolError(f"{len(found)} rooms match {named!r}: {listed}; name one by its id")
    some = "; ".join(f"{r.id} {r.name!r}" for r in model.rooms[:15]) or "none"
    raise ToolError(f"no room named {named!r} in this services model; its rooms: {some}")


def _room_words(text: str) -> list[str]:
    return [w for w in re.findall(r"\w+", text.casefold()) if w != "the"]


def _equipment(e: Element) -> bool:
    return (
        e.group in EQUIPMENT_GROUPS
        or e.kind.startswith("electric_distribution")
        or e.category in EQUIPMENT_CATEGORIES
    )


def _systems(model: ServicesModel) -> list[dict[str, Any]]:
    by: dict[str, list[Element]] = {}
    for e in model.elements:
        for name in e.systems:
            by.setdefault(name, []).append(e)
    types = {s.name: s.type for s in model.systems}
    return [
        {
            "name": name,
            "discipline": _discipline(f"{name} {types.get(name, '')}", members),
            "elements": len(members),
            "length_m": round(sum(e.length_m or 0 for e in members), 2),
        }
        for name, members in sorted(by.items())
    ]


def _discipline(words: str, members: list[Element]) -> str:
    """A system's own name and type first; its members' (mostly pipes, read as plumbing) last."""
    words = words.lower()
    if words.startswith("h_") or any(mark in words for mark in HEATING_MARKS):
        return "heating"
    said = discipline_of(words)
    if said != "other":
        return said
    return max({e.discipline for e in members}, key=[e.discipline for e in members].count)


def _walls(model: ServicesModel, room: Room) -> dict[str, Any]:
    """SV-23 with a room: each wall on a side of it, its length, free length (less doors and
    what hangs on it), its openings and mounted terminals; and whether a main is in reach."""
    edges = room_edges(room.polygon)
    terminals = [e for e in model.elements if e.group == "flow_terminal" and e.room == room.id]
    walls: list[dict[str, Any]] = []
    for wall in (w for w in model.walls if room.id in w.rooms):
        area = Polygon(wall.polygon).buffer(0.1)
        cover = [edge.line.intersection(area).length for edge in edges]
        best = max(range(len(edges)), key=cover.__getitem__)
        if cover[best] < WALL_COVER_M:
            continue
        line = edges[best].line
        openings = [
            o
            for o in model.openings
            if o.storey == room.storey
            and (o.wall == wall.id or LineString(o.segment).distance(line) < 0.4)
        ]
        mounted = [e.id for e in terminals if _on_side(edges, e, best)]
        taken = sum(LineString(o.segment).length for o in openings if o.kind == "door")
        taken += sum((e.body_m or (0.6,))[0] for e in terminals if e.id in mounted)
        walls.append(
            {
                "id": wall.id,
                "length_m": round(line.length, 2),
                "free_m": round(max(0.0, line.length - taken), 2),
                "openings": [o.kind for o in openings],
                "mounted": mounted,
            }
        )
    shape = Polygon(room.polygon)
    reach = any(
        e.group == "flow_segment"
        and e.storey == room.storey
        and e.path is not None
        and len(e.path) == 2
        and shape.distance(LineString([p[:2] for p in e.path])) <= MAIN_NEAR_M
        for e in model.elements
    )
    return {"room": {"id": room.id, "name": room.name}, "walls": walls, "main_in_reach": reach}


def _on_side(edges: list[Edge], e: Element, side: int) -> bool:
    """A terminal hangs on that side of its room: the nearest side, and close to it."""
    if e.at is None:
        return False
    at = Point(e.at[0], e.at[1])
    nearest = min(range(len(edges)), key=lambda i: edges[i].line.distance(at))
    return nearest == side and edges[side].line.distance(at) <= MOUNTED_M


def _box(model: ServicesModel, e: Element) -> tuple[float, float, float, float] | None:
    """The element's box in its storey's page fractions (a point gets 0.3 m around it)."""
    storey = next((s for s in model.storeys if s.id == e.storey), None)
    points = list(e.path or ()) or ([e.at] if e.at is not None else [])
    if storey is None or not points:
        return None
    pad = 0.3
    corners = [
        fraction(storey, (p[0] + dx, p[1] + dy))
        for p in points
        for dx in (-pad, pad)
        for dy in (-pad, pad)
    ]
    xs, ys = (
        [min(max(c[0], 0.0), 1.0) for c in corners],
        [min(max(c[1], 0.0), 1.0) for c in corners],
    )
    return (round(min(xs), 3), round(min(ys), 3), round(max(xs), 3), round(max(ys), 3))


__all__ = [
    "SERVICES_TOOLS",
    "Resolved",
    "ServicesToolStore",
    "project_services",
    "resolve_selection",
    "run_services_tool",
]

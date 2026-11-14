"""The pipeline as tools for an agent chat (board #222, Tudor's agent-chat orchestrator): OpenAI
function-calling JSON in `PIPELINE_TOOLS`, and `run_pipeline_tool(store, name, arguments_json)`
that runs one and returns JSON text. It never raises: a bad call (unknown tool, malformed or
missing arguments, an unknown project, a project still running) is `{"error": "..."}` for the
model to read and correct.

Each tool calls the code the HTTP route calls, so the numbers are the routes' numbers:

    list_drawings   GET  /api/projects/{id}                 (+ each file's triage)
    ask_drawings    POST /api/projects/{id}/ask             (spends what a question spends)
    get_takeoff     GET  /api/drawings/{id}/takeoff?project={id}
    list_conflicts  GET  /api/projects/{id}/review          (its `conflicts`)
    list_issues     GET  /api/projects/{id}/issues
    run_checks      GET  /api/projects/{id}/checks?pack=
    get_plan_geometry  the drawing model's plans, rooms, openings and walls on one page

The names are provisional (the chat side posts the final list); renaming is a change of `NAME`
in `TOOLS`. No tool but `ask_drawings` can spend money, and that one goes through the same spend
guard as the route.
"""

import json
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from app.api.checks import checks_of, find_pack
from app.api.deps import Ingest
from app.api.issues import issues_of
from app.api.project_ask import ProjectAskRequest, project_ask
from app.api.projects import review_of
from app.api.takeoff import takeoff_rows
from app.api.views import DrawingEntry, drawings_of
from app.composition import Answering
from app.core.checks.model import RulePack
from app.core.drawing.model import Drawing
from app.core.errors import DomainError
from app.core.ingest.model import FileStatus, ProjectStatus
from app.core.review.ports import ReviewStore
from app.settings import Settings

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class PipelineStore:
    """The services the routes get from `app.state`, held together for the tools."""

    ingest: Ingest
    reviews: ReviewStore
    settings: Settings
    answering: Answering
    packs: tuple[RulePack, ...] = ()

    @classmethod
    def of_app(cls, app: Any) -> "PipelineStore":
        """From a FastAPI app (`create_app()`'s state)."""
        state = app.state
        return cls(state.ingest, state.reviews, state.settings, state.answering, state.rule_packs)


def _string(description: str) -> dict[str, str]:
    return {"type": "string", "description": description}


def _tool(name: str, description: str, **properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": list(properties),
                "additionalProperties": False,
            },
        },
    }


PROJECT = _string("the project id (12 hex characters) from list_drawings or the chat's context")
DRAWING = _string("a drawing id (16 hex characters) from list_drawings")

PIPELINE_TOOLS: list[dict[str, Any]] = [
    _tool(
        "list_drawings",
        "The drawings of a project: id, file name, kind, read state, page count and, for a file "
        "that is not a floor plan, what triage thinks it shows and whether it belongs.",
        project_id=PROJECT,
    ),
    _tool(
        "ask_drawings",
        "Ask a question (e.g. 'how many doors are there?') on every drawing of a project. Gives "
        "each drawing's answer with its evidence (page and box), whether it is sure or needs a "
        "double-check, the drawings that refused and why, and a total only when the drawings "
        "show different parts of the building (why_no_total says why not).",
        project_id=PROJECT,
        question=_string("the question in plain words"),
    ),
    _tool(
        "get_takeoff",
        "The quantities read from one drawing (counts, areas, lengths), each with its marks on "
        "the page, how it was measured and, where two methods disagree, the conflict with the "
        "position of each method's items.",
        project_id=PROJECT,
        drawing_id=DRAWING,
    ),
    _tool(
        "list_conflicts",
        "Every conflict of a project: a quantity two methods measured differently, with each "
        "method's value and whether a rule, a person or nobody settled it.",
        project_id=PROJECT,
    ),
    _tool(
        "list_issues",
        "Everything in a project that needs a person's look: conflicts, reading flags, files set "
        "aside, refused questions. Each is located on a page when it has a place.",
        project_id=PROJECT,
    ),
    _tool(
        "run_checks",
        "Check a project's drawings against a building-code rule pack. Each rule result names "
        "the clause it comes from. A pre-check, not a compliance certificate.",
        project_id=PROJECT,
        pack=_string("the rule pack id"),
    ),
    _tool(
        "get_plan_geometry",
        "Where things are on one page of a drawing, in page fractions (0-1, x then y, from the "
        "top left): the plan frame, scale, rooms, openings (doors, windows) and walls. A part "
        "the drawing's reader does not give is null with the reason.",
        project_id=PROJECT,
        drawing_id=DRAWING,
        page=_string("the page number, 1 for a single sheet"),
    ),
]


class ToolError(Exception):
    """A call the tool refuses, with the sentence the model reads."""


def run_pipeline_tool(store: PipelineStore, name: str, arguments_json: str) -> str:
    """Run the tool `name` with JSON `arguments_json`; JSON text back. Never raises."""
    try:
        run = _RUNNERS.get(name)
        if run is None:
            raise ToolError(f"unknown tool {name!r}; the tools are {', '.join(_RUNNERS)}")
        arguments = _arguments(name, arguments_json)
        return json.dumps(_plain(run(store, arguments)), ensure_ascii=False)
    except ToolError as error:
        return _error(str(error))
    except DomainError as error:  # not found, not allowed, bad input: the route's own sentence
        return _error(str(error) or type(error).__name__)
    except Exception as error:  # a bug: the model gets no internals, the server log the traceback
        log.exception("pipeline tool %s failed", name)
        return _error(f"{name} failed ({type(error).__name__})")


def _error(message: str) -> str:
    return json.dumps({"error": message}, ensure_ascii=False)


def _plain(found: Any) -> Any:
    if isinstance(found, BaseModel):
        return found.model_dump(mode="json", by_alias=True)
    if isinstance(found, list):
        return [_plain(item) for item in found]  # pyright: ignore[reportUnknownVariableType]
    return found


def _arguments(name: str, arguments_json: str) -> dict[str, str]:
    """The call's arguments: a JSON object with exactly the tool's string parameters."""
    try:
        given = json.loads(arguments_json or "{}")
    except ValueError as error:
        raise ToolError(f"the arguments are not valid JSON ({error})") from error
    if not isinstance(given, dict):
        raise ToolError("the arguments must be a JSON object")
    wanted = _parameters(name)
    missing = [key for key in wanted if key not in given]
    if missing:
        raise ToolError(f"missing argument {', '.join(missing)} (needs {', '.join(wanted)})")
    unknown = [key for key in given if key not in wanted]  # pyright: ignore[reportUnknownVariableType]
    if unknown:
        raise ToolError(f"unknown argument {', '.join(unknown)} (needs {', '.join(wanted)})")
    out: dict[str, str] = {}
    for key in wanted:
        value = given[key]  # pyright: ignore[reportUnknownVariableType]
        if isinstance(value, int) and not isinstance(value, bool):
            value = str(value)  # a page number sent as a number
        if not isinstance(value, str) or not value.strip():
            raise ToolError(f"{key} must be a non-empty string")
        out[key] = value.strip()
    return out


def _parameters(name: str) -> list[str]:
    for tool in PIPELINE_TOOLS:
        if tool["function"]["name"] == name:
            return list(tool["function"]["parameters"]["properties"])
    return []


def _done(store: PipelineStore, project_id: str) -> ProjectStatus:
    """The project, which must exist and be done (the routes' 404 and 409)."""
    status = store.ingest.status(project_id)
    if status.state != "done":
        raise ToolError(f"project {project_id} is {status.state}; ask again when it is done")
    return status


def _entry(status: ProjectStatus, drawing_id: str) -> DrawingEntry:
    found = next((e for e in drawings_of(status) if e.drawing_id == drawing_id), None)
    if found is None:
        raise ToolError(f"project {status.id} has no drawing {drawing_id}")
    return found


def _list_drawings(store: PipelineStore, args: Mapping[str, str]) -> list[dict[str, Any]]:
    status = store.ingest.status(args["project_id"])
    files = {file.path: file for file in status.files}
    return [_listed(store, entry, files.get(entry.file)) for entry in drawings_of(status)]


def _listed(store: PipelineStore, entry: DrawingEntry, file: FileStatus | None) -> dict[str, Any]:
    triage = None if file is None else file.triage
    try:
        pages: int | None = len(store.ingest.drawing(entry.drawing_id).pages)
    except DomainError:
        pages = None  # not read (yet)
    return {
        "drawing_id": entry.drawing_id,
        "name": entry.file,
        "kind": entry.kind,
        "route": entry.route,
        "state": entry.state,
        "pages": pages,
        "triage": None
        if triage is None
        else {
            "class": triage.class_,
            "subject": None if triage.description is None else triage.description.subject,
            "relevance": None if triage.relevance is None else triage.relevance.verdict,
            "verdict": triage.verdict,
        },
    }


def _ask(store: PipelineStore, args: Mapping[str, str]) -> BaseModel:
    return project_ask(
        args["project_id"],
        ProjectAskRequest(question=args["question"]),
        store.ingest,
        store.reviews,
        store.answering,
        store.settings,
    )


def _takeoff(store: PipelineStore, args: Mapping[str, str]) -> BaseModel:
    status = _done(store, args["project_id"])
    entry = _entry(status, args["drawing_id"])
    return takeoff_rows(entry.drawing_id, store.ingest, store.reviews, False, status.id)


def _conflicts(store: PipelineStore, args: Mapping[str, str]) -> list[BaseModel]:
    status = _done(store, args["project_id"])
    return list(review_of(status, store.ingest, store.reviews).conflicts)


def _issues(store: PipelineStore, args: Mapping[str, str]) -> list[BaseModel]:
    found = issues_of(
        args["project_id"], None, store.ingest, store.reviews, store.settings, store.packs
    )
    return list(found.issues)


def _checks(store: PipelineStore, args: Mapping[str, str]) -> BaseModel:
    pack = find_pack(store.packs, args["pack"])  # NotFoundError names the pack
    return checks_of(args["project_id"], pack, store.ingest)


def _geometry(store: PipelineStore, args: Mapping[str, str]) -> dict[str, Any]:
    status = _done(store, args["project_id"])
    entry = _entry(status, args["drawing_id"])
    try:
        page = int(args["page"])
    except ValueError as error:
        raise ToolError("page must be a whole number") from error
    drawing = store.ingest.drawing(entry.drawing_id)
    if not any(shown.page == page for shown in drawing.pages):
        raise ToolError(f"drawing {entry.drawing_id} has no page {page}")
    return geometry_of(drawing, entry.route, entry.drawing_id, page)


def geometry_of(drawing: Drawing, route: str | None, drawing_id: str, page: int) -> dict[str, Any]:
    """One page of the drawing model as geometry. Boxes are page fractions
    [x0, y0, x1, y1]. A source that gives none of a part has it null, with `reasons[part]`.
    `walls_sure`: the walls are what the model or reader says they are (a building model's
    IfcWall), not cut solids that may also be columns (an IFC sheet read from its PDF)."""
    read = drawing.read
    reasons: dict[str, str] = {}

    def looked_for(name: str) -> bool:
        return read is None or name in read

    on_page = [e for e in drawing.elements if e.page == page]
    rooms = [r for r in drawing.rooms if r.page == page]
    walls = [e for e in on_page if e.class_ == "wall"]
    openings = [e for e in on_page if e.class_ in ("door", "window")]
    out: dict[str, Any] = {
        "drawing_id": drawing_id,
        "page": page,
        "source": {"route": route, "method": drawing.scale.source},
        "scale": {
            "status": drawing.scale.status,
            "m_per_unit": drawing.scale.m_per_unit,
            "text": drawing.scale.text,
            "unit": next(p.unit for p in drawing.pages if p.page == page),
        },
        "frame": [_dump(p, "id", "box", "storey") for p in drawing.plans if p.page == page],
        "rooms": [_room(r) for r in rooms] if rooms or looked_for("room") else None,
        "openings": [_item(e) for e in openings]
        if openings or (looked_for("door") and looked_for("window"))
        else None,
        "walls": [_item(e) for e in walls] if walls or looked_for("wall") else None,
        "walls_sure": bool(walls) and route == "bim",
    }
    for part, present in (("rooms", rooms), ("openings", openings), ("walls", walls)):
        if out[part] is None:
            reasons[part] = f"the reader for this drawing (route {route}) does not look for {part}"
        elif not present:
            reasons[part] = "none were found on this page"
    if walls and route != "bim":
        reasons["walls"] = (
            "cut solids: walls, columns and other cut parts share one drawn style, "
            "so some of these are not walls"
        )
    out["reasons"] = reasons
    return out


def _dump(item: BaseModel, *fields: str) -> dict[str, Any]:
    dumped = item.model_dump(mode="json", by_alias=True)
    return {field: dumped[field] for field in fields}


def _item(element: Any) -> dict[str, Any]:
    out = _dump(element, "id", "class", "box", "polygon")
    for key in ("length_m", "mark", "global_id"):
        if key in element.attrs:
            out[key] = element.attrs[key]
    return out


def _room(room: Any) -> dict[str, Any]:
    return _dump(room, "id", "type", "label", "box", "polygon", "area_m2", "outdoor")


Runner = Callable[[PipelineStore, Mapping[str, str]], Any]
_RUNNERS: dict[str, Runner] = {
    "list_drawings": _list_drawings,
    "ask_drawings": _ask,
    "get_takeoff": _takeoff,
    "list_conflicts": _conflicts,
    "list_issues": _issues,
    "run_checks": _checks,
    "get_plan_geometry": _geometry,
}

__all__ = ["PIPELINE_TOOLS", "PipelineStore", "geometry_of", "run_pipeline_tool"]

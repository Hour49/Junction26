"""The pipeline as tools for an agent chat (board #222, Tudor's agent-chat orchestrator): OpenAI
function-calling JSON in `PIPELINE_TOOLS`, and `run_pipeline_tool(store, name, arguments)`
that runs one (arguments: JSON text or the decoded object) and returns JSON text. It never
raises: a bad call (unknown tool, malformed or missing arguments, an unknown project, a project
still running) is `{"error": "..."}` for the
model to read and correct.

The project is `PipelineStore.project_id`: the chat loop binds it and no tool takes one. Each
tool's arguments are a pydantic model (`extra="forbid"`, strings capped) whose schema is the
tool's `parameters`. Each tool calls the code the HTTP route calls, so the numbers are the
routes' numbers:

    list_drawings   GET  /api/projects/{id}                 (+ each file's triage)
    ask_drawings    POST /api/projects/{id}/ask             (spends what a question spends)
    get_takeoff     GET  /api/drawings/{id}/takeoff?project={id}
    list_conflicts  GET  /api/projects/{id}/review          (its `conflicts`)
    list_issues     GET  /api/projects/{id}/issues
    run_checks      GET  /api/projects/{id}/checks?pack=    (fails first, passes counted)
    get_plan_geometry  the drawing model's plans, rooms, openings and walls on one page

The names are provisional (the chat side posts the final list); renaming is a change of `NAME`
in `TOOLS`. No tool but `ask_drawings` can spend money, and that one goes through the same spend
guard as the route.
"""

import json
import logging
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.adapters.vector_pdf import swiss
from app.adapters.vector_pdf.objects import read_page
from app.adapters.vector_pdf.wall_fills import WallFill, wall_fills
from app.api.checks import ProjectChecks, checks_of, find_pack
from app.api.deps import Ingest
from app.api.issues import issues_of
from app.api.project_ask import ProjectAnswer, ProjectAskRequest, project_ask
from app.api.projects import review_of
from app.api.takeoff import takeoff_rows
from app.api.views import DrawingEntry, drawings_of
from app.composition import Answering
from app.core.checks.model import RulePack
from app.core.drawing.model import Drawing, Room
from app.core.errors import DomainError
from app.core.ingest.model import FileStatus, ProjectStatus, Triage
from app.core.ingest.triage import sheet_flag
from app.core.pipeline.rules import ROOM_NUMBERS
from app.core.pipeline.user_scale import HINT as SCALE_HINT
from app.core.review.ports import ReviewStore
from app.settings import Settings

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class PipelineStore:
    """The services the routes get from `app.state`, held together for the tools."""

    project_id: str  # the project the chat is about; the loop binds it, the model never names it
    ingest: Ingest
    reviews: ReviewStore
    settings: Settings
    answering: Answering
    packs: tuple[RulePack, ...] = ()
    user_scale: bool = False  # USER_SCALE: a no-scale refusal says the user can give the scale

    @classmethod
    def of_app(cls, app: Any, project_id: str) -> "PipelineStore":
        """From a FastAPI app (`create_app()`'s state), for one project."""
        state = app.state
        return cls(
            project_id,
            state.ingest,
            state.reviews,
            state.settings,
            state.answering,
            state.rule_packs,
        )


class _Args(BaseModel):
    """A tool's arguments: no field but the ones declared, strings capped."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class _NoArgs(_Args):
    pass


class _AskArgs(_Args):
    question: str = Field(min_length=1, max_length=500, description="the question in plain words")


class _DrawingArgs(_Args):
    drawing_id: str = Field(
        pattern=r"^[0-9a-f]{16}$", description="a drawing id (16 hex characters) from list_drawings"
    )


class _ChecksArgs(_Args):
    pack: str = Field(min_length=1, max_length=64, description="the rule pack id")


class _GeometryArgs(_DrawingArgs):
    page: int = Field(ge=1, le=10_000, description="the page number, 1 for a single sheet")


def _tool(name: str, description: str, model: type[_Args]) -> dict[str, Any]:
    """The OpenAI function-calling entry; its parameters are the argument model's schema."""
    schema = model.model_json_schema()
    for field in schema.get("properties", {}).values():
        field.pop("title", None)
    schema.pop("title", None)
    schema.setdefault("properties", {})
    schema.setdefault("required", [])
    return {
        "type": "function",
        "function": {"name": name, "description": description, "parameters": schema},
    }


# The project is the store's: the chat loop binds it, the model never names one.
_TOOLS: list[tuple[str, str, type[_Args]]] = [
    (
        "list_drawings",
        "The drawings of the project: id, file name, kind, read state, page count, what kind "
        "of sheet triage says each picture looks like (with its printed title, sheet number and "
        "whether it may not be a floor plan) and, for a file that is not a floor plan, what "
        "triage thinks it shows and whether it belongs.",
        _NoArgs,
    ),
    (
        "ask_drawings",
        "Ask a question (e.g. 'how many doors are there?') on every drawing of the project. "
        "Gives each drawing's answer with its evidence (page and box), whether it is sure or "
        "needs a double-check, the drawings that refused and why, and a total only when the "
        "drawings show different parts of the building (why_no_total says why not).",
        _AskArgs,
    ),
    (
        "get_takeoff",
        "The quantities read from one drawing (counts, areas, lengths), each with its marks on "
        "the page, how it was measured and, where two methods disagree, the conflict with the "
        "position of each method's items.",
        _DrawingArgs,
    ),
    (
        "list_conflicts",
        "Every conflict of the project: a quantity two methods measured differently, with each "
        "method's value and whether a rule, a person or nobody settled it.",
        _NoArgs,
    ),
    (
        "list_issues",
        "Everything in the project that needs a person's look: conflicts, reading flags, files "
        "set aside, refused questions. Each is located on a page when it has a place.",
        _NoArgs,
    ),
    (
        "run_checks",
        "Check the project's drawings against a building-code rule pack: every failing and "
        "cannot-tell result with its drawing, rule and clause, then each rule on each drawing "
        "with its results counted by status. A pre-check, not a compliance certificate.",
        _ChecksArgs,
    ),
    (
        "get_plan_geometry",
        "Where things are on one page of a drawing, in page fractions (0-1, x then y, from the "
        "top left): the plan frame, scale, rooms, openings (doors, windows) and walls; for a "
        "swiss-style vector PDF also `walls_drawn`, its wall fills as polygons (never sure). A "
        "part the drawing's reader does not give is null with the reason.",
        _GeometryArgs,
    ),
]
PIPELINE_TOOLS: list[dict[str, Any]] = [_tool(*tool) for tool in _TOOLS]
_MODELS: dict[str, type[_Args]] = {name: model for name, _, model in _TOOLS}


class ToolError(Exception):
    """A call the tool refuses, with the sentence the model reads."""


def run_pipeline_tool(store: PipelineStore, name: str, arguments: str | dict[str, Any]) -> str:
    """Run the tool `name` on the store's project; `arguments`: JSON text or the decoded object.
    JSON text back (`ensure_ascii=False`). Never raises: a bad call is {"error": "..."}."""
    try:
        run = _RUNNERS.get(name)
        if run is None:
            raise ToolError(f"unknown tool {name!r}; the tools are {', '.join(_RUNNERS)}")
        args = _MODELS[name].model_validate(_decoded(arguments))
        return json.dumps(_plain(run(store, args)), ensure_ascii=False)
    except json.JSONDecodeError as error:
        return _error(f"the arguments are not valid JSON ({error})")
    except ValidationError as error:
        return _error(f"bad arguments for {name}: {_why(error)}")
    except ToolError as error:
        return _error(str(error))
    except DomainError as error:  # not found, not allowed, bad input: the route's own sentence
        return _error(str(error) or type(error).__name__)
    except Exception as error:  # a bug: the model gets no internals, the server log the traceback
        log.exception("pipeline tool %s failed", name)
        return _error(f"{name} failed ({type(error).__name__})")


def _decoded(arguments: str | dict[str, Any]) -> dict[str, Any]:
    given: Any = json.loads(arguments or "{}") if isinstance(arguments, str) else arguments
    if not isinstance(given, dict):
        raise ToolError("the arguments must be a JSON object")
    return cast(dict[str, Any], given)


def _why(error: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(at) for at in found['loc']) or 'arguments'}: {found['msg']}"
        for found in error.errors(include_url=False, include_input=False)
    )


def _error(message: str) -> str:
    return json.dumps({"error": message}, ensure_ascii=False)


def _plain(found: Any) -> Any:
    if isinstance(found, BaseModel):
        return found.model_dump(mode="json", by_alias=True)
    if isinstance(found, list):
        return [_plain(item) for item in found]  # pyright: ignore[reportUnknownVariableType]
    return found


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


def _list_drawings(store: PipelineStore, args: Any) -> list[dict[str, Any]]:
    status = store.ingest.status(store.project_id)
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
            "sheet": _sheet(triage),
        },
    }


def _sheet(triage: Triage) -> dict[str, Any] | None:
    """What the sheet-kind step called the picture, so the chat can say what kind of drawing it
    is: a doubted piping plan is read, so its class is floor_plan (R3-G4: "a raster floor
    plan"). `flag`: the reading flag its answers carry (triage.sheet_flag)."""
    sheet = triage.sheet
    if sheet is None:
        return None
    return {
        "looks_like": sheet.kind_words,
        "decision": sheet.decision,
        "title": sheet.title,
        "sheet_number": sheet.sheet_number,
        "printed_scale": sheet.printed_scale,
        "seen": sheet.seen,
        "flag": sheet_flag(triage),
    }


def _ask(store: PipelineStore, args: Any) -> BaseModel:
    found = project_ask(
        store.project_id,
        ProjectAskRequest(question=args.question),
        store.ingest,
        store.reviews,
        store.answering,
        store.settings,
    )
    return with_scale_hint(found) if store.user_scale else found


def with_scale_hint(found: ProjectAnswer) -> ProjectAnswer:
    """USER_SCALE: each no-scale refusal also says how the user can give the scale."""
    parts = []
    for part in found.parts:
        refusal = part.answer.refusal
        if refusal is not None and refusal.code == "no-scale":
            hinted = refusal.model_copy(update={"text": f"{refusal.text} {SCALE_HINT}"})
            part = part.model_copy(
                update={"answer": part.answer.model_copy(update={"refusal": hinted})}
            )
        parts.append(part)
    return found.model_copy(update={"parts": parts})


def _takeoff(store: PipelineStore, args: Any) -> BaseModel:
    status = _done(store, store.project_id)
    entry = _entry(status, args.drawing_id)
    return takeoff_rows(entry.drawing_id, store.ingest, store.reviews, False, status.id)


def _conflicts(store: PipelineStore, args: Any) -> list[BaseModel]:
    status = _done(store, store.project_id)
    return list(review_of(status, store.ingest, store.reviews).conflicts)


def _issues(store: PipelineStore, args: Any) -> list[BaseModel]:
    found = issues_of(
        store.project_id, None, store.ingest, store.reviews, store.settings, store.packs
    )
    return list(found.issues)


def _checks(store: PipelineStore, args: Any) -> dict[str, Any]:
    pack = find_pack(store.packs, args.pack)  # NotFoundError names the pack
    return _failures_first(checks_of(store.project_id, pack, store.ingest))


def _failures_first(found: ProjectChecks) -> dict[str, Any]:
    """The route's checks as the chat reads them: the failing and cannot-tell results first,
    each with its drawing, rule and clause, then each rule on each drawing with its results
    counted by status. The passes are only counted, so when the loop cuts a long result to fit
    (it halves the longest list) the failures are the last thing it reaches (R4-I5: the drawings
    list was cut before flat-b's failing Zimmer 1.05)."""
    listed: dict[str, list[dict[str, Any]]] = {"fail": [], "cannot_tell": []}
    rules: list[dict[str, Any]] = []
    for drawing in found.drawings:
        where = {"file": drawing.file, "drawing_id": drawing.drawing_id}
        for rule in drawing.rules:
            clause = rule.clause.model_dump(mode="json")
            for result in rule.results:
                if result.status in listed:
                    shown = result.model_dump(mode="json", exclude={"rule_id", "marks"})
                    listed[result.status].append(
                        {**where, "rule_id": rule.rule_id, "title": rule.title,
                         "clause": clause, **shown}
                    )  # fmt: skip
            rules.append(
                {**where, "rule_id": rule.rule_id, "title": rule.title, "status": rule.status,
                 "why": rule.why, "clause": rule.clause.ref,
                 "counts": dict(Counter(result.status for result in rule.results))}
            )  # fmt: skip
    return {
        "project_id": found.project_id,
        "pack": found.pack,
        "note": found.note,
        "status": found.status,
        "failures": listed["fail"],
        "cannot_tell": listed["cannot_tell"],
        "rules": rules,
    }


def _geometry(store: PipelineStore, args: Any) -> dict[str, Any]:
    status = _done(store, store.project_id)
    entry = _entry(status, args.drawing_id)
    page = args.page
    drawing = store.ingest.drawing(entry.drawing_id)
    if not any(shown.page == page for shown in drawing.pages):
        raise ToolError(f"drawing {entry.drawing_id} has no page {page}")
    return geometry_of(
        drawing, entry.route, entry.drawing_id, page, _fills(store, drawing, entry, page)
    )


def _fills(
    store: PipelineStore, drawing: Drawing, entry: DrawingEntry, page: int
) -> list[WallFill] | None:
    """The walls a swiss-style vector PDF draws as grey fills; None: not such a sheet."""
    if entry.route != "vector":
        return None
    sheet = store.ingest.sheet(entry.drawing_id)
    if sheet.kind != "pdf":
        return None
    shown = read_page(sheet.data, page - 1)
    if not swiss.matches(shown):
        return None
    return wall_fills(shown, drawing.scale.m_per_unit)


def geometry_of(
    drawing: Drawing,
    route: str | None,
    drawing_id: str,
    page: int,
    fills: list[WallFill] | None = None,
) -> dict[str, Any]:
    """One page of the drawing model as geometry. Boxes are page fractions
    [x0, y0, x1, y1]. A source that gives none of a part has it null, with `reasons[part]`.
    `walls_drawn`: the walls a swiss-style vector PDF draws as grey fills (`fills`, from
    wall_fills), outside the extraction: polygons in page fractions, never sure; null with a
    reason on any other source. `walls_sure`: the walls are what the model or reader says they
    are (a building model's IfcWall), not cut solids that may also be columns (an IFC sheet
    read from its PDF)."""
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
        "walls_drawn": None if fills is None else [_fill(f) for f in fills],
        "walls_drawn_source": None if fills is None else "vector fills",
        "walls_drawn_area_m2": _fills_area(fills),
    }
    if fills is None:
        reasons["walls_drawn"] = (
            "only a swiss-style vector PDF draws its walls as filled polygons; "
            f"this drawing is read by route {route}"
        )
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


def _fill(fill: WallFill) -> dict[str, Any]:
    return {
        "polygon": [list(point) for point in fill.polygon],
        "holes": [[list(point) for point in hole] for hole in fill.holes],
        "box": list(fill.box),
        "area_m2": fill.area_m2,
    }


def _fills_area(fills: list[WallFill] | None) -> float | None:
    if not fills or any(f.area_m2 is None for f in fills):
        return None
    return round(sum(f.area_m2 or 0 for f in fills), 3)


def _dump(item: BaseModel, *fields: str) -> dict[str, Any]:
    dumped = item.model_dump(mode="json", by_alias=True)
    return {field: dumped[field] for field in fields}


def _item(element: Any) -> dict[str, Any]:
    out = _dump(element, "id", "class", "box", "polygon")
    for key in ("length_m", "mark", "global_id"):
        if key in element.attrs:
            out[key] = element.attrs[key]
    return out


def _room(room: Room) -> dict[str, Any]:
    """A room with its printed number when the reader keeps it apart from the label (the vector
    reader's attrs), so rooms of one name are told apart ("Stanza" four times: R3-L3); a room
    with none has no `number` key (review-617 M1)."""
    out = _dump(room, "id", "type", "label", "box", "polygon", "area_m2", "outdoor")
    number = next((v for key in ROOM_NUMBERS if isinstance(v := room.attrs.get(key), str)), None)
    if number is not None:
        out["number"] = number
    return out


Runner = Callable[[PipelineStore, Any], Any]
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

"""The agent's toolbox for one project and turn (spec AC-13): the pipeline tools (#228), the plan
tools, the evidence tools over the project's other files, and the law tools when the app has a
law index, behind one `run(name, arguments)` that never raises. A tool module whose code is not
in this build is simply not offered."""

import json
import logging
import re
from collections.abc import Callable
from functools import partial
from typing import Any

from app.adapters.counting_rules import TOOLS as COUNTING_TOOLS
from app.adapters.counting_rules import run_counting_tool
from app.adapters.evidence_tools import EVIDENCE_TOOLS, run_evidence_tool
from app.adapters.pipeline_tools import PIPELINE_TOOLS, PipelineStore, run_pipeline_tool
from app.api.views import drawings_of
from app.core.agent.rooms import FIND_ROOMS, TOKEN, name_words
from app.core.checks.model import RulePack
from app.core.errors import DomainError
from app.core.plan_edit.law_check import ROOM_WORDS
from app.core.plan_edit.model import Proposal, Selection

log = logging.getLogger(__name__)
Json = dict[str, Any]
Runner = Callable[[str, str], str]  # (tool name, arguments JSON) -> result JSON
# A room by its printed number after a type word or its label ("bathroom 1.01", "Bagno 1.01"), not a
# measurement ("7.50 m2"). The pipeline's parser reads the type word and drops the number, but
# answers "room 1.01" (QA smoke-1; the parser is app/core/answering's, so worked around here)
ROOM_NUMBER = re.compile(r"\b([^\W\d_]+)\s+(\d+\.\d{2})\b(?!\s*(?:m\b|m2|m²|cm|mm|%))")
ROOMS_LISTED = 12
FIND_TOOLS: list[Json] = [
    {
        "type": "function",
        "function": {
            "name": FIND_ROOMS,
            "description": (
                "The rooms whose label printed on the drawings contains every word of `query` "
                "(e.g. 'office', 'open office 102'), with their places (ev ids). Use it when "
                "ask_drawings refuses a question that names a room: offer the printed labels "
                "as options, or read the one room with get_plan_geometry. Labels only."
            ),
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "minLength": 1, "maxLength": 120}},
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    }
]


class AgentToolbox:
    def __init__(
        self,
        sets: list[tuple[list[Json], Runner]],
        describe: Callable[[Selection], str],
        made: Callable[[], list[Proposal]] = list,
    ):
        self._runners = {tool["function"]["name"]: run for tools, run in sets for tool in tools}
        self._tools = [tool for tools, _ in sets for tool in tools]
        self._describe = describe
        self._made = made  # the proposals the plan tools hold, law checks included

    def proposal(self, proposal_id: str) -> Proposal | None:
        return next((p for p in self._made() if p.proposal_id == proposal_id), None)

    @property
    def tools(self) -> list[Json]:
        return self._tools

    def run(self, name: str, arguments: str) -> str:
        run = self._runners.get(name)
        if run is None:
            return _error(f"unknown tool {name!r}; the tools are {', '.join(self._runners)}")
        try:
            return run(name, arguments)
        except Exception as error:  # the tools never raise; a bug in one still must not end a turn
            log.exception("agent tool %s failed", name)
            return _error(f"{name} failed ({type(error).__name__})")

    def describe(self, selection: Selection) -> str:
        return self._describe(selection)


def project_toolbox(
    app: Any,
    project_id: str,
    selection: list[Selection],
    proposals: dict[str, Proposal],
    pack: RulePack | None = None,
) -> AgentToolbox:
    """The tools of `project_id` in `app` (create_app()'s state). `proposals`: the chat's
    proposals so far, so the plan tools number new ones after them. `pack`: the rule pack this
    turn's plan edits are checked against (LC-6), None: not checked."""
    pipeline = PipelineStore.of_app(app, project_id)
    pipe: Runner = partial(run_pipeline_tool, pipeline)
    sets: list[tuple[list[Json], Runner]] = [
        (PIPELINE_TOOLS, partial(_by_number, pipe)),
        (FIND_TOOLS, partial(_find_rooms, pipeline)),
    ]
    sets.append((COUNTING_TOOLS, run_counting_tool))  # read-only conventions, no project state
    describe: Callable[[Selection], str] = _plain
    made: Callable[[], list[Proposal]] = list
    laws = getattr(app.state, "laws", None)  # the law index (SqliteLawIndex), None: no law files
    try:
        from app.adapters.plan_tools import PLAN_TOOLS, PlanStore, run_plan_tool
    except ImportError:
        pass
    else:
        plans = PlanStore(
            pipeline, {s.id: s for s in selection}, list(proposals.values()), pack, laws
        )
        if pipeline.settings.services_follow == "on":  # decision 0016
            from app.adapters.service_tools import follower

            services = follower(app, pipeline)
            services.warm()  # the models are read while the turn's first steps run
            plans.services = services.run
        sets.append((PLAN_TOOLS, partial(run_plan_tool, plans)))
        describe = plans.describe
        made = lambda: plans.proposals  # noqa: E731
    evidence = getattr(app.state, "evidence", None)  # EvidenceIndexes (decision 0012)
    if evidence is not None:
        index = evidence.evidence_index(project_id)
        sets.append((EVIDENCE_TOOLS, partial(run_evidence_tool, index)))
    if laws is not None:
        try:
            from app.adapters.law_tools import TOOLS, run_tool  # pyright: ignore
        except ImportError:
            pass
        else:
            run_law: Runner = partial(run_tool, laws)  # pyright: ignore
            sets.append(
                (TOOLS, run_law if pack is None else partial(_pack_default, run_law, pack.id))
            )  # pyright: ignore
    return AgentToolbox(sets, describe, made)


def _find_rooms(store: PipelineStore, name: str, arguments: str) -> str:
    """find_rooms: the project's rooms whose printed label (and number) holds every word."""
    given: Any = json.loads(arguments)
    query: Any = given.get("query") if isinstance(given, dict) else None  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    words = set(name_words(query)) if isinstance(query, str) else set[str]()
    if not words:
        return _error("give the room's words as printed, e.g. 'office' or 'open office 102'")
    found: list[Json] = []
    for entry in drawings_of(store.ingest.status(store.project_id)):
        try:
            rooms = store.ingest.drawing(entry.drawing_id).rooms
        except DomainError:
            continue  # not read
        for room in rooms:
            printed = _printed(room.label, room.attrs.get("number"))
            if printed and words <= set(TOKEN.findall(printed.lower())):
                place = {"drawing_id": entry.drawing_id, "page": room.page, "box": list(room.box)}
                found.append({"room": room.id, "label": printed, "name": entry.name, **place})
    if not found:
        reason = f"no room label printed on the drawings holds {' '.join(sorted(words))}"
        return json.dumps({"status": "unknown", "reason": reason}, ensure_ascii=False)
    out: Json = {"status": "ok", "count": len(found), "rooms": found[:ROOMS_LISTED]}
    return json.dumps(out, ensure_ascii=False)


def _printed(label: str | None, number: Any) -> str | None:
    """A room's label as printed, with its number when the label does not hold it."""
    if not label:
        return None
    return f"{label} {number}" if number and str(number) not in label else label


def room_by_number(question: str) -> str:
    """`question` with each "<room word or label> <number>" read as "room <number>"."""

    def swap(found: re.Match[str]) -> str:
        word = found[1].lower()
        if word == "room" or not any(re.search(pattern, word) for _, pattern in ROOM_WORDS):
            return found[0]
        return f"room {found[2]}"

    return ROOM_NUMBER.sub(swap, question)


def _by_number(run: Runner, name: str, arguments: str) -> str:
    """ask_drawings with its question's rooms named by number (QA smoke-1)."""
    try:
        given: Any = json.loads(arguments)
    except json.JSONDecodeError:
        return run(name, arguments)
    question: Any = given.get("question") if isinstance(given, dict) else None  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    if name == "ask_drawings" and isinstance(question, str):
        arguments = json.dumps({**given, "question": room_by_number(question)})  # pyright: ignore[reportUnknownArgumentType]
    return run(name, arguments)


def _pack_default(run: Runner, pack: str, name: str, arguments: str) -> str:
    """A law tool call with the turn's pack when the model gives none (QA answers-3)."""
    try:
        given: Any = json.loads(arguments)
    except json.JSONDecodeError:
        return run(name, arguments)
    if name == "search_law" and isinstance(given, dict) and not given.get("pack"):  # pyright: ignore[reportUnknownMemberType]
        arguments = json.dumps({**given, "pack": pack})  # pyright: ignore[reportUnknownArgumentType]
    return run(name, arguments)


def _plain(selection: Selection) -> str:
    """A selection's line when no plan tools can describe it from geometry."""
    where = f"on drawing {selection.drawing_id} page {selection.page}"
    return f"{selection.id}: {selection.kind} {selection.ref or ''} {where}".replace("  ", " ")


def _error(message: str) -> str:
    return json.dumps({"error": message}, ensure_ascii=False)

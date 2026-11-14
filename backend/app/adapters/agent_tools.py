"""The agent's toolbox for one project and turn (spec AC-13): the pipeline tools (#228), the plan
tools, the evidence tools over the project's other files, and the law tools when the app has a
law index, behind one `run(name, arguments)` that never raises. A tool module whose code is not
in this build is simply not offered."""

import json
import logging
from collections.abc import Callable
from functools import partial
from typing import Any

from app.adapters.evidence_tools import EVIDENCE_TOOLS, run_evidence_tool
from app.adapters.pipeline_tools import PIPELINE_TOOLS, PipelineStore, run_pipeline_tool
from app.core.plan_edit.model import Proposal, Selection

log = logging.getLogger(__name__)
Json = dict[str, Any]
Runner = Callable[[str, str], str]  # (tool name, arguments JSON) -> result JSON


class AgentToolbox:
    def __init__(self, sets: list[tuple[list[Json], Runner]], describe: Callable[[Selection], str]):
        self._runners = {tool["function"]["name"]: run for tools, run in sets for tool in tools}
        self._tools = [tool for tools, _ in sets for tool in tools]
        self._describe = describe

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
    app: Any, project_id: str, selection: list[Selection], proposals: dict[str, Proposal]
) -> AgentToolbox:
    """The tools of `project_id` in `app` (create_app()'s state). `proposals`: the chat's
    proposals so far, so the plan tools number new ones after them."""
    pipeline = PipelineStore.of_app(app, project_id)
    sets: list[tuple[list[Json], Runner]] = [(PIPELINE_TOOLS, partial(run_pipeline_tool, pipeline))]
    describe: Callable[[Selection], str] = _plain
    try:
        from app.adapters.plan_tools import PLAN_TOOLS, PlanStore, run_plan_tool
    except ImportError:
        pass
    else:
        plans = PlanStore(pipeline, {s.id: s for s in selection}, list(proposals.values()))
        sets.append((PLAN_TOOLS, partial(run_plan_tool, plans)))
        describe = plans.describe
    evidence = getattr(app.state, "evidence", None)  # EvidenceIndexes (decision 0012)
    if evidence is not None:
        index = evidence.evidence_index(project_id)
        sets.append((EVIDENCE_TOOLS, partial(run_evidence_tool, index)))
    laws = getattr(app.state, "laws", None)
    if laws is not None:
        try:
            from app.adapters.law_tools import TOOLS, run_tool  # pyright: ignore
        except ImportError:
            pass
        else:
            sets.append((TOOLS, partial(run_tool, laws)))  # pyright: ignore
    return AgentToolbox(sets, describe)


def _plain(selection: Selection) -> str:
    """A selection's line when no plan tools can describe it from geometry."""
    where = f"on drawing {selection.drawing_id} page {selection.page}"
    return f"{selection.id}: {selection.kind} {selection.ref or ''} {where}".replace("  ", " ")


def _error(message: str) -> str:
    return json.dumps({"error": message}, ensure_ascii=False)

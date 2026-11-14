"""`SERVICES_FOLLOW=on`: a plan edit's proposal is followed through the project's service models
(decision 0016, spec services-follow). The plan tools call `ServiceFollower.run` for every
proposal they make (plan_tools._proposed), so the model picks the edit and code does the rest:
no tool to forget, no order to get wrong.

Which models: every IFC file of the project that carries distribution elements. They are laid
over the plan through the building model the sheet was drawn from: the centres of that model's
spaces against the centres of the rooms the sheet draws (services.model.fit_frame). A plan that
was not drawn from a model, a sheet the model does not fit, or a service model without the
sheet's storey is not followed, and its lanes say why.

`run` never raises: a model that cannot be read leaves its lanes "not checked" with the reason,
and the edit itself is returned as it was.
"""

import logging
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from app.adapters.ifc_services import ServiceFile, ServiceFiles
from app.adapters.pipeline_tools import (
    PipelineStore,
    _done,  # pyright: ignore[reportPrivateUsage]
    _entry,  # pyright: ignore[reportPrivateUsage]
)
from app.adapters.plan_tools import plan_page
from app.api.views import drawings_of
from app.core.errors import DomainError
from app.core.ifc_facts import Discipline
from app.core.ingest.model import FileStatus
from app.core.plan_edit.model import Proposal
from app.core.plan_edit.walls import PlanPage
from app.core.services.follow import follow, not_followed
from app.core.services.model import (
    LANES,
    Frame,
    Lane,
    Point2,
    ServiceElement,
    ServicesFollow,
    fit_frame,
)

log = logging.getLogger(__name__)

STOREY_MATCH_M = 0.05  # a service model has the sheet's storey when one of its is this close
TOP_STOREY_M = 3.5  # the height followed above the building's top storey
ACTIONS_SHOWN = 12  # per lane, to the model; the proposal keeps them all
NOT_FROM_MODEL = (
    "this plan was not drawn from a building model, so service models cannot be laid over it"
)


@dataclass(frozen=True)
class _Placed:
    frame: Frame
    storey: str
    heights: tuple[float, float]


@dataclass
class ServiceFollower:
    pipeline: PipelineStore
    files: ServiceFiles
    credit_of: Callable[[int, str], str | None] = lambda size, sha256: None  # a file's credit

    def run(self, proposal: Proposal) -> tuple[ServicesFollow, dict[str, Any]]:
        """The follow-up for the proposal and what the model reads of it."""
        try:
            followed = self._follow(proposal)
        except Exception as error:  # a bug or an unreadable file: the edit is not lost with it
            log.exception("services follow failed for proposal %s", proposal.proposal_id)
            why = f"the service models could not be read ({type(error).__name__})"
            followed = _unchecked(dict.fromkeys(LANES, why))
        return followed, for_model(followed)

    def _follow(self, proposal: Proposal) -> ServicesFollow:
        store = self.pipeline
        status = _done(store, store.project_id)
        entry = _entry(status, proposal.drawing_id)
        models = [f for f in status.files if f.kind == "ifc" and f.sha256]
        if not models:
            return _unchecked({})
        names = {e.file: e.name for e in drawings_of(status)}
        read: list[tuple[FileStatus, ServiceFile]] = []
        for model in models:
            try:
                read.append((model, self._read(model)))
            except DomainError as error:
                log.warning("service model %s not read: %s", model.path, error)
        carrying = [(model, file) for model, file in read if file.elements]
        if not carrying:
            return _unchecked({})
        page = plan_page(store, proposal.drawing_id, proposal.page)
        source = next((f for m, f in read if m.path == entry.source), None)
        placed = (
            NOT_FROM_MODEL
            if entry.route != "bim" or source is None
            else self._placed(page, proposal, source)
        )
        lanes: list[Lane] = []
        credits: list[str] = []
        for discipline in LANES:
            mine = [(m, f) for m, f in carrying if discipline in {e.lane for e in f.elements}]
            if not mine:
                lanes.append(Lane(discipline, "no_model"))
                continue
            name = ", ".join(_name(model, names) for model, _ in mine)
            if isinstance(placed, str):
                lanes.append(Lane(discipline, "not_aligned", name, placed))
                continue
            fitting = [(m, f) for m, f in mine if _has_storey(f, placed.heights[0])]
            if not fitting:
                why = f"its storeys are not this building's (none at {placed.heights[0]:.2f} m)"
                lanes.append(Lane(discipline, "not_aligned", name, why))
                continue
            elements: list[ServiceElement] = [
                placed.frame.placed(element)
                for _, file in fitting
                for element in file.elements
                if element.lane == discipline
            ]
            credits += [c for m, _ in fitting if (c := self.credit_of(m.size, m.sha256 or ""))]
            lanes.append(Lane(discipline, "checked", name, elements=tuple(elements)))
        if isinstance(placed, str):
            return not_followed(lanes)
        return follow(page, proposal, lanes, placed.heights, placed.storey, credits)

    def _read(self, model: FileStatus) -> ServiceFile:
        assert model.sha256 is not None
        ingest, project = self.pipeline.ingest, self.pipeline.project_id
        return self.files.file(model.sha256, lambda: ingest.upload_bytes(project, model.id))

    def _placed(self, page: PlanPage, proposal: Proposal, source: ServiceFile) -> _Placed | str:
        """The sheet over its model: the frame, the storey the sheet shows and its heights."""
        drawing = self.pipeline.ingest.drawing(proposal.drawing_id)
        shapes = page.room_shapes()
        pairs: list[tuple[Point2, Point2]] = []
        storeys: Counter[str] = Counter()
        for listed in drawing.model_objects or ():
            centre = source.spaces.get(listed.global_id or "")
            shape = shapes.get(listed.element or "")
            if listed.class_ != "space" or centre is None or shape is None:
                continue
            pairs.append((centre, (shape.centroid.x, shape.centroid.y)))
            storeys[listed.storey or ""] += 1
        frame = fit_frame(pairs)
        if isinstance(frame, str):
            return frame
        storey = storeys.most_common(1)[0][0]
        floor = next((height for name, height in source.storeys if name == storey), None)
        if floor is None:
            return "the model does not say how high this sheet's storey is"
        above = min((h for _, h in source.storeys if h > floor + 1.0), default=floor + TOP_STOREY_M)
        return _Placed(frame, storey, (floor, above))


def _has_storey(file: ServiceFile, floor: float) -> bool:
    return any(abs(height - floor) <= STOREY_MATCH_M for _, height in file.storeys)


def _name(model: FileStatus, names: dict[str, str]) -> str:
    """The model's plain name in the project; a model with no drawing of its own has none, so
    its file name."""
    return names.get(model.path) or PurePosixPath(model.path).name


def _unchecked(reasons: dict[Discipline, str]) -> ServicesFollow:
    return not_followed([Lane(d, "no_model", reason=reasons.get(d)) for d in LANES])


def for_model(followed: ServicesFollow) -> dict[str, Any]:
    """What the model reads: every lane's line and counts and its actions in plain words. No
    refs, places or model ids (decision 0013 §2). `text`: the lines as one paragraph, for a
    planner without a model."""
    checked = [d for d in followed.disciplines if d.status == "checked"]
    others = [d for d in followed.disciplines if d.status != "checked"]
    text = " ".join(d.line for d in checked)
    if checked and others:
        text += " Not checked: " + "; ".join(
            f"{d.discipline} ({d.reason})" for d in others
        ) + "."  # fmt: skip
    return {
        "storey": followed.storey,
        "text": text,
        "disciplines": [
            {
                "discipline": d.discipline,
                "status": d.status,
                "model": d.source,
                "line": d.line,
                "summary": d.summary.model_dump(),
                "actions": [
                    {"status": a.status, "what": a.label} for a in d.actions[:ACTIONS_SHOWN]
                ],
                "more_actions": max(len(d.actions) - ACTIONS_SHOWN, 0),
            }
            for d in followed.disciplines
        ],
        "unknowns": list(followed.unknowns),
    }


def follower(app: Any, pipeline: PipelineStore) -> ServiceFollower:
    """The follower of one project, with the app's read models (kept on `app.state`)."""
    files = getattr(app.state, "service_files", None)
    if files is None:
        files = app.state.service_files = ServiceFiles()
    credits = getattr(app.state, "credits", None)
    return ServiceFollower(pipeline, files, credits.of if credits is not None else lambda *_: None)

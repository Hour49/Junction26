"""`SERVICES_FOLLOW=on`: a plan edit's proposal is followed through the project's service models
(decision 0016, spec services-follow). The plan tools call `ServiceFollower.run` for every
proposal they make (plan_tools._proposed), so the model picks the edit and code does the rest:
no tool to forget, no order to get wrong.

Which models: every IFC file of the project that carries distribution elements. They are laid
over the plan through the building model the sheet was drawn from: the centres of that model's
spaces against the centres of the rooms the sheet draws (services.model.fit_frame). A plan that
was not drawn from a model, a sheet the model does not fit, or a service model without the
sheet's storey is not followed, and its lanes say why.

A plan that was not drawn from a model can still be followed on the project's services pictures
(`pictures`: a drawing's services fact sheet, the picture readers'): a lane such a picture gives
replaces that lane's "not checked" (services.picture_follow).

`run` never raises: a model that cannot be read leaves its lanes "not checked" with the reason,
and the edit itself is returned as it was.
"""

import logging
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from pathlib import PurePosixPath
from typing import Any

from app.adapters.ifc_services import FILES_KEPT, ServiceFile, ServiceFiles
from app.adapters.pipeline_tools import (
    PipelineStore,
    _done,  # pyright: ignore[reportPrivateUsage]
    _entry,  # pyright: ignore[reportPrivateUsage]
)
from app.adapters.plan_tools import plan_page
from app.api.views import drawings_of
from app.core.errors import DomainError
from app.core.ifc_facts import Discipline, FactSheet
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
from app.core.services.picture_follow import Sheet, picture_follow

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
    # A drawing's services fact sheet read from its picture, by drawing id; None: it has none
    pictures: Callable[[str], FactSheet | None] = lambda drawing_id: None

    def run(self, proposal: Proposal) -> tuple[ServicesFollow, dict[str, Any]]:
        """The follow-up for the proposal and what the model reads of it."""
        try:
            followed = self._with_pictures(proposal, self._follow(proposal))
        except Exception as error:  # a bug or an unreadable file: the edit is not lost with it
            log.exception("services follow failed for proposal %s", proposal.proposal_id)
            why = f"the service models could not be read ({type(error).__name__})"
            followed = _unchecked(dict.fromkeys(LANES, why))
        return followed, for_model(followed)

    def warm(self) -> None:
        """Starts reading the project's models off the request, so the first proposal does not
        wait for them. Never raises; a project that is not read yet is left alone."""
        try:
            status = _done(self.pipeline, self.pipeline.project_id)
            models, _ = _models(status, None)
            self.files.warm([(m.sha256 or "", partial(self._bytes, m.id)) for m in models])
        except Exception:  # the follow-up reads them itself and says what it could not
            log.debug("service models not read ahead", exc_info=True)

    def _follow(self, proposal: Proposal) -> ServicesFollow:
        store = self.pipeline
        status = _done(store, store.project_id)
        entry = _entry(status, proposal.drawing_id)
        models, left_out = _models(status, entry.source)
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
        followed = follow(page, proposal, lanes, placed.heights, placed.storey, credits)
        if not left_out:
            return followed
        more = (
            f"{left_out} more model file{'s' if left_out > 1 else ''} of this project "
            f"{'were' if left_out > 1 else 'was'} not read: at most {FILES_KEPT} are followed."
        )
        return followed.model_copy(update={"unknowns": (*followed.unknowns, more)})

    def _with_pictures(self, proposal: Proposal, followed: ServicesFollow) -> ServicesFollow:
        """On a plan not drawn from a model, the lanes the project's services pictures give."""
        status = _done(self.pipeline, self.pipeline.project_id)
        if _entry(status, proposal.drawing_id).route == "bim":
            return followed
        sheets: list[tuple[Sheet, FactSheet]] = []
        for drawing_id in dict.fromkeys(f.drawing_id for f in status.files if f.drawing_id):
            facts = self.pictures(drawing_id)
            if facts is not None:  # a picture lane reads page 1; the plan's own sheet its page
                page = proposal.page if drawing_id == proposal.drawing_id else 1
                sheets.append((self._sheet(drawing_id, page, facts), facts))
        if not sheets:
            return followed
        plan = self._sheet(proposal.drawing_id, proposal.page, self.pictures(proposal.drawing_id))
        seen = picture_follow(proposal, plan, sheets)
        lanes = tuple(
            mine if mine.status != "no_model" else theirs
            for mine, theirs in zip(seen.disciplines, followed.disciplines, strict=True)
        )
        return followed.model_copy(
            update={
                "disciplines": lanes,
                "storey": followed.storey or seen.storey,
                "unknowns": (*followed.unknowns, *seen.unknowns),
            }
        )

    def _sheet(self, drawing_id: str, page: int, facts: FactSheet | None) -> Sheet:
        """Where a drawing's page lies: its size in metres when it has a scale, its room names
        at their boxes' centres, the floor its services facts name."""
        drawing = self.pipeline.ingest.drawing(drawing_id)
        shown = next((p for p in drawing.pages if p.page == page), None)
        m = drawing.scale.m_per_unit
        return Sheet(
            drawing_id=drawing_id,
            page=page,
            storey=next((f.storey for f in facts.facts if f.storey), None) if facts else None,
            size_m=(shown.width * m, shown.height * m) if shown and m else None,
            rooms=tuple(
                (r.label, ((r.box[0] + r.box[2]) / 2, (r.box[1] + r.box[3]) / 2))
                for r in drawing.rooms
                if r.page == page and r.label
            ),
        )

    def _read(self, model: FileStatus) -> ServiceFile:
        assert model.sha256 is not None
        return self.files.file(model.sha256, partial(self._bytes, model.id))

    def _bytes(self, file_id: str) -> bytes:
        return self.pipeline.ingest.upload_bytes(self.pipeline.project_id, file_id)

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


def _models(status: Any, source: str | None) -> tuple[list[FileStatus], int]:
    """The project's model files that are read, and how many are left out: the sheet's own
    model first, then the others as the project lists them, as many as are kept read
    (`FILES_KEPT`: one more would push the first out again on every proposal)."""
    models = [f for f in status.files if f.kind == "ifc" and f.sha256]
    models.sort(key=lambda f: f.path != source)
    return models[:FILES_KEPT], max(len(models) - FILES_KEPT, 0)


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
                "line": d.line + _cut_note(len(d.actions)),
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


def _cut_note(actions: int) -> str:
    """Said in words, so a cut list is not read as the whole of it."""
    if actions <= ACTIONS_SHOWN:
        return ""
    return f" Only the first {ACTIONS_SHOWN} of its {actions} findings are listed here."


def follower(app: Any, pipeline: PipelineStore) -> ServiceFollower:
    """The follower of one project, with the app's read models (kept on `app.state`)."""
    files = getattr(app.state, "service_files", None)
    if files is None:
        files = app.state.service_files = ServiceFiles()
    credits = getattr(app.state, "credits", None)
    made = ServiceFollower(pipeline, files, credits.of if credits is not None else lambda *_: None)
    if pipeline.settings.discipline_pictures != "off":  # the picture lane's kept sheets
        from app.adapters.discipline_pictures.lane import PictureSheets

        kept = PictureSheets(None, pipeline.settings.discipline_pictures_cache_dir)
        made.pictures = kept.of_drawings(lambda: _done(pipeline, pipeline.project_id).files)
    return made

"""POST /api/projects/{project_id}/ask: a question on every drawing of a project (docs/API.md
"Answering"). Each part is exactly what POST /api/ask gives on that drawing in the project. A
total is given only when one drawing answers, or when the drawings that answer are known to show
different parts of the building: the same building drawn twice (a sheet and its model) would
otherwise be counted twice (board #14, Tudor)."""

import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from fastapi import APIRouter
from pydantic import Field

from app.adapters.ifc_model.glb import GlbModels
from app.api.ask import QUESTION_CHARS, AnswerView, answer_view
from app.api.deps import (
    AnsweringDep,
    IngestDep,
    Models3dDep,
    ProjectId,
    ReviewsDep,
    SettingsDep,
    now,
)
from app.api.questions import AskedQuestion, record
from app.api.views import View, drawings_of
from app.core.answering.model import Unit
from app.core.drawing.model import Drawing
from app.core.ingest.model import Highlight, Model3d, ProjectStatus
from app.core.review.check import LevelName, lowest
from app.core.review.model import RefusalCode, Row
from app.core.review.proof import SHOWN_UNITS
from app.core.review.review import NotAllowedError, noun

router = APIRouter(prefix="/api/projects")

SUMMED = ("count", "area", "length")  # what a total adds up over drawings
# What a refused drawing lacks, per refusal code: (one drawing, several)
LACKS: dict[RefusalCode, tuple[str, str]] = {
    "no-reader": ("gives no reliable number for it", "give no reliable number for it"),
    "no-scale": ("has no scale", "have no scale"),
    "not-in-drawing": ("doesn't show it", "don't show it"),
    "not-read": ("wasn't read for it", "weren't read for it"),
    "unsupported-question": ("can't answer this question", "can't answer this question"),
    "no-drawing": ("has no drawing model", "have no drawing model"),
}


class ProjectAskRequest(View):
    question: str = Field(min_length=1, max_length=QUESTION_CHARS)


class ProjectAnswerPart(View):
    drawing_id: str
    name: str  # the drawing's file as the project uploaded it
    answer: AnswerView  # what POST /api/ask gives on this drawing in this project
    file_id: str | None = None  # the drawing's file in the project (FileStatus.id)
    # The IFC file whose 3D view shows this drawing (…/files/{model_file_id}/model.glb): its own
    # file when that is IFC, else the IFC model it was read from; left out when there is none
    model_file_id: str | None = Field(default=None, exclude_if=lambda value: value is None)
    # MODEL_3D: that file's 3D view state, as its FileStatus.model_3d; left out otherwise
    model_3d: Model3d | None = Field(default=None, exclude_if=lambda value: value is None)
    # The elements the answer counted, by IFC GlobalId (answer.proof.objects), to highlight in the
    # 3D view; left out when there are none
    highlight: list[Highlight] = Field(default_factory=list[Highlight], exclude_if=lambda v: not v)


class ProjectAnswer(View):
    question: str
    parts: list[ProjectAnswerPart]  # the drawings that answered, then those that refused
    # One answering part's value, or several parts added up when they are known to show
    # different storeys of one model (a count, or an area or length of each whole drawing, in
    # one unit); None otherwise: the drawings may show the same rooms twice
    total: int | float | None
    total_unit: Unit | None  # the unit of `total`; None with it
    total_sure: bool  # every part in the total is sure (`line.sure`); False with no total
    # The lowest confidence level among the total's parts that have one (`answer.level`); None
    # with no total, or when no part has a level
    total_level: LevelName | None
    total_note: str  # one plain sentence: what the total is over, what is left out and why
    # total_note in its two parts. why_no_total: why there is no total, as a sentence; None with
    # a total. refused_note: the drawings that refused and what each lacks, as a sentence; None
    # when none refused.
    why_no_total: str | None
    refused_note: str | None


@dataclass(frozen=True)
class Total:
    note: str
    total: int | float | None = None
    unit: Unit | None = None
    sure: bool = False
    level: LevelName | None = None
    why_not: str | None = None
    left_out: str | None = None


@router.post("/{project_id}/ask")
def project_ask(
    project_id: ProjectId,
    body: ProjectAskRequest,
    ingest: IngestDep,
    reviews: ReviewsDep,
    answering: AnsweringDep,
    settings: SettingsDep,
    models_3d: Models3dDep = None,
) -> ProjectAnswer:
    """`models_3d`: the 3D views' state to put on IFC parts at response time (MODEL_3D); the chat
    tool calls this without, so a kept chat never keeps a stale state."""
    status = ingest.status(project_id)  # 404 for a project that doesn't exist
    if status.state != "done":
        raise NotAllowedError(f"project {project_id} is {status.state}; ask when it is done")
    file_ids = {file.path: file.id for file in status.files}
    ifc_ids = {file.path: file.id for file in status.files if file.kind == "ifc"}
    parts = [
        _part(
            entry.drawing_id,
            entry.file,
            file_ids.get(entry.file),
            # a sheet read from its model: the model; MODEL_3D off: none, nor a highlight
            ifc_ids.get(entry.source or entry.file) if settings.model_3d else None,
            answer_view(
                body.question, entry.drawing_id, project_id, ingest, reviews, answering, settings
            ),
        )
        for entry in drawings_of(status)
    ]
    answered = [part for part in parts if part.answer.refusal is None]
    refused = [part for part in parts if part.answer.refusal is not None]
    total = _total(parts, ingest.drawing)
    asked, at = uuid.uuid4().hex[:16], now()
    for part in answered or refused:  # a question no drawing answered: every drawing refused
        record(
            settings.projects_dir,
            project_id,
            AskedQuestion(
                question=body.question,
                answer=part.answer.answer,
                unit=part.answer.unit,
                drawing_id=part.drawing_id,
                at=at,
                refused=part.answer.refusal is not None,
                refusal=None if part.answer.refusal is None else part.answer.refusal.code,
                project_ask=asked,
            ),
        )
    return with_models_3d(
        ProjectAnswer(
            question=body.question,
            parts=answered + refused,
            total=total.total,
            total_unit=total.unit,
            total_sure=total.sure,
            total_level=total.level,
            total_note=total.note,
            why_no_total=total.why_not,
            refused_note=total.left_out,
        ),
        status,
        models_3d,
    )


def _part(
    drawing_id: str, file: str, file_id: str | None, model_file_id: str | None, answer: AnswerView
) -> ProjectAnswerPart:
    # the 3D view's fields only with a model file (MODEL_3D on): off, the payload as before
    counted = answer.proof.objects or () if answer.refusal is None and model_file_id else ()
    return ProjectAnswerPart(
        drawing_id=drawing_id,
        name=file,
        answer=answer,
        file_id=file_id,
        model_file_id=model_file_id,
        highlight=[
            Highlight(global_id=item.global_id, role="affected")
            for item in counted
            if item.global_id
        ],
    )


def with_models_3d(
    answer: ProjectAnswer, status: ProjectStatus, models: GlbModels | None
) -> ProjectAnswer:
    """Each part with an IFC model file gets that file's 3D view state (MODEL_3D); off, the
    answer as it is."""
    if models is None:
        return answer
    files = {file.id: file for file in status.files if file.kind == "ifc" and file.sha256}
    parts = [
        part.model_copy(update={"model_3d": models.status(files[part.model_file_id].sha256 or "")})
        if part.model_file_id in files
        else part
        for part in answer.parts
    ]
    return answer.model_copy(update={"parts": parts})


def _total(parts: list[ProjectAnswerPart], drawing_of: Callable[[str], Drawing]) -> Total:
    answered = [part.answer for part in parts if part.answer.refusal is None]
    left_out = _refused([part.answer for part in parts if part.answer.refusal is not None])
    if not answered:
        said = f"No drawing answered it: {left_out}" if left_out else "The project has no drawing"
        why = "No drawing answered it." if left_out else f"{said}."
        return Total(note=f"{said}.", why_not=why, left_out=_dotted(left_out))
    rows = [view.quantity for view in answered]
    found = [row for row in rows if row is not None]
    many = _drawings(len(answered))
    if any(isinstance(view.answer, str) for view in answered):  # "Which room is the largest?"
        return _no_total(f"{many} answered with a room's name, so there is no total", left_out)
    if len(found) < len(rows):
        return _no_total(f"{many} answered from a printed table, so there is no total", left_out)
    if len(found) > 1:
        if not all(_summed(row) for row in found):
            return _no_total(
                f"{many} answered, each about its own room, so there is no total", left_out
            )
        if len({view.unit for view in answered}) != 1:
            return _no_total(f"{many} answered in different units, so there is no total", left_out)
        if not _disjoint([drawing_of(view.drawing_id) for view in answered], found):
            return _no_total(
                f"{many} answered; they may show the same rooms, so the numbers are not added up",
                left_out,
            )
    total = sum(row.value for row in found)
    total = total if isinstance(total, int) else round(total, 6)  # no float noise
    unit = answered[0].unit
    # A sum with an area measured on an estimated scale is said in whole m², as its part is
    # (ask.shown_value, #294): two decimals would claim a precision the estimate does not have.
    if unit == "m2" and isinstance(total, float) and any(row.estimate for row in found):
        total = round(total)
    first = found[0]
    said = noun(first.measure, first.subject, total)
    shown = f"{total} {said}" if said else f"{first.label}: {total}{_shown(unit)}"
    note = f"{shown} {'from' if len(found) == 1 else 'over'} {many}"
    checks = sum(_double_check(row) for row in found)
    if checks:
        note += f"; {checks} of them {'needs' if checks == 1 else 'need'} a double-check"
    sure = all(view.line.sure is True for view in answered)
    return Total(
        total=total,
        unit=unit,
        sure=sure,
        level=lowest(view.level.level for view in answered if view.level is not None),
        note=_sentence(note, left_out),
        left_out=_dotted(left_out),
    )


def _no_total(why: str, left_out: str) -> Total:
    return Total(note=_sentence(why, left_out), why_not=f"{why}.", left_out=_dotted(left_out))


def _dotted(left_out: str) -> str | None:
    return f"{left_out[0].upper()}{left_out[1:]}." if left_out else None


def _disjoint(drawings: Sequence[Drawing], rows: Sequence[Row]) -> bool:
    """The drawings are known to show different parts of one building: sheets of the same
    building model (the same objects by IFC global id, as the IFC second counter links a sheet
    to its model), each showing one storey, no two the same. A model file shows every storey, a
    question "in the model" asks the whole model on each sheet, and drawings with no model may
    be the same flat drawn twice: none of them is known to be disjoint."""
    if any(row.scope.model for row in rows):
        return False
    models = {
        frozenset(item.global_id for item in drawing.model_objects or () if item.global_id)
        for drawing in drawings
    }
    storeys = [{plan.storey for plan in drawing.plans} for drawing in drawings]
    return (
        len(models) == 1
        and frozenset() not in models
        and all(drawing.pages for drawing in drawings)
        and all(len(shown) == 1 and None not in shown for shown in storeys)
        and len(set.union(*storeys)) == len(drawings)
    )


def _shown(unit: Unit | None) -> str:
    """' m²' after an area, nothing after a count."""
    return "" if unit in (None, "count") else f" {SHOWN_UNITS.get(unit, unit)}"


def _summed(row: Row) -> bool:
    """A row whose values add up over drawings: a count, or an area or length of the whole
    drawing; not one room's (by name or printed label) or the largest of several."""
    scope = row.scope
    return row.measure in SUMMED and not (scope.name or scope.label or scope.largest)


def _double_check(row: Row | None) -> bool:
    """The row's methods disagree (its conflict), or a person still has to settle it."""
    return row is not None and (row.needs_person or row.status == "conflict")


def _refused(views: list[AnswerView]) -> str:
    """'1 drawing gives no reliable number for it, 2 drawings have no scale', by refusal code."""
    codes: dict[RefusalCode, int] = {}
    for view in views:
        assert view.refusal is not None  # only refusals are passed: narrows the type
        codes[view.refusal.code] = codes.get(view.refusal.code, 0) + 1
    return ", ".join(
        f"{_drawings(count)} {LACKS[code][count != 1]}" for code, count in codes.items()
    )


def _drawings(count: int) -> str:
    return f"{count} drawing{'' if count == 1 else 's'}"


def _sentence(said: str, left_out: str) -> str:
    return f"{said}; {left_out}." if left_out else f"{said}."

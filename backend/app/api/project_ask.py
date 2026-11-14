"""POST /api/projects/{project_id}/ask: a question on every drawing of a project (docs/API.md
"Answering"). Each part is exactly what POST /api/ask gives on that drawing in the project. A
total is given only when one drawing answers, or when the drawings that answer are known to show
different parts of the building: the same building drawn twice (a sheet and its model) would
otherwise be counted twice (board #14, Tudor)."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from fastapi import APIRouter
from pydantic import Field

from app.api.ask import QUESTION_CHARS, AnswerView, answer_view
from app.api.deps import AnsweringDep, IngestDep, ProjectId, ReviewsDep, SettingsDep, now
from app.api.projects import drawings_of
from app.api.questions import AskedQuestion, record
from app.api.views import View
from app.core.answering.model import Unit
from app.core.drawing.model import Drawing
from app.core.review.model import RefusalCode, Row
from app.core.review.proof import SHOWN_UNITS
from app.core.review.review import NotAllowedError, noun

router = APIRouter(prefix="/api/projects")

SUMMED = ("count", "area", "length")  # what a total adds up over drawings
# What a refused drawing lacks, per refusal code: (one drawing, several)
LACKS: dict[RefusalCode, tuple[str, str]] = {
    "no-reader": ("has no reader for it", "have no reader for it"),
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


class ProjectAnswer(View):
    question: str
    parts: list[ProjectAnswerPart]  # the drawings that answered, then those that refused
    # One answering part's value, or several parts added up when they are known to show
    # different storeys of one model (a count, or an area or length of each whole drawing, in
    # one unit); None otherwise: the drawings may show the same rooms twice
    total: int | float | None
    total_unit: Unit | None  # the unit of `total`; None with it
    total_sure: bool  # every part in the total is sure (`line.sure`); False with no total
    total_note: str  # one plain sentence: what the total is over, what is left out and why


@dataclass(frozen=True)
class Total:
    note: str
    total: int | float | None = None
    unit: Unit | None = None
    sure: bool = False


@router.post("/{project_id}/ask")
def project_ask(
    project_id: ProjectId,
    body: ProjectAskRequest,
    ingest: IngestDep,
    reviews: ReviewsDep,
    answering: AnsweringDep,
    settings: SettingsDep,
) -> ProjectAnswer:
    status = ingest.status(project_id)  # 404 for a project that doesn't exist
    if status.state != "done":
        raise NotAllowedError(f"project {project_id} is {status.state}; ask when it is done")
    parts = [
        ProjectAnswerPart(
            drawing_id=entry.drawing_id,
            name=entry.file,
            answer=answer_view(
                body.question, entry.drawing_id, project_id, ingest, reviews, answering, settings
            ),
        )
        for entry in drawings_of(status)
    ]
    answered = [part for part in parts if part.answer.refusal is None]
    refused = [part for part in parts if part.answer.refusal is not None]
    total = _total(parts, ingest.drawing)
    record(
        settings.projects_dir,
        project_id,
        AskedQuestion(
            question=body.question,
            answer=total.total,
            unit=total.unit,
            drawing_id=None,
            at=now(),
            refused=not answered,
        ),
    )
    return ProjectAnswer(
        question=body.question,
        parts=answered + refused,
        total=total.total,
        total_unit=total.unit,
        total_sure=total.sure,
        total_note=total.note,
    )


def _total(parts: list[ProjectAnswerPart], drawing_of: Callable[[str], Drawing]) -> Total:
    answered = [part.answer for part in parts if part.answer.refusal is None]
    left_out = _refused([part.answer for part in parts if part.answer.refusal is not None])
    if not answered:
        said = f"No drawing answered it: {left_out}" if left_out else "The project has no drawing"
        return Total(note=f"{said}.")
    rows = [view.quantity for view in answered]
    found = [row for row in rows if row is not None]
    many = _drawings(len(answered))
    if len(found) < len(rows):
        return Total(note=_sentence(f"{many} answered from a printed table, so there is no total",
                                    left_out))  # fmt: skip
    if len(found) > 1:
        if not all(_summed(row) for row in found):
            return Total(note=_sentence(f"{many} answered, each about its own room, so there is "
                                        "no total", left_out))  # fmt: skip
        if len({view.unit for view in answered}) != 1:
            return Total(note=_sentence(f"{many} answered in different units, so there is no "
                                        "total", left_out))  # fmt: skip
        if not _disjoint([drawing_of(view.drawing_id) for view in answered], found):
            return Total(note=_sentence(f"{many} answered; they may show the same rooms, so the "
                                        "numbers are not added up", left_out))  # fmt: skip
    total = sum(row.value for row in found)
    total = total if isinstance(total, int) else round(total, 6)  # no float noise
    unit = answered[0].unit
    first = found[0]
    said = noun(first.measure, first.subject, total)
    shown = f"{total} {said}" if said else f"{first.label}: {total}{_shown(unit)}"
    note = f"{shown} {'from' if len(found) == 1 else 'over'} {many}"
    checks = sum(_double_check(row) for row in found)
    if checks:
        note += f"; {checks} of them {'needs' if checks == 1 else 'need'} a double-check"
    sure = all(view.line.sure is True for view in answered)
    return Total(total=total, unit=unit, sure=sure, note=_sentence(note, left_out))


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
    """'1 drawing has no reader for it, 2 drawings have no scale', by refusal code."""
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

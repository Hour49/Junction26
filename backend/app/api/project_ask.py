"""POST /api/projects/{project_id}/ask: a question on every drawing of a project (docs/API.md
"Answering"). Each part is exactly what POST /api/ask gives on that drawing in the project; the
total only adds those parts up, and only where adding them means something."""

from dataclasses import dataclass

from fastapi import APIRouter
from pydantic import Field

from app.api.ask import QUESTION_CHARS, AnswerView, answer_view
from app.api.deps import AnsweringDep, IngestDep, ProjectId, ReviewsDep, SettingsDep, now
from app.api.projects import drawings_of
from app.api.questions import AskedQuestion, record
from app.api.views import View
from app.core.answering.model import Unit
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
    # The answering parts added up: a count, or an area or length over the whole of each
    # drawing, in one unit; None when there is nothing to add up or adding means nothing
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
    total = _total(parts)
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


def _total(parts: list[ProjectAnswerPart]) -> Total:
    answered = [part.answer for part in parts if part.answer.refusal is None]
    left_out = _refused([part.answer for part in parts if part.answer.refusal is not None])
    if not answered:
        said = f"No drawing answered it: {left_out}" if left_out else "The project has no drawing"
        return Total(note=f"{said}.")
    rows = [view.quantity for view in answered]
    summed = [row for row in rows if row is not None and _summed(row)]
    units = {view.unit for view in answered}
    if len(summed) < len(rows) or len(units) != 1:
        why = (
            "each answer is about its own room or table"
            if len(summed) < len(rows)
            else "they answered in different units"
        )
        return Total(note=_sentence(f"{_drawings(len(answered))} answered; {why}, so they are "
                                    "not added up", left_out))  # fmt: skip
    total = sum(row.value for row in summed)
    total = total if isinstance(total, int) else round(total, 6)  # no float noise
    unit = answered[0].unit
    first = summed[0]
    said = noun(first.measure, first.subject, total)
    shown = f"{total} {said}" if said else f"{first.label}: {total}{_shown(unit)}"
    note = f"{shown} over {_drawings(len(answered))}"
    checks = sum(_double_check(row) for row in summed)
    if checks:
        note += f"; {checks} of them {'needs' if checks == 1 else 'need'} a double-check"
    sure = all(view.line.sure is True for view in answered)
    return Total(total=total, unit=unit, sure=sure, note=_sentence(note, left_out))


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

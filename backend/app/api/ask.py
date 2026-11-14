"""POST /api/ask: a question on one drawing (docs/API.md "Answering"). The answer carries the
takeoff row it was read from, in the same shape as the takeoff gives it, and the answer_v1.1 line
the scorer reads."""

from fastapi import APIRouter
from pydantic import Field

from app.api.deps import AnsweringDep, Ingest, IngestDep, ReviewsDep, SettingsDep, drawing_id_of
from app.api.views import PageView, Reader, View, page_views, reader_of
from app.composition import Answering, readers
from app.core.answering.model import Answer, Unit
from app.core.answering.ports import AnswerConfidence
from app.core.drawing.model import Drawing
from app.core.errors import NotFoundError
from app.core.review.ask import Asked, ask
from app.core.review.model import MarkView, Refusal, Row
from app.core.review.ports import ReviewStore
from app.core.review.proof import Proof

router = APIRouter(prefix="/api")

QUESTION_CHARS = 2000


class AskRequest(View):
    drawing_id: str
    question: str = Field(min_length=1, max_length=QUESTION_CHARS)


class AnswerView(View):
    question: str
    drawing_id: str
    file: str
    pages: list[PageView]
    answer: int | float | str | None  # None on a refusal: the screen shows no number
    unit: Unit | None
    # The probability the answer is right (DECISIONS_CONFIDENCE), None: not rated, or a refusal
    confidence: float | None
    quantity: Row | None  # the takeoff row; None for a refusal or a schedule answer
    marks: list[MarkView]
    refusal: Refusal | None
    method: str
    explanation: str | None
    reader: Reader
    cost_usd: float
    latency_s: float
    line: Answer  # the answer_v1.1 line as the scorer reads it
    proof: Proof  # what to draw as the proof: colour key, arithmetic, model objects, schedule


class _SheetFiles:
    """The one file a drawing was read from, as the pipeline read it, read only when asked."""

    def __init__(self, ingest: Ingest, drawing_id: str, path: str) -> None:
        self._ingest = ingest
        self._drawing_id = drawing_id
        self._path = path

    def read(self, path: str) -> bytes:
        if path != self._path:
            raise NotFoundError(f"drawing {self._drawing_id} was not read from {path}")
        return self._ingest.sheet(self._drawing_id).data


def confidence_of(
    drawing: Drawing, drawing_id: str, ingest: Ingest, answering: Answering
) -> AnswerConfidence | None:
    """The pipeline's answer confidence over the sheet the drawing was read from; None when it
    is off, or the drawing has no sheet of its own (a building model)."""
    if answering.confidence is None:
        return None
    info = ingest.drawing_info(drawing_id)
    if info.kind == "ifc" or info.path != drawing.file:
        return None
    return answering.confidence(_SheetFiles(ingest, drawing_id, info.path))


def asked_on(
    question: str,
    drawing: Drawing,
    drawing_id: str,
    reviews: ReviewStore,
    answering: Answering,
    ingest: Ingest,
) -> Asked:
    """The question on the drawing, with the surveyor's edits of it applied."""
    return ask(
        question,
        drawing,
        parser=answering.parser,
        clock=answering.clock,
        prior=answering.prior,
        state=reviews.get(drawing_id),
        prior_families=answering.prior_families,
        confidence=confidence_of(drawing, drawing_id, ingest, answering),
    )


def shown_value(asked: Asked) -> int | float | str | None:
    """The value the screen shows: the row's current value (edits applied), none on a refusal."""
    if asked.refusal is not None:
        return None
    return asked.answer.answer if asked.row is None else asked.row.value


@router.post("/ask")
def ask_route(
    body: AskRequest,
    ingest: IngestDep,
    reviews: ReviewsDep,
    answering: AnsweringDep,
    settings: SettingsDep,
) -> AnswerView:
    drawing_id = drawing_id_of(body.drawing_id)
    drawing = ingest.drawing(drawing_id)
    info = ingest.drawing_info(drawing_id)
    asked = asked_on(body.question, drawing, drawing_id, reviews, answering, ingest)
    line, shown = asked.answer, asked.row
    value = shown_value(asked)
    return AnswerView(
        question=body.question,
        drawing_id=drawing_id,
        file=drawing.file,
        pages=page_views(drawing_id, drawing.pages, info.normalised),
        answer=value,
        unit=None if asked.refusal is not None else line.unit,
        confidence=None if asked.refusal is not None else line.confidence,
        quantity=shown,
        marks=list(asked.marks),
        refusal=asked.refusal,
        method=line.method,
        explanation=line.explanation,
        reader=reader_of(info, readers(settings)),
        cost_usd=line.cost_usd,
        latency_s=line.latency_s,
        line=line,
        proof=asked.proof,
    )

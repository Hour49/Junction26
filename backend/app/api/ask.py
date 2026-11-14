"""POST /api/ask: a question on one drawing (docs/API.md "Answering"). The answer carries the
takeoff row it was read from, in the same shape as the takeoff gives it, and the answer_v1.1 line
the scorer reads."""

from collections.abc import Callable
from typing import TypedDict

from fastapi import APIRouter
from pydantic import Field

from app.adapters.page_render import render_png
from app.api.deps import (
    AnsweringDep,
    Ingest,
    IngestDep,
    ReviewsDep,
    SettingsDep,
    as_uploaded,
    drawing_id_of,
    now,
)
from app.api.questions import AskedQuestion, record
from app.api.views import PageView, Reader, View, page_views, reader_of
from app.composition import Answering, readers
from app.core import cost
from app.core.answering.model import Answer, Unit
from app.core.answering.ports import AnswerConfidence
from app.core.drawing.model import Drawing
from app.core.errors import NotFoundError
from app.core.ingest.model import DrawingInfo, FileStatus
from app.core.ingest.triage import sheet_doubt, sheet_flag
from app.core.review.ask import Asked, ask
from app.core.review.check import Check, Level
from app.core.review.model import (
    MarkView,
    Refusal,
    Resolved,
    ResolverUnavailable,
    Row,
    is_none,
)
from app.core.review.ports import ReviewStore
from app.core.review.proof import Proof
from app.core.review.resolve import among_values, answer_request, conflict_request
from app.settings import Settings

router = APIRouter(prefix="/api")

QUESTION_CHARS = 2000


def page_images(ingest: Ingest, drawing_id: str) -> Callable[[int, int], bytes]:
    """The drawing's pages as PNGs for the resolver, at the width it asks for, rendered only
    when it asks for one."""
    return lambda page, width: render_png(ingest.sheet(drawing_id), page, width)


class AskRequest(View):
    drawing_id: str
    question: str = Field(min_length=1, max_length=QUESTION_CHARS)
    project_id: str | None = None  # the project asked in: names the file as it uploaded it


class Signal(View):
    """A raw score a reader gives an answer, named for what it is. Not a probability that the
    answer is right: `calibrated` says whether it was checked against right answers (never yet)."""

    signal: str  # which score: `g1main` (Gemini Decisions' choice distribution)
    score: float = Field(ge=0.0, le=1.0)
    calibrated: bool


class AnswerView(View):
    question: str
    drawing_id: str
    file: str
    pages: list[PageView]
    answer: int | float | str | None  # None on a refusal: the screen shows no number
    unit: Unit | None
    # A raw score for the answer (DECISIONS_CONFIDENCE), None: not rated, or a refusal
    confidence: Signal | None
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
    # CHECK_POLICY: the answer is not certified, so a person is asked to double-check it at the
    # places where the readers disagree; None: certified, signed off, a refusal, or the policy off
    check: Check | None
    # CHECK_POLICY: the answer's confidence level (high, medium, low), what it rests on and one
    # sentence with the measured counts; high exactly when `check` is null on a rated answer.
    # None: a refusal, a value a person signed off or settled, the policy off or without levels
    level: Level | None
    # RESOLVER: what the resolver said about an answer CHECK_POLICY does not certify (`answer`,
    # `check` and `level` stay as they are: it is a model's check, beside them), and why it said
    # nothing when it could not; both left out of the JSON when None
    resolved: Resolved | None = Field(default=None, exclude_if=is_none)
    resolver_note: str | None = Field(default=None, exclude_if=is_none)
    # A room total that may leave rooms out: the sum of the `rooms_counted` rooms the reader
    # found (or drawn); `rooms_missing` are the rooms not in it: those a room schedule names that
    # it lacks, then those found whose box area was refused.
    # Left out of the JSON when it is not one
    partial: bool | None = Field(default=None, exclude_if=is_none)
    rooms_counted: int | None = Field(default=None, exclude_if=is_none)
    rooms_missing: list[str] | None = Field(default=None, exclude_if=is_none)


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
    is off, or the drawing was not read on the raster route (Gemini Decisions reads images, and
    a vector or model reading has no probability to give)."""
    if answering.confidence is None:
        return None
    info = ingest.drawing_info(drawing_id)
    if info.route != "raster" or info.path != drawing.file:
        return None
    return answering.confidence(_SheetFiles(ingest, drawing_id, info.path))


def asked_on(
    question: str,
    drawing: Drawing,
    drawing_id: str,
    reviews: ReviewStore,
    answering: Answering,
    ingest: Ingest,
    project_id: str | None,
    no_reader: bool = False,
) -> Asked:
    """The question on the drawing, with the surveyor's edits of it in `project_id` applied (a
    checked id: deps.project_of). The page's flags are the stored reading's plus the sheet-kind
    step's on the file in that project (triage.sheet_flag): its triage, not the cache's."""
    info = ingest.drawing_info(drawing_id)
    found = file_of(ingest, as_uploaded(ingest, info, project_id))
    flag = None if found is None else sheet_flag(found.triage)
    return ask(
        question,
        drawing,
        parser=answering.parser,
        clock=answering.clock,
        prior=answering.prior,
        state=reviews.get(project_id, drawing_id),
        prior_families=answering.prior_families,
        confidence=confidence_of(drawing, drawing_id, ingest, answering),
        sure_at=answering.sure_at,
        flags=info.flags if flag is None else (*info.flags, flag),
        raster=info.route == "raster",
        check=answering.check,
        route=info.route,
        disputes=answering.disputes,
        no_reader=no_reader,
        scorers=answering.scorers,
        carbon_ladder=answering.carbon_ladder,
        room_words=answering.room_words,
    )


def file_of(ingest: Ingest, named: DrawingInfo) -> FileStatus | None:
    """The file the drawing was read from, in the project that names it (deps.as_uploaded)."""
    try:
        files = ingest.status(named.project_id).files
    except NotFoundError:
        return None
    return next((file for file in files if file.path == named.path), None)


def doubt_of(ingest: Ingest, named: DrawingInfo) -> str | None:
    """The sheet-kind step's doubt line for the file the drawing was read from, in the project
    that names it (SHEET_KIND, .agents/exp/vlm-kind.md); None when it had no doubt."""
    found = file_of(ingest, named)
    return None if found is None else sheet_doubt(found.triage)


def no_reader_of(drawing_id: str, ingest: Ingest, settings: Settings) -> bool:
    """The drawing's route is read by the do-nothing stand-in (`hello`): no reader at all."""
    route = ingest.drawing_info(drawing_id).route
    return route is not None and readers(settings)[route] == "hello"


def signal_of(asked: Asked, answering: Answering) -> Signal | None:
    """The answer's raw score with its name; none on a refusal (its line may carry the prior's
    hit rate, which is another number)."""
    score = asked.answer.confidence
    if asked.refusal is not None or score is None or answering.signal is None:
        return None
    return Signal(signal=answering.signal, score=score, calibrated=False)


def shown_value(asked: Asked) -> int | float | str | None:
    """The value the screen shows: the row's current value (edits applied), none on a refusal.
    An area that is an estimate shows in whole m²: two decimals would claim a precision that an
    estimated scale (about ±16%, its areas about ±24% and more) does not have. The scorer's line
    keeps the value as measured."""
    if asked.refusal is not None:
        return None
    if asked.row is None:
        value, unit, estimate = asked.answer.answer, asked.answer.unit, bool(asked.answer.estimate)
    else:
        value, unit, estimate = asked.row.value, asked.row.unit, asked.row.estimate is not None
    if estimate and unit == "m2" and isinstance(value, float):
        return round(value)
    return value


@router.post("/ask")
def ask_route(
    body: AskRequest,
    ingest: IngestDep,
    reviews: ReviewsDep,
    answering: AnsweringDep,
    settings: SettingsDep,
) -> AnswerView:
    view = answer_view(
        body.question, body.drawing_id, body.project_id, ingest, reviews, answering, settings
    )
    if body.project_id is not None:  # asked in a project (checked to hold the drawing): kept
        record(
            settings.projects_dir,
            body.project_id,
            AskedQuestion(
                question=body.question,
                answer=view.answer,
                unit=view.unit,
                drawing_id=view.drawing_id,
                at=now(),
                refused=view.refusal is not None,
                refusal=None if view.refusal is None else view.refusal.code,
            ),
        )
    return view


def answer_view(
    question: str,
    drawing_id: str,
    project_id: str | None,
    ingest: Ingest,
    reviews: ReviewStore,
    answering: Answering,
    settings: Settings,
) -> AnswerView:
    """What POST /api/ask answers for `question` on one drawing, asked in `project_id` (its
    edits and its names) or in none; nothing is recorded."""
    drawing_id = drawing_id_of(drawing_id)
    drawing = ingest.drawing(drawing_id)
    info = ingest.drawing_info(drawing_id)
    named = as_uploaded(ingest, info, project_id)
    owner = None if project_id is None else named.project_id
    spent = cost.mark()  # a confidence not cached at ingest calls Decisions now (R1b-4-2)
    asked = asked_on(
        question, drawing, drawing_id, reviews, answering, ingest, owner,
        no_reader_of(drawing_id, ingest, settings),
    )  # fmt: skip
    shown = asked.row
    resolved = note = None
    if answering.resolver is not None and asked.check is not None and shown is not None:
        if shown.resolved is not None:
            resolved = shown.resolved  # its conflict was resolved: shown as stored, no call
        else:
            # a conflict a person has to choose is asked about as POST .../resolve asks it
            # (both sides, the same cache entry); any other answer with its own value
            pages = page_images(ingest, drawing_id)
            if shown.conflict is not None and shown.needs_person:
                request = conflict_request(drawing_id, shown)
                reply = among_values(shown, answering.resolver.resolve(request, pages))
            else:
                request = answer_request(drawing_id, question, shown, asked.marks, asked.check)
                reply = answering.resolver.resolve(request, pages)
            if isinstance(reply, ResolverUnavailable):
                note = reply.note
            else:
                resolved = reply
    line = asked.answer.model_copy(update={"cost_usd": cost.since(spent)})
    doubt = None if asked.refusal is not None else doubt_of(ingest, named)
    if doubt is not None:  # on an answer with a value only; it changes no value, check or level
        explanation = "; ".join(said for said in (line.explanation, doubt) if said)
        line = line.model_copy(update={"explanation": explanation})
    return AnswerView(
        question=question,
        drawing_id=drawing_id,
        file=drawing.file if project_id is None else named.path,
        pages=page_views(drawing_id, drawing, info.normalised),
        answer=shown_value(asked),
        unit=None if asked.refusal is not None else line.unit,
        confidence=signal_of(asked, answering),
        quantity=shown,
        marks=list(asked.marks),
        refusal=asked.refusal,
        method=line.method,
        explanation=line.explanation,
        reader=reader_of(named, shown is not None and shown.second is not None, readers(settings)),
        cost_usd=line.cost_usd,
        latency_s=line.latency_s,
        line=line,
        proof=asked.proof,
        check=asked.check,
        level=asked.level,
        resolved=resolved,
        resolver_note=note,
        **partial_fields(asked),
    )


class PartialFields(TypedDict, total=False):
    partial: bool
    rooms_counted: int
    rooms_missing: list[str]


def partial_fields(asked: Asked) -> PartialFields:
    """AnswerView's partial fields of a room total that may leave rooms out; none otherwise."""
    if asked.partial is None or asked.refusal is not None:
        return {}
    return {
        "partial": True,
        "rooms_counted": asked.partial.counted,
        # not in the sum: the rooms a schedule lists, then those whose box area was refused
        "rooms_missing": list(dict.fromkeys((*asked.partial.missing, *asked.partial.refused))),
    }

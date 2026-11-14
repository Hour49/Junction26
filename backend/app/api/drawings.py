"""Drawings: what a drawing is and how it was read, its model document, and its pages as PNG
(docs/API.md "Drawings")."""

from typing import Annotated, Any

from fastapi import APIRouter, Query
from fastapi.responses import Response

from app.adapters.evidence_render import render as render_evidence
from app.adapters.page_render import render_png
from app.api.ask import QUESTION_CHARS, asked_on, shown_value
from app.api.deps import (
    AnsweringDep,
    Credits,
    CreditsDep,
    DrawingId,
    Ingest,
    IngestDep,
    ReviewsDep,
    SettingsDep,
)
from app.api.views import PageView, Reader, View, page_views, reader_of
from app.composition import readers
from app.core.drawing.model import Drawing
from app.core.errors import InvalidInputError
from app.core.ingest.model import DrawingInfo
from app.core.pipeline.takeoff import known_quantities
from app.core.review.ask import SUGGESTIONS, suggestions
from app.core.review.model import Suggestion

router = APIRouter(prefix="/api/drawings")

# extraction_v1's optional lists, left out of the document when the drawing has none (0004)
OPTIONAL = ("tables", "conflicts", "read", "model_objects")
# A drawing id is a hash of its content and readers, so its pages never change.
IMMUTABLE = "public, max-age=31536000, immutable"
WIDTHS = (400, 1600, 3200)  # thumbnail, view, zoom


def checked_width(width: int) -> int:
    if width not in WIDTHS:
        raise InvalidInputError(f"width is one of {', '.join(map(str, WIDTHS))}, not {width}")
    return width


class DrawingView(View):
    id: str
    file: str
    reader: Reader
    credit: str | None
    pages: list[PageView]
    suggestions: list[Suggestion]


def credit_of(info: DrawingInfo, ingest: Ingest, credits: Credits) -> str | None:
    """The licence credit of the file the drawing is shown on, found by its content."""
    for file in ingest.status(info.project_id).files:
        if file.path == info.path and file.sha256 is not None:
            return credits.of(file.size, file.sha256)
    return None


def extraction_v1(drawing: Drawing) -> dict[str, Any]:
    absent = {name for name in OPTIONAL if getattr(drawing, name) is None}
    return {
        "schema": "extraction_v1",
        **drawing.model_dump(mode="json", by_alias=True, exclude=absent),
    }


@router.get("/{drawing_id}")
def drawing(
    drawing_id: DrawingId,
    ingest: IngestDep,
    settings: SettingsDep,
    answering: AnsweringDep,
    credits: CreditsDep,
) -> DrawingView:
    found = ingest.drawing(drawing_id)
    info = ingest.drawing_info(drawing_id)
    return DrawingView(
        id=drawing_id,
        file=found.file,
        reader=reader_of(info, readers(settings)),
        credit=credit_of(info, ingest, credits),
        pages=page_views(drawing_id, found.pages, info.normalised),
        suggestions=list(suggestions(known_quantities(found), answering.parser, SUGGESTIONS)),
    )


@router.get("/{drawing_id}/model")
def model(drawing_id: DrawingId, ingest: IngestDep) -> dict[str, Any]:
    """The drawing model as an extraction_v1 document (decision 0004)."""
    return extraction_v1(ingest.drawing(drawing_id))


@router.get(
    "/{drawing_id}/pages/{page}.png",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}, "description": "the page as PNG"}},
)
def page_png(
    drawing_id: DrawingId,
    page: int,
    ingest: IngestDep,
    width: Annotated[int, Query(description="400, 1600 or 3200")] = 1600,
) -> Response:
    png = render_png(ingest.sheet(drawing_id), page, checked_width(width))
    return Response(content=png, media_type="image/png", headers={"Cache-Control": IMMUTABLE})


@router.get(
    "/{drawing_id}/evidence.png",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}, "description": "the answer's proof drawn"}},
)
def evidence_png(
    drawing_id: DrawingId,
    question: Annotated[str, Query(min_length=1, max_length=QUESTION_CHARS)],
    ingest: IngestDep,
    reviews: ReviewsDep,
    answering: AnsweringDep,
    credits: CreditsDep,
    width: Annotated[int, Query(description="400, 1600 or 3200")] = 1600,
) -> Response:
    """The answer to `question` with its proof drawn on its page (docs/GOLDEN.md), as POST /api/ask
    gives it, edits applied. Not cached: a review edit changes it."""
    drawing = ingest.drawing(drawing_id)
    asked = asked_on(question, drawing, drawing_id, reviews, answering, ingest)
    page = next((mark.page for mark in asked.marks), 1)
    if asked.proof.schedule is not None:
        page = asked.proof.schedule.page
    width = checked_width(width)
    # a schedule is zoomed to its table, so its page is drawn at the largest width first
    drawn = WIDTHS[-1] if asked.proof.schedule is not None else width
    sheet = render_png(ingest.sheet(drawing_id), page, drawn) if drawing.pages else None
    value = shown_value(asked)
    if asked.refusal is not None:
        headline = f"{question}  ->  no answer: {asked.refusal.text}"
    else:
        unit = asked.answer.unit if asked.answer.unit not in (None, "count") else ""
        headline = f"{question}  ->  {value} {unit}".rstrip()
    credit = credit_of(ingest.drawing_info(drawing_id), ingest, credits)
    png = render_evidence(sheet, page, asked.marks, asked.proof, headline, credit, width)
    return Response(content=png, media_type="image/png", headers={"Cache-Control": "no-store"})

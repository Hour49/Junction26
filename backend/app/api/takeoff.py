"""The surveyor's takeoff of a drawing: rows, review edits with the recount, sign-off and the CSV
export (docs/API.md "Takeoff and review"). An edit or a sign-off returns the whole takeoff, so the
screen replaces its state instead of merging one row."""

import csv
import io
import re
from pathlib import PurePosixPath
from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import Response
from pydantic import Field

from app.api.deps import DrawingId, Ingest, IngestDep, ReviewsDep, now
from app.api.views import View
from app.core.pipeline.takeoff import known_quantities
from app.core.review.ask import RULES
from app.core.review.model import Edit, Row
from app.core.review.ports import ReviewStore
from app.core.review.review import apply, quantity_of, reset, review_queue, row, sign, unsign

router = APIRouter(prefix="/api/drawings")

ZEROS = Query(description="also list the rows whose value is 0 and nothing happened to")
CSV_COLUMNS = (
    "drawing", "key", "label", "value", "unit", "status", "original_value", "first_method",
    "first_value", "second_method", "second_value", "settled_value", "rule", "estimate",
    "signed_by", "signed_at",
)  # fmt: skip
FORMULA = ("=", "+", "-", "@", "\t", "\r")  # a cell starting so would run in a spreadsheet


class Takeoff(View):
    drawing_id: str
    file: str
    quantities: list[Row]
    review_queue: list[str]


class SignOffRequest(View):
    quantity: str = Field(min_length=1)
    by: str = Field(min_length=1, max_length=100)
    undo: bool = False


def takeoff_rows(drawing_id: str, ingest: Ingest, reviews: ReviewStore, zeros: bool) -> Takeoff:
    """The drawing's rows in takeoff order, edits applied. Without `zeros`, a row is left out
    when its value is 0 and it has no conflict, edit or sign-off."""
    drawing = ingest.drawing(drawing_id)
    state = reviews.get(drawing_id)
    rows = [row(found, drawing, state, RULES) for found in known_quantities(drawing).values()]
    if not zeros:
        rows = [found for found in rows if found.value != 0 or found.status != "single"]
    return Takeoff(
        drawing_id=drawing_id, file=drawing.file, quantities=rows, review_queue=review_queue(rows)
    )


@router.get("/{drawing_id}/takeoff")
def takeoff(
    drawing_id: DrawingId,
    ingest: IngestDep,
    reviews: ReviewsDep,
    zeros: Annotated[bool, ZEROS] = False,
) -> Takeoff:
    return takeoff_rows(drawing_id, ingest, reviews, zeros)


@router.post("/{drawing_id}/review")
def review(
    drawing_id: DrawingId,
    edit: Edit,
    ingest: IngestDep,
    reviews: ReviewsDep,
    zeros: Annotated[bool, ZEROS] = False,
) -> Takeoff:
    if edit.action == "reset" and edit.quantity is None:
        reviews.update(drawing_id, lambda state: reset(state, None))
    else:
        drawing = ingest.drawing(drawing_id)
        found = quantity_of(known_quantities(drawing), edit.quantity)
        at = now()
        reviews.update(drawing_id, lambda state: apply(state, edit, found, drawing, at))
    return takeoff_rows(drawing_id, ingest, reviews, zeros)


@router.post("/{drawing_id}/signoff")
def signoff(
    drawing_id: DrawingId,
    body: SignOffRequest,
    ingest: IngestDep,
    reviews: ReviewsDep,
    zeros: Annotated[bool, ZEROS] = False,
) -> Takeoff:
    drawing = ingest.drawing(drawing_id)
    found = quantity_of(known_quantities(drawing), body.quantity)
    if body.undo:
        reviews.update(drawing_id, lambda state: unsign(state, found.key))
    else:
        at = now()
        reviews.update(drawing_id, lambda state: sign(state, found, drawing, body.by, at))
    return takeoff_rows(drawing_id, ingest, reviews, zeros)


@router.get(
    "/{drawing_id}/takeoff.csv",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}, "description": "the takeoff as CSV"}},
)
def takeoff_csv(
    drawing_id: DrawingId,
    ingest: IngestDep,
    reviews: ReviewsDep,
    zeros: Annotated[bool, ZEROS] = False,
) -> Response:
    found = takeoff_rows(drawing_id, ingest, reviews, zeros)
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for quantity in found.quantities:
        first, second, signed = quantity.first, quantity.second, quantity.signed
        cells = (
            found.file,
            quantity.key,
            quantity.label,
            quantity.value,
            quantity.unit,
            quantity.status,
            quantity.original_value,
            first.method if first else "",
            first.value if first else "",
            second.method if second else "",
            second.value if second else "",
            quantity.settled.value if quantity.settled else "",
            quantity.rule.id,
            quantity.estimate or "",
            signed.by if signed else "",
            signed.at if signed else "",
        )
        writer.writerow([_cell(cell) for cell in cells])
    stem = re.sub(r"[^A-Za-z0-9._-]", "_", PurePosixPath(found.file).stem) or "drawing"
    return Response(
        content=out.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{stem}-takeoff.csv"'},
    )


def _cell(value: object) -> object:
    """Text from a file (a room label in a key) can't run as a spreadsheet formula."""
    if isinstance(value, str) and value.startswith(FORMULA):
        return "'" + value
    return value

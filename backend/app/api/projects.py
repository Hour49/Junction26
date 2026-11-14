"""Projects: upload a zip or one file, follow its ingest file by file, and the project's review
summary (docs/API.md "Projects and ingest")."""

import logging
import threading
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, Literal, NamedTuple

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel

from app.adapters.page_render import render_upload
from app.api.deps import FileId, Ingest, IngestDep, ProjectId, ReviewsDep, SettingsDep
from app.api.drawings import IMMUTABLE, checked_width
from app.api.issues import open_count
from app.api.questions import ProjectQuestions, listed, log_size
from app.api.takeoff import Takeoff, takeoff_rows
from app.api.views import (
    SHEET_KINDS,
    ProjectTrace,
    ProjectView,
    View,
    drawings_of,
    expected_drawings_of,
    skipped_of,
)
from app.core.errors import NotFoundError
from app.core.ingest.model import FileTrace, ProjectStatus, SecondCount
from app.core.pipeline.model import QuantityConflict
from app.core.review.model import ReviewState, Settled, SignOff
from app.core.review.ports import ReviewStore
from app.core.review.review import disputes, reset
from app.settings import Settings
from scripts.make_sample_archive import build_archive

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/projects")

MAX_UPLOAD = 200 * 1024 * 1024  # bytes; a larger body is refused with 413 before ingest sees it
MAX_WAITING = 3  # projects queued or running; one more upload is refused with 429
SAMPLE_NAME = "sample-project.zip"
# The files a preview is made of: images, and a PDF's first page.
PREVIEW_KINDS = (*SHEET_KINDS, "photo", "pdf_encrypted")


class Started(View):
    id: str
    name: str
    state: Literal["queued", "running", "done", "failed"]
    url: str


class ProjectSummary(View):
    id: str
    name: str
    state: Literal["queued", "running", "done", "failed"]
    created_at: str
    files: int
    drawings: int
    to_review: int | None  # quantities left to review over all drawings; None until `done`
    conflicts_open: int | None  # conflicts a person still has to settle; None until `done`
    # Issues in state open (GET …/issues without a pack, decision 0008); None until `done`
    issues_open: int | None = None


class ProjectList(View):
    projects: list[ProjectSummary]


class DrawingReview(View):
    drawing_id: str
    file: str
    to_review: int
    signed: int
    quantities: int


class ConflictEntry(View):
    drawing_id: str
    file: str
    quantity: str
    label: str
    conflict: QuantityConflict
    settled: Settled | None
    needs_person: bool
    signed: SignOff | None  # the sign-off, when a person signed the value off
    value: int | float  # the value in use: edits applied, the settled value if one was chosen


class ProjectReview(View):
    drawings: list[DrawingReview]
    conflicts: list[ConflictEntry]


class Admission:
    """The 429 limit: projects queued or running plus uploads still being received, checked and
    counted under one lock, so concurrent uploads can't all pass the check (MAX_WAITING)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._started: list[str] = []  # ids of the uploads this process started
        self._receiving = 0

    @contextmanager
    def slot(self, ingest: Ingest) -> Iterator[Callable[[str], None]]:
        """A place for one upload, or 429; yields the function that records its project id."""
        with self._lock:
            self._started[:] = [
                pid for pid in self._started if ingest.status(pid).state in ("queued", "running")
            ]
            waiting = len(self._started) + self._receiving
            if waiting >= MAX_WAITING:
                raise HTTPException(429, f"{waiting} projects are still being ingested; try again")
            self._receiving += 1
        try:
            yield self._record
        finally:
            with self._lock:
                self._receiving -= 1

    def _record(self, project_id: str) -> None:
        with self._lock:
            self._started.append(project_id)


class Counts(NamedTuple):
    review: ProjectReview
    issues_open: int


class KeptReviews:
    """Each done project's review and open issue count for the project list (R4-c-2:
    recomputing every review on every list call took 15-40 s with 18 projects). One is kept
    until what it is made of changes: the project's status, the size of its question log
    (refused answers are issues; the log is only appended to), or for one of its drawings the
    upload that wrote it last (a drawing is shared by content, so another project's ingest may
    write it again) or its review edits. All are read on every call, so every review write
    (settle, sign-off, add, reject, restore, reset) and every ask is seen, whoever wrote it."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._kept: dict[str, tuple[object, Counts]] = {}

    def counts(
        self, status: ProjectStatus, ingest: Ingest, reviews: ReviewStore, settings: Settings
    ) -> Counts | None:
        if status.state != "done":
            return None
        drawings = tuple(
            (ingest.drawing_info(entry.drawing_id), reviews.get(status.id, entry.drawing_id))
            for entry in drawings_of(status)
        )
        asked = log_size(settings.projects_dir, status.id)
        key = (status, drawings, asked)  # read before the counts: they are never newer
        with self._lock:
            kept = self._kept.get(status.id)
        if kept is not None and kept[0] == key:
            return kept[1]
        takeoffs = takeoffs_of(status, ingest, reviews)  # once, for the review and the issues
        found = Counts(
            review_of(status, ingest, reviews, takeoffs),
            open_count(status, ingest, reviews, settings, takeoffs),
        )
        with self._lock:
            self._kept[status.id] = (key, found)
        return found


class _Sample(BaseModel):
    """What the API remembers of the sample: the last project made from it (api/sample.json)."""

    project_id: str


@router.get("")
def project_list(
    request: Request, ingest: IngestDep, reviews: ReviewsDep, settings: SettingsDep
) -> ProjectList:
    """Every project, newest first."""
    kept: KeptReviews = request.app.state.kept_reviews
    statuses = ingest.projects()
    return ProjectList(
        projects=[
            summary_of(status, kept.counts(status, ingest, reviews, settings))
            for status in statuses
        ]
    )


def summary_of(status: ProjectStatus, found: Counts | None) -> ProjectSummary:
    """`found`: the project's counts, for a `done` project."""
    to_review = conflicts_open = issues_open = None
    if found is not None:
        to_review = sum(drawing.to_review for drawing in found.review.drawings)
        conflicts_open = sum(entry.needs_person for entry in found.review.conflicts)
        issues_open = found.issues_open
    return ProjectSummary(
        id=status.id,
        name=status.name,
        state=status.state,
        created_at=status.created_at,
        files=len(status.files),
        drawings=len(drawings_of(status)),
        to_review=to_review,
        conflicts_open=conflicts_open,
        issues_open=issues_open,
    )


@router.post("", status_code=202)
async def upload(
    request: Request,
    ingest: IngestDep,
    name: Annotated[str, Query(min_length=1, max_length=255)],
) -> Started:
    """The request body is the file's bytes (a zip or one drawing file); `name` its file name."""
    admission: Admission = request.app.state.admission
    try:
        with admission.slot(ingest) as record:
            data = bytearray()
            async for chunk in request.stream():
                data += chunk
                if len(data) > MAX_UPLOAD:
                    raise HTTPException(413, f"the upload is over {MAX_UPLOAD // 2**20} MB")
            started = _start(ingest, name, bytes(data))
            record(started.id)
    except HTTPException as refused:
        if refused.status_code == 429:  # refused before the body was read
            await _discard(request)
        raise
    return started


async def _discard(request: Request) -> None:
    """Reads the body to nowhere, up to the upload limit: a 429 sent with the body unread closes
    the socket with bytes still coming, the kernel resets it, and a client still writing never
    sees the 429 (R3-qa-3-1). Over the limit the client gets the reset, as a 413 would."""
    seen = 0
    async for chunk in request.stream():
        seen += len(chunk)
        if seen > MAX_UPLOAD:
            return


@router.post("/sample", status_code=202)
def sample(
    request: Request,
    ingest: IngestDep,
    reviews: ReviewsDep,
    settings: SettingsDep,
    fresh: bool = False,
) -> Started:
    """The synthetic sample archive. `fresh`: the review edits of the last sample run are reset."""
    # Built on first use; never refused as busy: it is small, and it is the demo's first click.
    if not settings.sample_archive.is_file():
        _build_sample(settings.sample_archive)
    record = settings.projects_dir / "api" / "sample.json"
    if fresh and record.is_file():
        _reset_project(ingest, reviews, _Sample.model_validate_json(record.read_text()).project_id)
    started = _start(ingest, SAMPLE_NAME, settings.sample_archive.read_bytes(), fresh)
    _write(record, _Sample(project_id=started.id).model_dump_json())
    return started


@router.get("/{project_id}")
def project(project_id: ProjectId, ingest: IngestDep) -> ProjectView:
    status = ingest.status(project_id)
    return ProjectView(
        **status.model_dump(),
        drawings=drawings_of(status),
        skipped=skipped_of(status),
        expected_drawings=expected_drawings_of(status),
    )


@router.get("/{project_id}/files/{file_id}/trace")
def trace(project_id: ProjectId, file_id: FileId, ingest: IngestDep) -> FileTrace:
    return trace_view(ingest.trace(project_id, file_id), ingest)


@router.get("/{project_id}/trace")
def project_trace(project_id: ProjectId, ingest: IngestDep) -> ProjectTrace:
    """Every file's trace in one request, in the order the upload lists the files."""
    return ProjectTrace(
        project_id=project_id,
        files=[trace_view(found, ingest) for found in ingest.traces(project_id)],
    )


def trace_view(found: FileTrace, ingest: Ingest) -> FileTrace:
    """The trace with its file's second count, read from the drawing's conflicts."""
    second = None
    drawing_id = found.file.drawing_id
    if drawing_id is not None:
        measured = ingest.drawing(drawing_id).conflicts
        if measured is not None:
            second = SecondCount(
                measured=len(measured),
                conflicts=sum(entry.status == "conflict" for entry in measured),
            )
    return found.model_copy(update={"second_count": second})


@router.get(
    "/{project_id}/files/{file_id}/preview.png",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}, "description": "the upload as PNG"}},
)
def preview(
    project_id: ProjectId,
    file_id: FileId,
    ingest: IngestDep,
    width: Annotated[int, Query(description="400, 1600 or 3200")] = 1600,
) -> Response:
    """The file as uploaded, EXIF turn applied only: an image, or a PDF's first page."""
    checked_width(width)
    kind = ingest.trace(project_id, file_id).file.kind
    if kind not in PREVIEW_KINDS:
        raise NotFoundError(f"file {file_id} is no image or PDF, so it has no preview")
    png = render_upload(ingest.upload_bytes(project_id, file_id), kind, width)
    return Response(content=png, media_type="image/png", headers={"Cache-Control": IMMUTABLE})


@router.get("/{project_id}/review")
def project_review(project_id: ProjectId, ingest: IngestDep, reviews: ReviewsDep) -> ProjectReview:
    """Per drawing what is left to review and what is signed, and every conflict of the project."""
    return review_of(ingest.status(project_id), ingest, reviews)


@router.get("/{project_id}/questions")
def project_questions(
    project_id: ProjectId, ingest: IngestDep, settings: SettingsDep
) -> ProjectQuestions:
    """The questions asked in the project (`project_id` in POST /api/ask), newest first."""
    ingest.status(project_id)  # 404 for a project that doesn't exist
    return ProjectQuestions(
        project_id=project_id, questions=listed(settings.projects_dir, project_id)
    )


def takeoffs_of(status: ProjectStatus, ingest: Ingest, reviews: ReviewStore) -> dict[str, Takeoff]:
    """Each drawing's takeoff in the project, its edits applied, zero rows left out."""
    return {
        entry.drawing_id: takeoff_rows(
            entry.drawing_id, ingest, reviews, zeros=False, project=status.id
        )
        for entry in drawings_of(status)
    }


def review_of(
    status: ProjectStatus,
    ingest: Ingest,
    reviews: ReviewStore,
    takeoffs: Mapping[str, Takeoff] | None = None,
) -> ProjectReview:
    """`takeoffs`: takeoffs_of(status), when the caller has it already."""
    takeoffs = takeoffs if takeoffs is not None else takeoffs_of(status, ingest, reviews)
    drawings: list[DrawingReview] = []
    conflicts: list[ConflictEntry] = []
    for entry in drawings_of(status):
        found = takeoffs[entry.drawing_id]
        drawings.append(
            DrawingReview(
                drawing_id=entry.drawing_id,
                file=entry.file,
                to_review=len(found.review_queue),
                signed=sum(row.status == "signed" for row in found.quantities),
                quantities=len(found.quantities),
            )
        )
        conflicts += [
            ConflictEntry(
                drawing_id=entry.drawing_id,
                file=entry.file,
                quantity=row.key,
                label=row.label,
                conflict=row.conflict,
                settled=row.settled,
                needs_person=row.needs_person,
                signed=row.signed,
                value=row.value,
            )
            for row in disputes(found.quantities)
            if row.conflict is not None  # always: narrows the type
        ]
    return ProjectReview(drawings=drawings, conflicts=conflicts)


def _start(ingest: Ingest, name: str, data: bytes, fresh: bool = False) -> Started:
    project_id = ingest.start(name=name, data=data, fresh=fresh)
    status = ingest.status(project_id)
    return Started(
        id=project_id, name=status.name, state=status.state, url=f"/api/projects/{project_id}"
    )


def _build_sample(path: Path) -> None:
    """The sample is made by code (scripts/make_sample_archive.py, same bytes every time), so a
    deploy without data/samples builds it here; a temp file and a rename, so a half-written zip
    never shows."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        part = path.with_name(f"{path.name}.{threading.get_ident()}.part")
        part.write_bytes(build_archive())
        part.replace(path)
    except OSError:
        log.exception(
            "can't write the sample archive at %s; build it with `uv run python "
            "scripts/make_sample_archive.py --out <path>` in backend/",
            path,
        )
        raise NotFoundError("The sample project isn't available on this server") from None


def _reset_project(ingest: Ingest, reviews: ReviewStore, project_id: str) -> None:
    try:
        status = ingest.status(project_id)
    except NotFoundError:
        return
    for file in status.files:
        if file.drawing_id is not None:
            reviews.update(status.id, file.drawing_id, _cleared)


def _cleared(state: ReviewState) -> ReviewState:
    return reset(state, None)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")

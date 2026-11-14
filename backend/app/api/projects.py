"""Projects: upload a zip or one file, follow its ingest file by file, and the project's review
summary (docs/API.md "Projects and ingest")."""

from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel

from app.adapters.page_render import render_upload
from app.api.deps import FileId, Ingest, IngestDep, ProjectId, ReviewsDep, SettingsDep
from app.api.drawings import IMMUTABLE, checked_width
from app.api.takeoff import takeoff_rows
from app.api.views import DrawingEntry, ProjectView, Rendering, View
from app.core.errors import NotFoundError
from app.core.ingest.model import FileStatus, FileTrace, ProjectStatus
from app.core.pipeline.model import QuantityConflict
from app.core.review.model import ReviewState, Settled
from app.core.review.ports import ReviewStore
from app.core.review.review import reset

router = APIRouter(prefix="/api/projects")

MAX_UPLOAD = 200 * 1024 * 1024  # bytes; a larger body is refused with 413 before ingest sees it
MAX_WAITING = 3  # projects queued or running; one more upload is refused with 429
SAMPLE_NAME = "sample-project.zip"
# The sheet a plan is shown on, in order of preference, after the file it was read from.
SHEET_KINDS = ("pdf_vector", "pdf_scan", "pdf_text", "png_plan", "jpeg_plan", "photo_plan")
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


class ProjectReview(View):
    drawings: list[DrawingReview]
    conflicts: list[ConflictEntry]


class _Sample(BaseModel):
    """What the API remembers of the sample: the last project made from it (api/sample.json)."""

    project_id: str


@router.get("")
def project_list(ingest: IngestDep) -> ProjectList:
    """Every project, newest first."""
    return ProjectList(
        projects=[
            ProjectSummary(
                id=status.id,
                name=status.name,
                state=status.state,
                created_at=status.created_at,
                files=len(status.files),
                drawings=len(drawings_of(status)),
            )
            for status in ingest.projects()
        ]
    )


@router.post("", status_code=202)
async def upload(
    request: Request,
    ingest: IngestDep,
    name: Annotated[str, Query(min_length=1, max_length=255)],
) -> Started:
    """The request body is the file's bytes (a zip or one drawing file); `name` its file name."""
    _not_busy(request, ingest)
    data = bytearray()
    async for chunk in request.stream():
        data += chunk
        if len(data) > MAX_UPLOAD:
            raise HTTPException(413, f"the upload is over {MAX_UPLOAD // 2**20} MB")
    return _start(request, ingest, name, bytes(data))


@router.post("/sample", status_code=202)
def sample(
    request: Request,
    ingest: IngestDep,
    reviews: ReviewsDep,
    settings: SettingsDep,
    fresh: bool = False,
) -> Started:
    """The synthetic sample archive. `fresh`: the review edits of the last sample run are reset."""
    _not_busy(request, ingest)
    if not settings.sample_archive.is_file():
        raise NotFoundError(
            "the sample archive is not built: run `uv run python scripts/make_sample_archive.py` "
            "in backend/"
        )
    record = settings.projects_dir / "api" / "sample.json"
    if fresh and record.is_file():
        _reset_project(ingest, reviews, _Sample.model_validate_json(record.read_text()).project_id)
    started = _start(request, ingest, SAMPLE_NAME, settings.sample_archive.read_bytes(), fresh)
    _write(record, _Sample(project_id=started.id).model_dump_json())
    return started


@router.get("/{project_id}")
def project(project_id: ProjectId, ingest: IngestDep) -> ProjectView:
    status = ingest.status(project_id)
    return ProjectView(**status.model_dump(), drawings=drawings_of(status))


@router.get("/{project_id}/files/{file_id}/trace")
def trace(project_id: ProjectId, file_id: FileId, ingest: IngestDep) -> FileTrace:
    return ingest.trace(project_id, file_id)


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
    drawings: list[DrawingReview] = []
    conflicts: list[ConflictEntry] = []
    for entry in drawings_of(ingest.status(project_id)):
        found = takeoff_rows(entry.drawing_id, ingest, reviews, zeros=False)
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
            )
            for row in found.quantities
            if row.conflict is not None
        ]
    return ProjectReview(drawings=drawings, conflicts=conflicts)


def drawings_of(status: ProjectStatus) -> tuple[DrawingEntry, ...]:
    """One entry per group of renderings: the sheet it was read from when that is a sheet, else
    PDF before PNG before JPEG; the group's other drawings are its other renderings. A group with
    the same content as one listed before is the same drawing: its files join that entry's other
    renderings, so every name the drawing was uploaded under is shown."""
    groups: dict[str, list[FileStatus]] = {}
    for file in status.files:
        if file.drawing_id is not None:
            groups.setdefault(file.group or file.path, []).append(file)
    entries: dict[str, tuple[str, FileStatus, list[FileStatus]]] = {}  # by drawing id
    for group, files in groups.items():
        primary = min(files, key=_preference)
        assert primary.drawing_id is not None
        if primary.drawing_id in entries:  # the same content under another name
            entries[primary.drawing_id][2].extend(files)
            continue
        others = [file for file in files if file is not primary]
        entries[primary.drawing_id] = (group, primary, others)
    return tuple(
        DrawingEntry(
            drawing_id=drawing_id,
            group=group,
            file=primary.path,
            kind=primary.kind,
            route=primary.route,
            source=primary.source,
            state=primary.state,
            other_renderings=[
                Rendering(drawing_id=file.drawing_id, file=file.path)
                for file in others
                if file.drawing_id is not None
            ],
        )
        for drawing_id, (group, primary, others) in entries.items()
    )


def _preference(file: FileStatus) -> tuple[bool, bool, int]:
    sheet = file.kind in SHEET_KINDS
    order = SHEET_KINDS.index(file.kind) if file.kind in SHEET_KINDS else len(SHEET_KINDS)
    return (not sheet, file.path != file.source, order)


def _start(
    request: Request, ingest: Ingest, name: str, data: bytes, fresh: bool = False
) -> Started:
    project_id = ingest.start(name=name, data=data, fresh=fresh)
    request.app.state.started.append(project_id)
    status = ingest.status(project_id)
    return Started(
        id=project_id, name=status.name, state=status.state, url=f"/api/projects/{project_id}"
    )


def _not_busy(request: Request, ingest: Ingest) -> None:
    started: list[str] = request.app.state.started
    waiting = [pid for pid in started if ingest.status(pid).state in ("queued", "running")]
    started[:] = waiting  # a finished project stays finished
    if len(waiting) >= MAX_WAITING:
        raise HTTPException(429, f"{len(waiting)} projects are still being ingested; try again")


def _reset_project(ingest: Ingest, reviews: ReviewStore, project_id: str) -> None:
    try:
        status = ingest.status(project_id)
    except NotFoundError:
        return
    for file in status.files:
        if file.drawing_id is not None:
            reviews.update(file.drawing_id, _cleared)


def _cleared(state: ReviewState) -> ReviewState:
    return reset(state, None)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")

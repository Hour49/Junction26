"""Projects: upload a zip or one file, follow its ingest file by file, and the project's review
summary (docs/API.md "Projects and ingest")."""

import gzip
import logging
import threading
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, Any, Literal, NamedTuple

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.adapters.ifc_model.glb import GlbModels
from app.adapters.page_render import render_upload
from app.api.ask import page_images
from app.api.deps import (
    AnsweringDep,
    CreditsDep,
    FileId,
    Ingest,
    IngestDep,
    Models3dDep,
    ProjectId,
    ReviewsDep,
    SettingsDep,
    now,
)
from app.api.drawings import IMMUTABLE, checked_width, file_credit
from app.api.issue_answers import answers
from app.api.issues import open_count
from app.api.questions import ProjectQuestions, listed, log_size
from app.api.takeoff import Takeoff, takeoff_rows
from app.api.views import (
    SHEET_KINDS,
    ErrorBody,
    ProjectTrace,
    ProjectView,
    View,
    drawings_of,
    expected_drawings_of,
    not_plans_of,
    skipped_of,
)
from app.core.errors import NotFoundError
from app.core.ingest.model import (
    FileStatus,
    FileTrace,
    Overrule,
    ProjectStatus,
    ReadAsPlan,
    SecondCount,
)
from app.core.pipeline.model import QuantityConflict
from app.core.review import conflict_card
from app.core.review.model import Resolved, ReviewState, Settled, SignOff, is_none
from app.core.review.ports import Resolver, ReviewStore
from app.core.review.resolve import resolve_conflicts
from app.core.review.review import NotAllowedError, disputes, reset
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
    # RESOLVER: conflicts a model picked a value for that no person settled or signed (not in
    # conflicts_open; a cannot_tell stays open); None until `done`; left out of the JSON while
    # RESOLVER is off and no pick is kept
    conflicts_picked: int | None = Field(default=None, exclude_if=is_none)
    # Issues in state open (GET …/issues without a pack, decision 0008); None until `done`
    issues_open: int | None = None
    # Of those, the ones that wait for a person's answer: not a note, not answered
    issues_to_answer: int | None = None
    # Files triage called not a floor plan (decision 0010); None until `done`; left out of the
    # JSON when triage is off
    not_plans: int | None = Field(default=None, exclude_if=lambda value: value is None)


class RelevanceRequest(View):
    """A person's call on a triaged file's relevance (decision 0010). `by` as a sign-off's;
    `undo` takes the call back and, like unsettle, needs nothing else."""

    verdict: Literal["related", "unrelated"] | None = None  # not with undo
    by: str | None = Field(default=None, min_length=1, max_length=100)
    undo: bool = False

    @model_validator(mode="after")
    def _complete(self) -> "RelevanceRequest":
        if not self.undo and (self.verdict is None or self.by is None):
            raise ValueError("a verdict and by are needed, unless undo")
        if self.undo and self.verdict is not None:
            raise ValueError("undo takes no verdict")
        return self


class TriageRequest(View):
    """A person's call that a file triage set aside is a floor plan (decision 0010): it is read
    as one. `by` as a sign-off's."""

    model_config = ConfigDict(extra="forbid", serialize_by_alias=True)

    class_: Literal["floor_plan"] = Field(alias="class")
    by: str = Field(min_length=1, max_length=100)


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
    title: str  # the conflict as a question, in plain words ("Door count: 13 or 11?")
    why: str  # what each method read and how it is decided (a rule, or a person has to choose)
    suggestions: list[str]  # short answers a person can tap, one per value read ("13 doors")
    # RESOLVER: what a model said about this conflict (a pick is the value in use until a person
    # settles or signs it); left out of the JSON when None
    resolved: Resolved | None = Field(default=None, exclude_if=is_none)


class ProjectReview(View):
    drawings: list[DrawingReview]
    conflicts: list[ConflictEntry]


class Resolving(View):
    """POST /api/projects/{id}/resolve: the review after the resolver's replies, and a note for
    each conflict it gave no reply on (the budget used up, a timeout...)."""

    review: ProjectReview
    notes: list[str]


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
    issues_to_answer: int


class OpenCounts(NamedTuple):
    conflicts_open: int | None
    conflicts_picked: int | None
    issues_open: int | None
    issues_to_answer: int | None


class KeptReviews:
    """Each done project's review and open issue count for the project list (R4-c-2:
    recomputing every review on every list call took 15-40 s with 18 projects). One is kept
    until what it is made of changes: the project's status, the size of its question log
    (refused answers are issues; the log is only appended to), or for one of its drawings the
    upload that wrote it last (a drawing is shared by content, so another project's ingest may
    write it again) or its review edits, or its issue answers. All are read on every call, so
    every review write (settle, sign-off, add, reject, restore, reset), every ask and every
    answer is seen, whoever wrote it."""

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
        said = answers(settings.projects_dir, status.id)
        key = (status, drawings, asked, said)  # read before the counts: they are never newer
        with self._lock:
            kept = self._kept.get(status.id)
        if kept is not None and kept[0] == key:
            return kept[1]
        takeoffs = takeoffs_of(status, ingest, reviews)  # once, for the review and the issues
        found = Counts(
            review_of(status, ingest, reviews, takeoffs),
            *open_count(status, ingest, reviews, settings, takeoffs),
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
            summary_of(
                status,
                kept.counts(status, ingest, reviews, settings),
                settings.resolver != "off",
            )
            for status in statuses
        ]
    )


def open_counts(found: Counts | None, resolver_on: bool = False) -> OpenCounts:
    """`found`: the project's counts, for a `done` project; else every count is None.
    `resolver_on`: RESOLVER is not off, so `conflicts_picked` is given even when 0."""
    if found is None:
        return OpenCounts(None, None, None, None)
    conflicts = found.review.conflicts
    conflicts_open = sum(entry.needs_person for entry in conflicts)
    picked = sum(
        entry.resolved is not None
        and entry.resolved.verdict == "picked"
        and not entry.needs_person  # the pick is in use: no mark edit, no rule
        and entry.settled is None
        and entry.signed is None
        for entry in conflicts
    )
    shown = picked if picked or resolver_on else None
    return OpenCounts(conflicts_open, shown, found.issues_open, found.issues_to_answer)


def summary_of(
    status: ProjectStatus, found: Counts | None, resolver_on: bool = False
) -> ProjectSummary:
    """`found`: the project's counts, for a `done` project."""
    to_review = None
    if found is not None:
        to_review = sum(drawing.to_review for drawing in found.review.drawings)
    return ProjectSummary(
        id=status.id,
        name=status.name,
        state=status.state,
        created_at=status.created_at,
        files=len(status.files),
        drawings=len(drawings_of(status)),
        to_review=to_review,
        **open_counts(found, resolver_on)._asdict(),
        not_plans=not_plans_of(status),
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
        _resolve_when_done(request.app.state, started.id)
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
    _resolve_when_done(request.app.state, started.id)
    return started


@router.get("/{project_id}")
def project(
    request: Request,
    project_id: ProjectId,
    ingest: IngestDep,
    reviews: ReviewsDep,
    settings: SettingsDep,
    credits: CreditsDep,
    models_3d: Models3dDep,
) -> ProjectView:
    # here, not at the top: plan_tools imports this module (through pipeline_tools)
    from app.adapters.plan_tools import PipelineStore, not_drawable

    status = ingest.status(project_id)
    files = {file.path: file for file in status.files}
    kept: KeptReviews = request.app.state.kept_reviews
    store = PipelineStore.of_app(request.app, project_id)
    drawings = drawings_of(status, lambda path: file_credit(path, files, credits))
    return ProjectView(
        **with_models_3d(status, models_3d).model_dump(),
        drawings=tuple(
            entry.model_copy(update={"drawable": why is None, "not_drawable_reason": why})
            for entry in drawings
            for why in [not_drawable(store, entry)]
        ),
        skipped=skipped_of(status),
        expected_drawings=expected_drawings_of(status),
        not_plans=not_plans_of(status),
        **open_counts(
            kept.counts(status, ingest, reviews, settings), settings.resolver != "off"
        )._asdict(),
    )


@router.post("/{project_id}/files", status_code=202)
async def add_file(
    request: Request,
    project_id: ProjectId,
    ingest: IngestDep,
    name: Annotated[str, Query(min_length=1, max_length=255)],
) -> FileStatus:
    """A photo added to a finished project from the chat (board #203). The body is the image's
    bytes, png or jpeg; `name` its file name. It is read in the background, alone, while the
    project stays done. Returns the new file, queued; poll the project. 404 unknown project,
    409 until the project is done or while a file of it is read, 413 over the upload limit, 415
    not a png or jpeg."""
    data = bytearray()
    async for chunk in request.stream():
        data += chunk
        if len(data) > MAX_UPLOAD:
            raise HTTPException(413, f"the upload is over {MAX_UPLOAD // 2**20} MB")
    return ingest.add_file(project_id, name, bytes(data))


@router.post("/{project_id}/files/{file_id}/relevance")
def relevance(
    project_id: ProjectId,
    file_id: FileId,
    body: RelevanceRequest,
    ingest: IngestDep,
) -> FileStatus:
    """A person says whether a file triage set aside belongs to the project, or takes that back
    (`undo`; with no call made, nothing changes). The file stays set aside either way: a call
    is no reading. Any file triage called not a floor plan takes a call, described and judged
    or not. 409 until the project is done; 422 `not-triaged` for a file triage did not set
    aside as not a floor plan."""
    if body.undo:
        return ingest.overrule(project_id, file_id, None)
    assert body.verdict is not None and body.by is not None  # checked by the model
    call = Overrule(verdict=body.verdict, by=body.by, at=now())
    return ingest.overrule(project_id, file_id, call)


@router.post("/{project_id}/files/{file_id}/triage", status_code=202)
def triage(
    project_id: ProjectId, file_id: FileId, body: TriageRequest, ingest: IngestDep
) -> FileStatus:
    """A person has a file triage set aside read as a floor plan: it is read in the background,
    alone, while the project stays done. Returns the file, queued; poll the project. 409 until
    the project is done or while a file of it is read again; 422 `not-triaged` for a file triage
    did not set aside as not a floor plan. A sheet the sheet-kind step doubted (flagged) was read
    already: its flag is dropped at once, nothing is read again. No undo: a reading is not
    unread."""
    return ingest.read_as_plan(project_id, file_id, ReadAsPlan(by=body.by, at=now()))


@router.get("/{project_id}/files/{file_id}/trace")
def trace(
    project_id: ProjectId, file_id: FileId, ingest: IngestDep, models_3d: Models3dDep
) -> FileTrace:
    return trace_view(ingest.trace(project_id, file_id), ingest, models_3d)


@router.get("/{project_id}/trace")
def project_trace(project_id: ProjectId, ingest: IngestDep, models_3d: Models3dDep) -> ProjectTrace:
    """Every file's trace in one request, in the order the upload lists the files."""
    return ProjectTrace(
        project_id=project_id,
        files=[trace_view(found, ingest, models_3d) for found in ingest.traces(project_id)],
    )


def trace_view(found: FileTrace, ingest: Ingest, models: GlbModels | None = None) -> FileTrace:
    """The trace with its file's second count, read from the drawing's conflicts, and its 3D
    view's state (MODEL_3D)."""
    second = None
    drawing_id = found.file.drawing_id
    if drawing_id is not None:
        measured = ingest.drawing(drawing_id).conflicts
        if measured is not None:
            second = SecondCount(
                measured=len(measured),
                conflicts=sum(entry.status == "conflict" for entry in measured),
            )
    return found.model_copy(
        update={"second_count": second, "file": with_model_3d(found.file, models)}
    )


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


def with_models_3d(status: ProjectStatus, models: GlbModels | None) -> ProjectStatus:
    """Each IFC file with its 3D view's state (MODEL_3D); off, the status as it is."""
    if models is None:
        return status
    return status.model_copy(
        update={"files": tuple(with_model_3d(file, models) for file in status.files)}
    )


def with_model_3d(file: FileStatus, models: GlbModels | None) -> FileStatus:
    """An IFC file with its 3D view's state (MODEL_3D); off, or any other file, as it is."""
    if models is None or file.kind != "ifc" or file.sha256 is None:
        return file
    return file.model_copy(update={"model_3d": models.status(file.sha256)})


@router.get(
    "/{project_id}/files/{file_id}/model.glb",
    response_class=Response,
    responses={
        200: {"content": {"model/gltf-binary": {}}, "description": "the model's GLB"},
        404: {"model": ErrorBody, "description": "no such file, no IFC file, or MODEL_3D off"},
        409: {"model": ErrorBody, "description": "code converting: being built, ask again"},
        422: {"model": ErrorBody, "description": "code too_big, no_geometry or failed: no view"},
    },
)
def model_glb(
    request: Request,
    project_id: ProjectId,
    file_id: FileId,
    ingest: IngestDep,
    models_3d: Models3dDep,
) -> Response:
    """An IFC file's 3D view: one GLB of the whole model, each node named by its element's
    GlobalId. The first request starts its conversion (409 `converting` until it is built; poll
    it or the project's `model_3d`); gzipped when the client takes gzip."""
    file = ingest.trace(project_id, file_id).file
    if models_3d is None or file.kind != "ifc" or file.sha256 is None:
        raise NotFoundError(f"file {file_id} has no 3D view")
    sha256 = file.sha256
    found = models_3d.start(sha256, lambda: ingest.upload_bytes(project_id, file_id))
    if found.state == "unavailable":
        assert found.code is not None
        return JSONResponse(
            status_code=422,
            content=ErrorBody(detail=found.reason, code=found.code).model_dump(exclude_none=True),
        )
    if found.state != "ready":
        body = ErrorBody(detail=f"the 3D view of {file.path} is being built", code="converting")
        return JSONResponse(status_code=409, content=body.model_dump(exclude_none=True))
    zipped = models_3d.glb_gz(sha256).read_bytes()
    headers = {"Cache-Control": IMMUTABLE, "Vary": "Accept-Encoding"}
    if "gzip" in request.headers.get("accept-encoding", ""):
        headers["Content-Encoding"] = "gzip"
        return Response(content=zipped, media_type="model/gltf-binary", headers=headers)
    return Response(gzip.decompress(zipped), media_type="model/gltf-binary", headers=headers)


@router.get("/{project_id}/review")
def project_review(project_id: ProjectId, ingest: IngestDep, reviews: ReviewsDep) -> ProjectReview:
    """Per drawing what is left to review and what is signed, and every conflict of the project."""
    return review_of(ingest.status(project_id), ingest, reviews)


@router.post("/{project_id}/resolve")
def resolve(
    project_id: ProjectId, ingest: IngestDep, reviews: ReviewsDep, answering: AnsweringDep
) -> Resolving:
    """RESOLVER: a model looks at each conflict no rule decides and no person settled, and picks
    a value or says it can't tell; one call per conflict, replies kept with the project's review,
    so a second POST asks only about what changed. 409 when RESOLVER is off or before `done`.
    It also runs on its own when an upload's ingest is done (`_resolve_when_done`)."""
    resolver = answering.resolver
    if resolver is None:
        raise NotAllowedError("RESOLVER is off: no model resolves conflicts on this server")
    status = ingest.status(project_id)
    if status.state != "done":
        raise NotAllowedError(f"project {project_id} is {status.state}; resolve it when done")
    notes = resolve_project(status, ingest, reviews, resolver)
    return Resolving(review=review_of(ingest.status(project_id), ingest, reviews), notes=notes)


def resolve_project(
    status: ProjectStatus, ingest: Ingest, reviews: ReviewStore, resolver: Resolver
) -> list[str]:
    """Asks the resolver about every conflict of the done project that needs a person and has
    no reply yet, and keeps the replies; the notes of the ones that got none."""
    notes: list[str] = []
    for entry in drawings_of(status):
        rows = takeoff_rows(entry.drawing_id, ingest, reviews, zeros=False, project=status.id)
        state = reviews.get(status.id, entry.drawing_id)
        found, said = resolve_conflicts(
            entry.drawing_id,
            rows.quantities,
            state,
            resolver,
            page_images(ingest, entry.drawing_id),
        )
        notes += [f"{entry.file}: {note}" for note in said]
        if found:
            reviews.update(
                status.id,
                entry.drawing_id,
                lambda kept, found=found: kept.model_copy(
                    update={"resolved": {**kept.resolved, **found}}
                ),
            )
    return notes


def _resolve_when_done(state: Any, project_id: str) -> None:
    """With RESOLVER on, the project's conflicts are resolved once its ingest is done: at once
    when it already is (an ingest run inline), else on a thread that waits for it."""
    resolver: Resolver | None = state.answering.resolver
    if resolver is None:
        return
    ingest: Ingest = state.ingest
    reviews: ReviewStore = state.reviews

    def run() -> None:
        try:
            status = ingest.wait(project_id)
            if status.state == "done":
                for note in resolve_project(status, ingest, reviews, resolver):
                    log.info("resolver, project %s: %s", project_id, note)
        except Exception:  # a thread's bug is logged; the POST stays to try again
            log.exception("resolving project %s after its ingest failed", project_id)

    if ingest.status(project_id).state in ("done", "failed"):
        run()
    else:
        threading.Thread(target=run, name=f"resolve-{project_id}", daemon=True).start()


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
                title=conflict_card.title(row),
                why=conflict_card.why(row),
                suggestions=conflict_card.suggestions(row),
                resolved=row.resolved,
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

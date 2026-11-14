"""What the routes get through `Depends`: the services `create_app` keeps on `app.state`, and the
ids of the paths, checked against their pattern so an id never reaches a disk path unchecked."""

import re
from datetime import UTC, datetime
from typing import Annotated, Protocol

from fastapi import Depends, Request

from app.composition import Answering
from app.core.drawing.model import Drawing
from app.core.errors import NotFoundError
from app.core.ingest.model import DrawingInfo, FileTrace, ProjectStatus, SheetFile
from app.core.review.ports import ReviewStore
from app.settings import Settings

PROJECT_ID = re.compile(r"[0-9a-f]{12}")
FILE_ID = re.compile(r"f[0-9]{1,6}")
DRAWING_ID = re.compile(r"[0-9a-f]{16}")


class Ingest(Protocol):
    """The part of ingest's `IngestService` the API calls (.agents/ingest.md, "Interface")."""

    def start(self, name: str, data: bytes, fresh: bool = False) -> str: ...

    def status(self, project_id: str) -> ProjectStatus: ...

    def projects(self) -> tuple[ProjectStatus, ...]: ...

    def trace(self, project_id: str, file_id: str) -> FileTrace: ...

    def drawing(self, drawing_id: str) -> Drawing: ...

    def drawing_info(self, drawing_id: str) -> DrawingInfo: ...

    def sheet(self, drawing_id: str) -> SheetFile: ...

    def upload_bytes(self, project_id: str, file_id: str) -> bytes: ...

    def close(self) -> None: ...


class Credits(Protocol):
    """The licence credit of a file found by its content (app/adapters/credits.py)."""

    def of(self, size: int, sha256: str) -> str | None: ...


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_ingest(request: Request) -> Ingest:
    return request.app.state.ingest


def get_reviews(request: Request) -> ReviewStore:
    return request.app.state.reviews


def get_credits(request: Request) -> Credits:
    return request.app.state.credits


def get_answering(request: Request) -> Answering:
    return request.app.state.answering


def now() -> str:
    """The time an edit is recorded with: ISO 8601, UTC, to the second."""
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _checked(value: str, pattern: re.Pattern[str], what: str) -> str:
    if not pattern.fullmatch(value):
        raise NotFoundError(f"no {what} {value!r}")
    return value


def _project_id(project_id: str) -> str:
    return _checked(project_id, PROJECT_ID, "project")


def _file_id(file_id: str) -> str:
    return _checked(file_id, FILE_ID, "file")


def drawing_id_of(drawing_id: str) -> str:
    return _checked(drawing_id, DRAWING_ID, "drawing")


ProjectId = Annotated[str, Depends(_project_id)]
FileId = Annotated[str, Depends(_file_id)]
DrawingId = Annotated[str, Depends(drawing_id_of)]
IngestDep = Annotated[Ingest, Depends(get_ingest)]
ReviewsDep = Annotated[ReviewStore, Depends(get_reviews)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
AnsweringDep = Annotated[Answering, Depends(get_answering)]
CreditsDep = Annotated[Credits, Depends(get_credits)]

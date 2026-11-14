"""App factory. Run from backend/: `uv run uvicorn app.main:create_app --factory --reload`.

The HTTP API is docs/API.md. The frontend's dev server proxies `/api` here, so no CORS is set
(docs/ENGINEERING.md section 1 keeps CORS out). uvicorn binds to 127.0.0.1 unless told otherwise.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.adapters.credits import DatasetCredits
from app.adapters.review_store import JsonReviewStore
from app.api import ask, drawings, health, info, projects, takeoff
from app.api.deps import Ingest
from app.api.views import ErrorBody
from app.composition import build_answering, build_ingest
from app.core.errors import DomainError, InvalidInputError, NotFoundError
from app.core.review.review import NotAllowedError
from app.settings import Settings

# The only place a domain error becomes an HTTP status. An unmapped one stays a 500, like any bug.
STATUS_BY_ERROR: dict[type[DomainError], int] = {
    NotFoundError: 404,
    InvalidInputError: 422,
    NotAllowedError: 409,
}
CODES = {
    404: "not-found",
    405: "method-not-allowed",
    409: "not-allowed",
    413: "too-large",
    422: "invalid",
    429: "busy",
}
log = logging.getLogger(__name__)


def _error(
    status: int, detail: str, code: str, errors: list[dict[str, object]] | None = None
) -> JSONResponse:
    body = ErrorBody(detail=detail, code=code, errors=errors)
    return JSONResponse(status_code=status, content=body.model_dump(exclude_none=True))


def domain_error_response(request: Request, exc: Exception) -> JSONResponse:
    status = next(code for error, code in STATUS_BY_ERROR.items() if isinstance(exc, error))
    return _error(status, str(exc), CODES[status])


def http_error_response(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, HTTPException)
    return _error(exc.status_code, str(exc.detail), CODES.get(exc.status_code, "error"))


def validation_error_response(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    detail = "; ".join(
        f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}" for error in exc.errors()
    )
    return _error(422, detail, "validation", jsonable_encoder(exc.errors()))


def internal_error_response(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    return _error(500, "internal error", "internal")


def create_app(settings: Settings | None = None, ingest: Ingest | None = None) -> FastAPI:
    """`ingest`: the project ingest to serve; by default the settings' one, in the background."""
    settings = settings or Settings()
    logging.basicConfig(level=settings.log_level)
    service = ingest or build_ingest(settings, settings.projects_dir)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        service.close()

    app = FastAPI(title="Hour49 backend", lifespan=lifespan)
    app.state.settings = settings  # adapters' providers build their clients from it
    app.state.ingest = service
    app.state.reviews = JsonReviewStore(settings.projects_dir / "api" / "reviews")
    app.state.answering = build_answering(settings)
    app.state.credits = DatasetCredits(
        settings.credit_dataset, settings.credit_photos, settings.sample_archive
    )
    app.state.admission = projects.Admission()  # the 429 limit
    for router in (health, info, projects, drawings, ask, takeoff):
        app.include_router(router.router)
    for error in STATUS_BY_ERROR:
        app.add_exception_handler(error, domain_error_response)
    app.add_exception_handler(HTTPException, http_error_response)
    app.add_exception_handler(RequestValidationError, validation_error_response)
    app.add_exception_handler(Exception, internal_error_response)
    return app

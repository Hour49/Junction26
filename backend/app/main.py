"""App factory. Run from backend/: `uv run uvicorn app.main:create_app --factory --reload`."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api import health
from app.core.errors import DomainError, NotFoundError
from app.settings import Settings

# The only place a domain error becomes an HTTP status. An unmapped one stays a 500, like any bug.
STATUS_BY_ERROR: dict[type[DomainError], int] = {NotFoundError: 404}


def domain_error_response(request: Request, exc: Exception) -> JSONResponse:
    status = next(code for error, code in STATUS_BY_ERROR.items() if isinstance(exc, error))
    return JSONResponse(status_code=status, content={"detail": str(exc)})


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    logging.basicConfig(level=settings.log_level)
    app = FastAPI(title="Hour49 backend")
    app.state.settings = settings  # adapters' providers build their clients from it
    app.include_router(health.router)
    for error in STATUS_BY_ERROR:
        app.add_exception_handler(error, domain_error_response)
    return app

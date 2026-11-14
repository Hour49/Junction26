"""Domain errors become their mapped HTTP status; anything else stays a 500, never a 200."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import DomainError, NotFoundError


class UnmappedError(DomainError):
    pass


def get_raising(app: FastAPI, exc: Exception) -> tuple[int, str]:
    def route() -> None:
        raise exc

    app.add_api_route("/raise", route)
    response = TestClient(app, raise_server_exceptions=False).get("/raise")
    return response.status_code, response.text


def test_mapped_domain_error_becomes_its_status(app: FastAPI) -> None:
    status, body = get_raising(app, NotFoundError("document 7"))
    assert status == 404
    assert body == '{"detail":"document 7","code":"not-found"}'


def test_unexpected_exception_is_a_500(app: FastAPI) -> None:
    status, _ = get_raising(app, RuntimeError("bug"))
    assert status == 500


def test_unmapped_domain_error_is_a_500(app: FastAPI) -> None:
    status, _ = get_raising(app, UnmappedError("no status chosen"))
    assert status == 500

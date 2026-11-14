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


DOCUMENTED_CODES = {
    "not-found",
    "invalid",
    "validation",
    "not-allowed",
    "too-large",
    "busy",
    "method-not-allowed",
    "internal",
}  # docs/API.md "Errors"


def test_wrong_method_has_a_documented_code(app: FastAPI) -> None:
    response = TestClient(app).get("/api/ask")  # POST only
    assert response.status_code == 405
    assert response.json() == {"detail": "Method Not Allowed", "code": "method-not-allowed"}


def test_unknown_route_has_a_documented_code(app: FastAPI) -> None:
    response = TestClient(app).get("/api/nope")
    assert response.status_code == 404
    assert response.json()["code"] == "not-found"


def test_every_mapped_code_is_documented() -> None:
    from pathlib import Path

    from app.main import CODES

    api_md = (Path(__file__).parents[2] / "docs" / "API.md").read_text(encoding="utf-8")
    errors = api_md.split("### Errors", 1)[1].split("\n## ", 1)[0]
    assert set(CODES.values()) <= DOCUMENTED_CODES
    for code in DOCUMENTED_CODES:
        assert f"`{code}`" in errors or f'"code": "{code}"' in errors, code

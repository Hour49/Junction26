from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_get_health_returns_ok(app: FastAPI) -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_post_health_is_refused(app: FastAPI) -> None:
    assert TestClient(app).post("/health").status_code == 405

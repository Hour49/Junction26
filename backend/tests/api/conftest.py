"""Fixtures of the API tests: an app on a temporary projects folder, with the real ingest run
inside each upload (no background thread), so every test is deterministic."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_vector_pdf import swiss_sheet

from app.composition import build_ingest
from app.main import create_app
from app.settings import Settings


@pytest.fixture
def settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.chdir(tmp_path)  # so a developer's backend/.env can't change test results
    return Settings(
        projects_dir=tmp_path / "projects",
        sample_archive=tmp_path / "sample-project.zip",
        credit_dataset=tmp_path / "dataset",  # absent unless a test writes it: no credits
        credit_photos=tmp_path / "photos",
    )


@pytest.fixture
def client(settings: Settings) -> TestClient:
    ingest = build_ingest(settings, settings.projects_dir, background=False)
    return TestClient(create_app(settings, ingest))


@pytest.fixture
def plan_pdf() -> bytes:
    """A synthetic swiss-style plan: 2 doors, 2 windows, 6 rooms, scale 1:100 (test_vector_pdf)."""
    return swiss_sheet().pdf()


def upload(client: TestClient, data: bytes, name: str = "plan.pdf") -> str:
    response = client.post("/api/projects", params={"name": name}, content=data)
    assert response.status_code == 202, response.text
    return response.json()["id"]


@pytest.fixture
def drawing_id(client: TestClient, plan_pdf: bytes) -> str:
    project = client.get(f"/api/projects/{upload(client, plan_pdf)}").json()
    return project["drawings"][0]["drawing_id"]

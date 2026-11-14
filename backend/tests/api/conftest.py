"""Fixtures of the API tests: an app on a temporary projects folder, with the real ingest run
inside each upload (no background thread), so every test is deterministic."""

import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
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


def plan_png() -> bytes:
    """A drawing as an image: dark outlines on white paper (a blank page is set aside)."""
    image = Image.new("RGB", (800, 400), "white")
    draw = ImageDraw.Draw(image)
    for x in range(50, 750, 100):
        draw.rectangle((x, 50, x + 80, 350), outline="black", width=3)
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


@pytest.fixture
def drawing_id(client: TestClient, plan_pdf: bytes) -> str:
    project = client.get(f"/api/projects/{upload(client, plan_pdf)}").json()
    return project["drawings"][0]["drawing_id"]


def raster_arm(folder: Path, name: str) -> None:
    """A precomputed raster arm with a file for the upload `name`: two doors and two bedrooms,
    each bedroom with its own printed name (as a CubiCasa sheet labels them)."""
    folder.mkdir(parents=True, exist_ok=True)
    box = [[0.05, 0.1, 0.1, 0.2], [0.6, 0.1, 0.65, 0.2]]
    rooms = [[0.1, 0.1, 0.45, 0.9], [0.55, 0.1, 0.9, 0.9]]
    drawing = {
        "schema": "extraction_v1",
        "file": name,
        "split": "dev",
        "truth": "elements",
        "pages": [{"page": 1, "width": 800, "height": 400, "unit": "px"}],
        "scale": {"status": "no_scale"},
        "plans": [{"id": "p1", "page": 1, "box": [0.0, 0.0, 1.0, 1.0]}],
        "elements": [{"id": f"d{at}", "class": "door", "page": 1, "plan": "p1", "box": found}
                     for at, found in enumerate(box, start=1)],
        "rooms": [{"id": f"r{at}", "type": "bedroom", "label": f"Makuuhuone {at}", "page": 1,
                   "plan": "p1", "box": found}
                  for at, found in enumerate(rooms, start=1)],
    }  # fmt: skip
    (folder / f"{Path(name).stem}.json").write_text(json.dumps(drawing), encoding="utf-8")


@pytest.fixture
def raster(settings: Settings) -> tuple[TestClient, str]:
    """An app whose raster route reads a precomputed arm, and the drawing id of a PNG it read."""
    raster_arm(settings.projects_dir.parent / "arm", "plan.png")
    settings = settings.model_copy(
        update={
            "extractor_raster": "composite",
            "raster_components": "elements=dir:arm,plans=dir:arm,rooms=dir:arm",
        }
    )
    client = TestClient(
        create_app(settings, build_ingest(settings, settings.projects_dir, background=False))
    )
    project = client.get(f"/api/projects/{upload(client, plan_png(), 'plan.png')}").json()
    return client, project["drawings"][0]["drawing_id"]

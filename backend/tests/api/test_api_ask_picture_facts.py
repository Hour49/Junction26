"""POST /api/ask and the project chat on a services picture with DISCIPLINE_PICTURES on: the
lane's kept fact sheet for the page (`<cache>/<sha256>-<CODE>.json`) answers what the takeoff
can't, as the batch pipeline's facts do (composition._facts). R1 services-second, 2026-11-15:
H-101 kept 29 radiators and the Ask said "I don't count radiators"."""

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.adapters.discipline_pictures.lane import PictureFactSheet, PictureSheets, kept_in
from app.composition import build_ingest
from app.core.ifc_facts import Fact
from app.main import create_app
from app.settings import Settings

RADIATORS = "How many radiators are there?"


def picture_project(settings: Settings, kept: bool) -> tuple[TestClient, dict[str, Any], str]:
    """The sample project with IFC_FACTS and DISCIPLINE_PICTURES on, and (`kept`) a lane sheet
    of 29 radiators kept for its first picture. Returns the client, the project, the picture's
    drawing id."""
    settings = settings.model_copy(
        update={
            "ifc_facts": True,
            "discipline_pictures": "template",
            "discipline_pictures_cache_dir": settings.projects_dir.parent / "pictures",
        }
    )
    client = TestClient(
        create_app(settings, build_ingest(settings, settings.projects_dir, background=False))
    )
    project = client.get(client.post("/api/projects/sample").json()["url"]).json()
    file = next(f for f in project["files"] if f["path"] == "scans/ground-floor.png")
    drawing = next(d for d in project["drawings"] if d["drawing_id"] == file["drawing_id"])
    if kept:
        cache = kept_in(Path(settings.discipline_pictures_cache_dir), "template")
        heaters = [
            Fact(topic="space_heater.count", subject=subject, value=29, unit="count",
                 discipline="heating", source="picture:vlm:held")
            for subject in ("Radiator", "all")
        ]  # fmt: skip
        PictureSheets(None, cache).put(
            file["sha256"],
            PictureFactSheet(model=file["sha256"][:16], disciplines=["heating"], facts=heaters),
        )
    return client, project, drawing["drawing_id"]


def ask(client: TestClient, project: dict[str, Any], drawing: str, question: str) -> Any:
    body = {"drawing_id": drawing, "question": question, "project_id": project["id"]}
    reply = client.post("/api/ask", json=body)
    assert reply.status_code == 200, reply.text
    return reply.json()


def test_a_picture_with_a_kept_sheet_is_answered_from_it_low(settings: Settings) -> None:
    client, project, drawing = picture_project(settings, kept=True)
    found = ask(client, project, drawing, RADIATORS)
    assert found["refusal"] is None and found["method"] == "facts", found
    assert "Total space heaters: 29" in found["answer"]
    assert "confidence is Low" in (found["explanation"] or ""), found
    assert found["confidence"] is None  # never a certified number


def test_the_project_chat_answers_the_picture_from_its_kept_sheet(settings: Settings) -> None:
    client, project, drawing = picture_project(settings, kept=True)
    asked = client.post(f"/api/projects/{project['id']}/ask", json={"question": RADIATORS})
    assert asked.status_code == 200, asked.text
    parts = {p["drawing_id"]: p["answer"] for p in asked.json()["parts"]}
    assert parts[drawing]["method"] == "facts"
    assert "Total space heaters: 29" in parts[drawing]["answer"]


def test_a_picture_with_no_kept_sheet_is_refused_as_before(settings: Settings) -> None:
    client, project, drawing = picture_project(settings, kept=False)
    found = ask(client, project, drawing, RADIATORS)
    assert found["refusal"] is not None and found["method"] != "facts"


def test_with_pictures_off_a_kept_sheet_is_not_read(settings: Settings) -> None:
    client, project, drawing = picture_project(settings, kept=True)
    off = client.app.state.settings.model_copy(update={"discipline_pictures": "off"})  # type: ignore[attr-defined]
    client = TestClient(create_app(off, build_ingest(off, off.projects_dir, background=False)))
    found = ask(client, project, drawing, RADIATORS)
    assert found["refusal"] is not None and found["method"] != "facts"

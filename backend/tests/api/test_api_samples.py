"""GET /api/projects/samples and POST /api/projects/sample?id= (chat-ux, 2026-11-15)."""

import io
import json
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.settings import Settings


def _zip(plan_pdf: bytes) -> bytes:
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as files:
        files.writestr("plans/flat.pdf", plan_pdf)
    return archive.getvalue()


def _manifest(settings: Settings, *entries: dict[str, object]) -> Path:
    folder = settings.sample_manifest.parent
    folder.mkdir(parents=True, exist_ok=True)
    settings.sample_manifest.write_text(json.dumps({"samples": list(entries)}))
    return folder


FLAT = {"id": "flat", "title": "Mixed", "blurb": "one line", "zip": "flat.zip", "tags": ["PDF"]}


def test_without_a_manifest_only_the_synthetic_sample_is_offered(client: TestClient) -> None:
    listed = client.get("/api/projects/samples").json()["samples"]
    assert [sample["id"] for sample in listed] == ["sample"]


def test_a_broken_manifest_falls_back_to_the_synthetic_sample(
    client: TestClient, settings: Settings
) -> None:
    settings.sample_manifest.parent.mkdir(parents=True)
    settings.sample_manifest.write_text("{not json")
    listed = client.get("/api/projects/samples").json()["samples"]
    assert [sample["id"] for sample in listed] == ["sample"]


def test_the_manifest_samples_are_listed_without_their_zip(
    client: TestClient, settings: Settings
) -> None:
    _manifest(settings, FLAT)
    listed = client.get("/api/projects/samples").json()["samples"]
    assert listed[0] == {
        "id": "flat",
        "title": "Mixed",
        "blurb": "one line",
        "tags": ["PDF"],
        "prompts": [],
    }
    assert [sample["id"] for sample in listed] == ["flat", "sample"]


def test_a_sample_is_started_by_id_and_fresh_resets_its_own_record(
    client: TestClient, settings: Settings, plan_pdf: bytes
) -> None:
    _manifest(settings, FLAT).joinpath("flat.zip").write_bytes(_zip(plan_pdf))
    started = client.post("/api/projects/sample", params={"id": "flat", "fresh": True})
    assert started.status_code == 202
    assert started.json()["name"] == "flat.zip"
    record = settings.projects_dir / "api" / "sample-flat.json"
    assert json.loads(record.read_text())["project_id"] == started.json()["id"]
    assert len(client.get(started.json()["url"]).json()["files"]) == 1
    assert not (settings.projects_dir / "api" / "sample.json").exists()


def test_an_unknown_sample_is_404(client: TestClient, settings: Settings) -> None:
    _manifest(settings, FLAT)
    assert client.post("/api/projects/sample", params={"id": "nope"}).status_code == 404


def test_a_zip_outside_the_manifest_folder_is_refused(
    client: TestClient, settings: Settings, plan_pdf: bytes
) -> None:
    folder = _manifest(settings, {**FLAT, "zip": "../outside.zip"})
    folder.parent.joinpath("outside.zip").write_bytes(_zip(plan_pdf))
    assert client.post("/api/projects/sample", params={"id": "flat"}).status_code == 404


def test_no_id_and_the_sample_id_start_the_synthetic_archive(
    client: TestClient, settings: Settings
) -> None:
    for params in ({}, {"id": "sample"}):
        started = client.post("/api/projects/sample", params=params)
        assert started.status_code == 202
        assert started.json()["name"] == "sample-project.zip"
    assert (settings.projects_dir / "api" / "sample.json").is_file()


ASKS = ["How many doors are on the plan?", "Which rooms have no window?"]


def test_a_project_made_from_a_sample_carries_its_prompts_from_the_manifest_now(
    client: TestClient, settings: Settings, plan_pdf: bytes
) -> None:
    _manifest(settings, {**FLAT, "prompts": ASKS}).joinpath("flat.zip").write_bytes(_zip(plan_pdf))
    assert client.get("/api/projects/samples").json()["samples"][0]["prompts"] == ASKS
    started = client.post("/api/projects/sample", params={"id": "flat", "fresh": True}).json()
    assert client.get(started["url"]).json()["prompts"] == ASKS
    _manifest(settings, {**FLAT, "prompts": ASKS[:1]})  # an edit to the manifest shows at once
    assert client.get(started["url"]).json()["prompts"] == ASKS[:1]
    _manifest(settings, FLAT)  # the sample lost its prompts: none, not an error
    assert "prompts" not in client.get(started["url"]).json()


def test_a_project_not_made_from_a_curated_sample_has_no_prompts(
    client: TestClient, settings: Settings, plan_pdf: bytes
) -> None:
    _manifest(settings, {**FLAT, "prompts": ASKS})
    synthetic = client.post("/api/projects/sample").json()
    assert "prompts" not in client.get(synthetic["url"]).json()
    uploaded = client.post("/api/projects", params={"name": "plan.pdf"}, content=plan_pdf).json()
    assert "prompts" not in client.get(uploaded["url"]).json()

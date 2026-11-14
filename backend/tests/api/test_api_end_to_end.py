"""The golden path on the real ingest, as the app runs it (lifespan included): upload a synthetic
vector PDF, ask a count, get the evidence, sign it off. No keys and no models.

The demo path: the sample archive (scripts/make_sample_archive.py) ingested in the background as
the app runs it, then a count asked, its marks on the served page, its takeoff row, an edit and
the reset. No network, no data/."""

import io
import time
from typing import Any

from fastapi.testclient import TestClient
from PIL import Image

from app.adapters.credits import SAMPLE
from app.composition import build_ingest
from app.main import create_app
from app.settings import Settings
from scripts.make_sample_archive import build_archive


def test_upload_a_plan_ask_a_count_and_get_its_evidence(
    settings: Settings, plan_pdf: bytes
) -> None:
    ingest = build_ingest(settings, settings.projects_dir, background=False)
    with TestClient(create_app(settings, ingest)) as client:
        started = client.post("/api/projects", params={"name": "plan.pdf"}, content=plan_pdf)
        assert started.status_code == 202
        status = client.get(started.json()["url"]).json()
        assert status["state"] == "done"
        (drawing,) = status["drawings"]
        assert (drawing["state"], drawing["route"]) == ("ready", "vector")
        drawing_id = drawing["drawing_id"]

        answer = client.post(
            "/api/ask", json={"drawing_id": drawing_id, "question": "How many doors are there?"}
        ).json()
        assert (answer["answer"], answer["method"], answer["refusal"]) == (2, "takeoff", None)
        assert [mark["label"] for mark in answer["marks"]] == ["door", "door"]
        assert [item["page"] for item in answer["line"]["evidence"]] == [1, 1]

        trace = client.get(f"/api/projects/{status['id']}/files/f1/trace").json()
        assert [stage["failure"] for stage in trace["stages"]] == [None] * len(trace["stages"])
        page = client.get(answer["pages"][0]["url"])
        assert page.content.startswith(b"\x89PNG")

        signed = client.post(
            f"/api/drawings/{drawing_id}/signoff", json={"quantity": "door", "by": "Ana"}
        ).json()
        door = next(row for row in signed["quantities"] if row["key"] == "door")
        assert door["status"] == "signed"


def finished(client: TestClient, url: str, seconds: float = 120) -> dict[str, Any]:
    """The project's status once ingest is done or failed; the deadline only bounds a hang."""
    deadline = time.monotonic() + seconds
    while (status := client.get(url).json())["state"] in ("queued", "running"):
        assert time.monotonic() < deadline, status
        time.sleep(0.05)
    return status


def row(takeoff: dict[str, Any], key: str) -> dict[str, Any]:
    return next(quantity for quantity in takeoff["quantities"] if quantity["key"] == key)


def test_demo_path_sample_archive_to_an_answer_with_evidence_then_review_and_reset(
    settings: Settings,
) -> None:
    settings.sample_archive.write_bytes(build_archive())
    ingest = build_ingest(settings, settings.projects_dir)  # in the background, as the app runs
    with TestClient(create_app(settings, ingest)) as client:
        started = client.post("/api/projects/sample")
        assert started.status_code == 202, started.text
        status = finished(client, started.json()["url"])
        assert status["state"] == "done"
        plan = next(item for item in status["drawings"] if item["file"] == "plans/flat-a.pdf")
        assert (plan["state"], plan["route"]) == ("ready", "vector")
        drawing_id = plan["drawing_id"]

        drawing = client.get(f"/api/drawings/{drawing_id}").json()
        assert drawing["credit"] == SAMPLE  # drawn by code: no partner data, and it says so
        assert any("door" in item["question"].lower() for item in drawing["suggestions"])

        answer = client.post(
            "/api/ask", json={"drawing_id": drawing_id, "question": "How many doors are there?"}
        ).json()
        assert (answer["answer"], answer["unit"], answer["refusal"]) == (2, "count", None)
        assert [(mark["label"], mark["state"]) for mark in answer["marks"]] == [
            ("door", "counted"),
            ("door", "counted"),
        ]
        served = {page["page"]: page for page in answer["pages"]}
        for mark in answer["marks"]:
            x0, y0, x1, y1 = mark["box"]
            assert mark["page"] in served and 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1
        png = client.get(served[answer["marks"][0]["page"]]["url"], params={"width": 400})
        assert png.status_code == 200
        assert Image.open(io.BytesIO(png.content)).width == 400

        door = row(client.get(f"/api/drawings/{drawing_id}/takeoff").json(), "door")
        assert door == answer["quantity"]
        assert (door["value"], door["original_value"]) == (2, 2)

        review = f"/api/drawings/{drawing_id}/review"
        rejected = client.post(
            review, json={"quantity": "door", "action": "reject", "mark": "m2"}
        ).json()
        assert row(rejected, "door")["value"] == 1
        reset = client.post(review, json={"action": "reset"}).json()
        door = row(reset, "door")
        assert door["value"] == 2
        assert [mark["state"] for mark in door["marks"]] == ["counted", "counted"]

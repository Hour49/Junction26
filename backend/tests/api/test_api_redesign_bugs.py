"""Four bugs from the frontend's pre-QA sweep (board #14, 2026-11-14)."""

import json
from typing import Any

import pytest
from conftest import upload
from fastapi.testclient import TestClient
from test_review_core import BOX_A, disputed, quantity

from app.api import takeoff

KUCHE = "area:room|name=küche"
NUMBER = "area:room|name=1.01"


def sample(client: TestClient) -> tuple[str, dict[str, Any]]:
    url = client.post("/api/projects/sample").json()["url"]
    return url, client.get(url).json()


def flat_b(project: dict[str, Any]) -> str:
    return next(f["drawing_id"] for f in project["files"] if f["path"] == "plans/flat-b.pdf")


def test_a_room_keyed_under_its_number_and_its_name_is_one_conflict(client: TestClient) -> None:
    url, project = sample(client)
    conflicts = client.get(f"{url}/review").json()["conflicts"]
    seen = [(c["drawing_id"], json.dumps(c["conflict"], sort_keys=True)) for c in conflicts]
    assert len(seen) == len(set(seen)), [c["quantity"] for c in conflicts]  # one per disagreement
    assert [c["quantity"] for c in conflicts if c["drawing_id"] == flat_b(project)] == [NUMBER]


def test_a_decision_on_one_name_of_the_room_is_the_decision_for_all(client: TestClient) -> None:
    _, project = sample(client)
    drawing = f"/api/drawings/{flat_b(project)}"
    at = {"project": project["id"], "zeros": True}
    settle = {"quantity": KUCHE, "action": "settle", "value": 30}
    rows = client.post(f"{drawing}/review", params=at, json=settle).json()["quantities"]
    by_key = {row["key"]: row for row in rows}
    assert by_key[KUCHE]["settled"] == by_key[NUMBER]["settled"] is not None
    assert by_key[NUMBER]["status"] == "edited"


def test_an_area_answer_names_the_room_by_its_printed_name(client: TestClient) -> None:
    _, project = sample(client)
    body = {
        "drawing_id": flat_b(project),
        "question": "What is the area of room 1.01?",
        "project_id": project["id"],
    }
    answer = client.post("/api/ask", json=body).json()
    assert answer["quantity"]["key"] == NUMBER
    assert answer["quantity"]["label"] == "area of room (name Küche · 1.01)"
    rows = client.get(f"/api/drawings/{flat_b(project)}/takeoff", params={"zeros": True}).json()
    labels = {row["key"]: row["label"] for row in rows["quantities"]}
    assert labels[KUCHE] == "area of room (name Küche)"  # asked by its own printed name
    assert labels[NUMBER] != labels[KUCHE]  # the room's rows still read differently


def test_conflicts_open_counts_only_what_a_person_still_has_to_settle(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, plan_pdf: bytes
) -> None:
    found = {
        "window": quantity(
            "window", 2, "count", BOX_A, conflict=disputed(False)
        ),  # no rule decides
        "door": quantity("door", 2, "count", BOX_A, conflict=disputed(True)),  # a rule decides
    }
    monkeypatch.setattr(takeoff, "known_quantities", lambda drawing: found)
    project = client.get(f"/api/projects/{upload(client, plan_pdf)}").json()

    def open_count() -> int:
        (summary,) = client.get("/api/projects").json()["projects"]
        return summary["conflicts_open"]

    assert len(client.get(f"/api/projects/{project['id']}/review").json()["conflicts"]) == 2
    assert open_count() == 1
    drawing = f"/api/drawings/{project['drawings'][0]['drawing_id']}"
    settle = {"quantity": "window", "action": "settle", "value": 3}
    client.post(f"{drawing}/review", params={"project": project["id"]}, json=settle)
    assert open_count() == 0

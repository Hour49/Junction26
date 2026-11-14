"""R4-c-2 (QA R4, 2026-11-14): GET /api/projects recomputed the whole review of every finished
project on every call (15-40 s with 18 projects), so the header's project picker sat on
"Loading projects…". A project's review counts are now kept until what they are made of changes:
its status, its review edits, or another upload writing one of its drawings again (a drawing
is shared by content)."""

from collections.abc import Callable
from typing import Any

import pytest
from conftest import plan_png, upload
from fastapi.testclient import TestClient
from test_review_core import BOX_A, disputed, quantity

from app.api import projects, takeoff


@pytest.fixture
def reviewed(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """The project ids `review_of` was computed for, in order."""
    calls: list[str] = []
    review_of: Callable[..., Any] = projects.review_of

    def counted(status: Any, *args: Any) -> Any:
        calls.append(status.id)
        return review_of(status, *args)

    monkeypatch.setattr(projects, "review_of", counted)
    return calls


def listed(client: TestClient) -> list[dict[str, Any]]:
    response = client.get("/api/projects")
    assert response.status_code == 200, response.text
    return response.json()["projects"]


def test_listing_twice_computes_each_review_once(
    client: TestClient, plan_pdf: bytes, reviewed: list[str]
) -> None:
    project_id = upload(client, plan_pdf)
    first = listed(client)
    assert listed(client) == first
    assert reviewed == [project_id]


def test_a_review_edit_recomputes_that_project(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, plan_pdf: bytes, reviewed: list[str]
) -> None:
    found = {"window": quantity("window", 2, "count", BOX_A, conflict=disputed(False))}
    monkeypatch.setattr(takeoff, "known_quantities", lambda drawing: found)
    project = client.get(f"/api/projects/{upload(client, plan_pdf)}").json()
    assert [summary["conflicts_open"] for summary in listed(client)] == [1]
    drawing = f"/api/drawings/{project['drawings'][0]['drawing_id']}"
    at = {"project": project["id"]}
    settle = {"quantity": "window", "action": "settle", "value": 3}
    assert client.post(f"{drawing}/review", params=at, json=settle).status_code == 200
    assert [summary["conflicts_open"] for summary in listed(client)] == [0]
    sign = {"quantity": "window", "by": "qa"}
    assert client.post(f"{drawing}/signoff", params=at, json=sign).status_code == 200
    listed(client)
    listed(client)  # nothing changed since the sign-off
    assert reviewed == [project["id"]] * 3


def test_another_upload_recomputes_only_the_projects_whose_drawings_it_wrote(
    client: TestClient, plan_pdf: bytes, reviewed: list[str]
) -> None:
    first = client.post("/api/projects/sample").json()["id"]
    listed(client)
    other = upload(client, plan_png(), name="other.png")  # other drawings: first is kept
    listed(client)
    assert reviewed == [first, other]
    again = client.post("/api/projects/sample", params={"fresh": True}).json()["id"]
    listed(client)  # the same drawings, written again by `again`
    assert sorted(reviewed[2:]) == sorted([again, first])

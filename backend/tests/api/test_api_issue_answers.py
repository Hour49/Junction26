"""Tudor's asks on board #14 (1, 3, 4): a person's answer to an issue, kept with the project;
each issue's answer chips and legend label; the open counts on the single-project GET."""

from typing import Any

import pytest
from conftest import upload
from fastapi.testclient import TestClient
from test_api_issues import listed, sample
from test_review_core import BOX_A, disputed, quantity

from app.api import takeoff
from app.composition import build_ingest
from app.main import create_app
from app.settings import Settings


def window_conflict(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every drawing's takeoff: a window count two methods disagree on, no rule decides."""
    found = {"window": quantity("window", 2, "count", BOX_A, conflict=disputed(False))}
    monkeypatch.setattr(takeoff, "known_quantities", lambda drawing: found)


def answer(client: TestClient, project_id: str, issue_id: str, body: dict[str, Any]) -> Any:
    return client.post(f"/api/projects/{project_id}/issues/{issue_id}/answer", json=body)


def test_an_answer_is_kept_with_the_issue_across_a_restart_and_can_be_taken_back(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch, plan_pdf: bytes
) -> None:
    window_conflict(monkeypatch)
    project_id = upload(client, plan_pdf)
    (issue,) = listed(client, project_id)
    assert issue["answer"] is None
    reply = answer(client, project_id, issue["id"], {"text": "3 is right", "by": "Ana"})
    assert reply.status_code == 200, reply.text
    said = reply.json()["answer"]
    assert (said["text"], said["by"]) == ("3 is right", "Ana") and said["at"].endswith("Z")
    assert reply.json() == {**issue, "answer": said}  # nothing else changes, state neither
    restarted = TestClient(create_app(settings, build_ingest(settings, settings.projects_dir)))
    assert listed(restarted, project_id) == [{**issue, "answer": said}]
    again = answer(client, project_id, issue["id"], {"text": "Check it on site", "by": "Bo"})
    assert again.json()["answer"]["text"] == "Check it on site"  # replaces the first
    undone = answer(client, project_id, issue["id"], {"undo": True})
    assert undone.status_code == 200 and undone.json()["answer"] is None
    assert listed(client, project_id) == [issue]
    assert answer(client, project_id, issue["id"], {"undo": True}).status_code == 200  # no-op


def test_an_answer_to_an_unknown_issue_or_project_is_404_and_a_bad_body_422(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, plan_pdf: bytes
) -> None:
    window_conflict(monkeypatch)
    project_id = upload(client, plan_pdf)
    (issue,) = listed(client, project_id)
    said = {"text": "fine", "by": "Ana"}
    assert answer(client, project_id, "conflict-000000000000", said).status_code == 404
    assert answer(client, "0123456789ab", issue["id"], said).status_code == 404
    for body in (
        {"text": "fine"},
        {"by": "Ana"},
        {"text": "", "by": "Ana"},
        {"undo": True, **said},
    ):
        assert answer(client, project_id, issue["id"], body).status_code == 422, body
    assert listed(client, project_id) == [issue]


def test_a_code_check_issue_is_answered_with_its_pack(client: TestClient) -> None:
    project = sample(client)
    url = f"/api/projects/{project['id']}/issues"
    packs = client.get("/api/info").json()["rule_packs"]
    pack = packs[0]["id"]
    checked = client.get(url, params={"pack": pack}).json()["issues"]
    failed = next(issue for issue in checked if issue["kind"] == "code_check_failed")
    said = {"text": "Accepted as drawn", "by": "Ana"}
    assert answer(client, project["id"], failed["id"], said).status_code == 404  # no pack
    reply = client.post(f"{url}/{failed['id']}/answer", params={"pack": pack}, json=said)
    assert reply.status_code == 200 and reply.json()["answer"]["text"] == "Accepted as drawn"


def test_each_issue_has_a_label_and_answer_chips_a_conflict_its_two_values(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, plan_pdf: bytes
) -> None:
    window_conflict(monkeypatch)
    (issue,) = listed(client, upload(client, plan_pdf))
    assert issue["label"] == "Window count"  # the takeoff row's label
    assert issue["suggestions"] == ["2 is right", "3 is right", "Check it on site"]


def test_the_sample_issues_get_chips_and_a_label_by_kind(client: TestClient) -> None:
    found = {issue["kind"]: issue for issue in listed(client, sample(client)["id"])}
    room = found["conflict"]  # an area: its values with the unit
    assert room["label"] == "Area of room (name Küche · 1.01)"
    assert room["suggestions"][-1] == "Check it on site" and len(room["suggestions"]) == 3
    assert all(chip.endswith(" m² is right") for chip in room["suggestions"][:2])
    assert (found["set_aside"]["label"], found["set_aside"]["suggestions"]) == (
        "Set aside",
        ["Not needed", "I'll send a readable copy"],
    )
    assert found["reading_flag"]["label"] == "How it was read"


def test_the_project_get_has_the_lists_open_counts_and_an_answer_lowers_to_answer(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    window_conflict(monkeypatch)
    project = sample(client)
    open_ones = [issue for issue in listed(client, project["id"]) if issue["state"] == "open"]
    to_answer = [issue for issue in open_ones if issue["severity"] != "note"]
    counts = ("conflicts_open", "issues_open", "issues_to_answer")
    (summary,) = client.get("/api/projects").json()["projects"]
    assert [project[key] for key in counts] == [summary[key] for key in counts]
    assert [project[key] for key in counts] == [len(to_answer), len(open_ones), len(to_answer)]
    assert len(to_answer) > 0
    said = {"text": "Check it on site", "by": "Ana"}
    assert answer(client, project["id"], to_answer[0]["id"], said).status_code == 200
    after = client.get(f"/api/projects/{project['id']}").json()
    (listed_after,) = client.get("/api/projects").json()["projects"]
    expected = [len(to_answer), len(open_ones), len(to_answer) - 1]  # still open: an answer
    assert [after[key] for key in counts] == [listed_after[key] for key in counts] == expected


def test_a_running_project_has_no_counts(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = sample(client)
    ingest = client.app.state.ingest  # type: ignore[attr-defined]
    running = ingest.status(project["id"]).model_copy(update={"state": "running"})
    monkeypatch.setattr(ingest, "status", lambda project_id: running)
    found = client.get(f"/api/projects/{project['id']}").json()
    assert (found["conflicts_open"], found["issues_open"], found["issues_to_answer"]) == (
        None,
        None,
        None,
    )

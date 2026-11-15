"""The chat asks about an open issue first (decision 0018), through POST /api/projects/{id}/chat
with CHAT_MODEL=rules. The sample's kitchen conflict is decided by a rule, so the issue list is
made to say a person must decide it; the settle and the answers are the real ones."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from test_api_chat import ask, sample

from app.api import chat as chat_route
from app.api.issues import listed_issues

KITCHEN = "How big is the kitchen?"


@pytest.fixture
def open_conflict(monkeypatch: pytest.MonkeyPatch) -> None:
    def listed(*args: Any, **more: Any) -> Any:
        found = listed_issues(*args, **more)
        return [
            issue.model_copy(update={"severity": "needs_person", "state": "open"})
            if issue.kind == "conflict"
            and issue.state == "settled"
            and issue.answer is None
            and issue.why.startswith("Area of room")
            else issue
            for issue in found
        ]

    monkeypatch.setattr(chat_route, "listed_issues", listed)


def reply(turn: dict[str, Any], label: str, **more: Any) -> dict[str, Any]:
    option = next(o for o in turn["options"] if o["label"].startswith(label))
    return {"issue_id": turn["issue"]["id"], "text": option["message"], "by": "Ana",
            "value": option.get("value"), "skip": option.get("skip", False), **more}  # fmt: skip


def test_a_question_on_an_open_conflict_asks_then_a_pick_settles_and_answers(
    client: TestClient, open_conflict: None
) -> None:
    project = sample(client)
    asked = ask(client, project, KITCHEN)
    assert asked["kind"] == "ask_issue" and asked["answers"] == []
    assert asked["issue"]["label"].startswith("Area of room")
    assert asked["issue"]["kind"] == "conflict"
    labels = [o["label"] for o in asked["options"]]
    assert labels[-1] == "Skip for now" and labels[0].startswith("Use ")
    body = reply(asked, "Use 22.4")
    turn = ask(client, project, body["text"], chat_id=asked["chat_id"], issue_answer=body)
    assert turn["kind"] != "ask_issue" and turn["answers"]
    issue = next(i for i in client.get(f"/api/projects/{project}/issues").json()["issues"]
                 if i["id"] == asked["issue"]["id"])  # fmt: skip
    assert issue["answer"]["by"] == "Ana"
    [part] = [p for a in turn["answers"] for p in a["parts"]
              if p["drawing_id"] == asked["issue"]["drawing_id"]]  # fmt: skip
    assert part["answer"]["quantity"]["settled"]["value"] == pytest.approx(22.401, abs=0.01)


def test_skip_answers_with_the_open_issue_and_is_never_asked_again(
    client: TestClient, open_conflict: None
) -> None:
    project = sample(client)
    asked = ask(client, project, KITCHEN)
    body = reply(asked, "Skip for now")
    turn = ask(client, project, "Skip for now", chat_id=asked["chat_id"], issue_answer=body)
    assert turn["kind"] != "ask_issue"
    assert turn["text"].endswith("Do you have other questions?") and "open issue" in turn["text"]
    issues = client.get(f"/api/projects/{project}/issues").json()["issues"]
    assert all(i["answer"] is None for i in issues)  # a skip is no answer
    again = ask(client, project, KITCHEN)  # a new chat
    assert again["kind"] != "ask_issue"


def test_an_answer_to_an_issue_the_chat_is_not_asking_about_is_422(
    client: TestClient, open_conflict: None
) -> None:
    project = sample(client)
    turn = ask(client, project, "How many doors are there?")
    body = {"issue_id": "conflict-x", "text": "Skip for now", "by": "Ana", "skip": True}
    sent = {"message": "x", "chat_id": turn["chat_id"], "issue_answer": body}
    response = client.post(f"/api/projects/{project}/chat", json=sent)
    assert response.status_code == 422


def test_r4_a_value_the_ask_did_not_offer_is_422_and_settles_nothing(
    client: TestClient, open_conflict: None
) -> None:
    project = sample(client)
    asked = ask(client, project, KITCHEN)
    body = {**reply(asked, "Use 22.4"), "value": 999.0}
    sent = {"message": body["text"], "chat_id": asked["chat_id"], "issue_answer": body}
    response = client.post(f"/api/projects/{project}/chat", json=sent)
    assert response.status_code == 422, response.text
    issues = client.get(f"/api/projects/{project}/issues").json()["issues"]
    assert all(i["answer"] is None for i in issues)
    # the ask still stands: an offered value is taken
    good = reply(asked, "Use 22.4")
    turn = ask(client, project, good["text"], chat_id=asked["chat_id"], issue_answer=good)
    assert turn["kind"] != "ask_issue"

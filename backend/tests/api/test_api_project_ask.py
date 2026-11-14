"""POST /api/projects/{id}/ask: a question on every drawing of a project (board #14, Tudor's
project chat). Each part is what POST /api/ask gives; the total adds up only what adds up."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import project_ask
from app.api.ask import AnswerView, answer_view

DOORS = "How many doors are there?"


def sample(client: TestClient) -> dict[str, Any]:
    return client.get(client.post("/api/projects/sample").json()["url"]).json()


def ask(client: TestClient, project_id: str, question: str) -> dict[str, Any]:
    reply = client.post(f"/api/projects/{project_id}/ask", json={"question": question})
    assert reply.status_code == 200, reply.text
    return reply.json()


def timeless(answer: dict[str, Any]) -> dict[str, Any]:
    """The answer without its latencies, which differ on every call."""
    return {**answer, "latency_s": 0, "line": {**answer["line"], "latency_s": 0}}


def changed(monkeypatch: pytest.MonkeyPatch, change: Any) -> None:
    """Each part as POST /api/ask gives it, then `change(view)`: a stand-in for a reading the
    synthetic sample doesn't have (a sure answer, another unit, a conflict)."""

    def changed_view(*args: Any) -> AnswerView:
        return change(answer_view(*args))

    monkeypatch.setattr(project_ask, "answer_view", changed_view)


def test_an_unknown_project_is_404(client: TestClient) -> None:
    for project_id in ("0123456789ab", "not-an-id"):
        reply = client.post(f"/api/projects/{project_id}/ask", json={"question": DOORS})
        assert reply.status_code == 404 and project_id in reply.json()["detail"]  # not "no route"


def test_a_project_not_done_is_409(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    project = sample(client)
    ingest = client.app.state.ingest  # type: ignore[attr-defined]
    running = ingest.status(project["id"]).model_copy(update={"state": "running"})
    monkeypatch.setattr(ingest, "status", lambda project_id: running)
    reply = client.post(f"/api/projects/{project['id']}/ask", json={"question": DOORS})
    assert reply.status_code == 409 and reply.json()["code"] == "not-allowed"


def test_a_count_is_summed_over_the_drawings_that_answer_refused_ones_last(
    client: TestClient,
) -> None:
    project = sample(client)
    found = ask(client, project["id"], DOORS)
    names = {entry["drawing_id"]: entry["file"] for entry in project["drawings"]}
    assert {part["drawing_id"] for part in found["parts"]} == set(names)
    for part in found["parts"]:  # each part is exactly what POST /api/ask gives
        assert part["name"] == names[part["drawing_id"]]
        body = {"drawing_id": part["drawing_id"], "question": DOORS, "project_id": project["id"]}
        assert timeless(part["answer"]) == timeless(client.post("/api/ask", json=body).json())
    refused = [part["answer"]["refusal"] is not None for part in found["parts"]]
    assert refused == sorted(refused) and True in refused and False in refused
    answered = [part["answer"]["answer"] for part in found["parts"] if part["answer"]["answer"]]
    assert len(answered) >= 2
    assert (found["total"], found["total_unit"]) == (sum(answered), "count")
    assert found["total_sure"] is False  # the sample's answers have no sure verdict
    assert found["total_note"] == (
        f"{sum(answered)} doors over {len(answered)} drawings; "
        f"{refused.count(True)} drawings have no reader for it."
    )


def test_a_question_about_one_room_has_no_total(client: TestClient) -> None:
    project = sample(client)
    found = ask(client, project["id"], "What is the area of the kitchen?")
    answered = [part for part in found["parts"] if part["answer"]["refusal"] is None]
    assert len(answered) == 2  # the kitchen of flat-a and of flat-b: two rooms
    assert (found["total"], found["total_unit"], found["total_sure"]) == (None, None, False)
    assert found["total_note"].startswith(
        "2 drawings answered; each answer is about its own room or table, so they are not added up"
    )


def test_parts_in_different_units_have_no_total(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = sample(client)
    seen: list[str] = []

    def in_feet(view: AnswerView) -> AnswerView:  # the second drawing that answers is in ft²
        if view.refusal is None:
            seen.append(view.drawing_id)
        return view.model_copy(update={"unit": "ft2"}) if len(seen) == 2 else view

    changed(monkeypatch, in_feet)
    found = ask(client, project["id"], "What is the total indoor area?")
    assert found["total"] is None
    assert "they answered in different units, so they are not added up" in found["total_note"]


def test_a_total_is_sure_only_when_every_summed_part_is(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = sample(client)

    def sure(view: AnswerView) -> AnswerView:
        return view.model_copy(update={"line": view.line.model_copy(update={"sure": True})})

    changed(monkeypatch, sure)
    assert ask(client, project["id"], DOORS)["total_sure"] is True
    first = project["drawings"][0]["drawing_id"]  # flat-a, which answers
    changed(monkeypatch, lambda view: view if view.drawing_id == first else sure(view))
    assert ask(client, project["id"], DOORS)["total_sure"] is False


def test_a_summed_part_that_needs_a_double_check_says_so(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = sample(client)
    first = project["drawings"][0]["drawing_id"]

    def disputed(view: AnswerView) -> AnswerView:
        if view.drawing_id != first or view.quantity is None:
            return view
        row = view.quantity.model_copy(update={"status": "conflict", "needs_person": True})
        return view.model_copy(update={"quantity": row})

    changed(monkeypatch, disputed)
    found = ask(client, project["id"], DOORS)
    assert found["total"] is not None
    assert "; 1 of them needs a double-check;" in found["total_note"]


def test_a_project_question_is_logged_once_with_no_drawing(client: TestClient) -> None:
    project = sample(client)
    found = ask(client, project["id"], DOORS)
    ask(client, project["id"], "What colour is the roof?")
    listed = client.get(f"/api/projects/{project['id']}/questions").json()["questions"]
    assert len(listed) == 2  # one line per project question, not one per drawing
    roof, doors = listed
    assert (doors["question"], doors["answer"], doors["unit"], doors["drawing_id"]) == (
        DOORS, found["total"], "count", None,
    )  # fmt: skip
    assert (roof["answer"], roof["unit"], roof["drawing_id"], roof["refused"]) == (
        None, None, None, True,
    )  # fmt: skip

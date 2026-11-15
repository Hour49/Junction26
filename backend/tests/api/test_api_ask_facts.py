"""POST /api/ask on a building model with IFC_FACTS: a question the takeoff has no row for is
answered from the model's fact sheet, read once per file content (sha256)."""

import threading
import time
from typing import Any

import ifcopenshell
import pytest
from fastapi.testclient import TestClient

from app.adapters.ifc_model import facts_source, facts_store
from app.api.ask import STILL_READING
from app.composition import build_ingest
from app.main import create_app
from app.settings import Settings

WALLS = "What is the total wall length?"  # the takeoff has no wall length


def model_ask(
    settings: Settings, question: str, ifc_facts: bool
) -> tuple[TestClient, dict[str, Any]]:
    settings = settings.model_copy(update={"ifc_facts": ifc_facts})
    client = TestClient(
        create_app(settings, build_ingest(settings, settings.projects_dir, background=False))
    )
    project = client.get(client.post("/api/projects/sample").json()["url"]).json()
    model = next(d for d in project["drawings"] if d["file"] == "model/house.ifc")
    body = {"drawing_id": model["drawing_id"], "question": question, "project_id": project["id"]}
    reply = client.post("/api/ask", json=body)
    assert reply.status_code == 200, reply.text
    return client, reply.json()


def test_off_a_question_the_takeoff_cannot_answer_is_refused(settings: Settings) -> None:
    _, found = model_ask(settings, WALLS, ifc_facts=False)
    assert found["refusal"] is not None and found["method"] != "facts"


def test_the_build_starts_when_the_project_is_read_so_the_first_ask_answers(
    settings: Settings,
) -> None:
    """QA research-lead MUST-FIX: the first fact question on a new model was refused, as the
    sheet was built only on that ask. Reading the project after ingest starts the build."""
    client, project = sample(settings)
    stored(client)  # no question asked yet
    found = client.post("/api/ask", json=on_model(project, WALLS)).json()
    assert found["refusal"] is None and found["method"] == "facts"
    assert "Total walls: 4" in found["answer"] and "length 8.00 m" in found["answer"]
    assert "Low" in (found["explanation"] or "")


def test_a_question_while_the_model_is_read_says_so(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    gate, store = threading.Event(), facts_store.store_facts

    def held(*args: Any, **kwargs: Any) -> Any:
        gate.wait(30)
        return store(*args, **kwargs)

    monkeypatch.setattr(facts_store, "store_facts", held)
    client, project = sample(settings)
    first = client.post("/api/ask", json=on_model(project, WALLS)).json()
    assert first["refusal"]["text"] == STILL_READING
    asked = client.post(f"/api/projects/{project['id']}/ask", json={"question": WALLS}).json()
    assert STILL_READING in [p["answer"]["refusal"]["text"] for p in asked["parts"]]
    gate.set()
    stored(client)
    answered = client.post("/api/ask", json=on_model(project, WALLS)).json()
    assert answered["method"] == "facts"


def sample(settings: Settings) -> tuple[TestClient, dict[str, Any]]:
    """The sample project ingested and read once, as the screen reads it when ingest is done."""
    settings = settings.model_copy(update={"ifc_facts": True})
    client = TestClient(
        create_app(settings, build_ingest(settings, settings.projects_dir, background=False))
    )
    return client, client.get(client.post("/api/projects/sample").json()["url"]).json()


def on_model(project: dict[str, Any], question: str) -> dict[str, Any]:
    model = next(d for d in project["drawings"] if d["file"] == "model/house.ifc")
    return {"drawing_id": model["drawing_id"], "question": question, "project_id": project["id"]}


def test_on_a_takeoff_answer_is_unchanged(settings: Settings) -> None:
    _, off = model_ask(settings, "How many doors are there?", ifc_facts=False)
    _, on = model_ask(settings, "How many doors are there?", ifc_facts=True)
    timeless = lambda a: {**a, "latency_s": 0, "line": {**a["line"], "latency_s": 0}}  # noqa: E731
    assert timeless(on) == timeless(off)


def stored(client: TestClient) -> None:
    """Waits for the background build the first ask started (a capped child process)."""
    folder = client.app.state.settings.projects_dir.parent / "cache" / "facts"  # type: ignore[attr-defined]
    for _ in range(600):
        if list(folder.glob("*.json")):
            return
        time.sleep(0.1)
    raise AssertionError("no fact sheet was stored")


def test_the_api_process_never_opens_a_model_for_a_chat_question(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    def never(*_: object) -> None:
        raise AssertionError("an IFC model was parsed in the API process")

    client, first = model_ask(settings, WALLS, ifc_facts=True)
    monkeypatch.setattr(ifcopenshell, "open", never)  # after ingest, which reads the model itself
    monkeypatch.setattr(facts_source, "read_facts", never)
    body = {"drawing_id": first["drawing_id"], "question": WALLS}
    client.post("/api/ask", json=body)  # the build runs apart
    stored(client)
    answered = client.post("/api/ask", json=body).json()
    assert answered["method"] == "facts" and "Total walls: 4" in answered["answer"]

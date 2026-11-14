"""POST /api/projects/{id}/ask: a question on every drawing of a project (board #14, Tudor's
project chat). Each part is what POST /api/ask gives; a total only for one answering drawing, or
for drawings known to show different storeys of one building model."""

from typing import Any

import pytest
from conftest import upload
from fastapi.testclient import TestClient

from app.api import project_ask
from app.api.ask import AnswerView, answer_view
from app.core.drawing.model import Drawing
from app.core.review.model import Row, Scope

DOORS = "How many doors are there?"
SAME_FLAT = "they may show the same rooms, so the numbers are not added up"


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


def disjoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """The sample's drawings as if they were sheets of different storeys of one model (the
    sample has no such sheets; test_disjoint_* check that rule on drawings that are)."""
    monkeypatch.setattr(project_ask, "_disjoint", lambda drawings, rows: True)


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


def test_each_part_is_the_drawings_answer_refused_ones_last(client: TestClient) -> None:
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


def test_drawings_that_may_show_the_same_flat_are_not_added_up(client: TestClient) -> None:
    # the sample's flat-a.pdf and model/house.ifc draw the same flat: a sum says 6 doors, not 4
    project = sample(client)
    found = ask(client, project["id"], DOORS)
    answered = [part for part in found["parts"] if part["answer"]["refusal"] is None]
    assert {part["name"] for part in answered} >= {"plans/flat-a.pdf", "model/house.ifc"}
    assert (found["total"], found["total_unit"], found["total_sure"]) == (None, None, False)
    assert found["total_note"] == (
        f"{len(answered)} drawings answered; {SAME_FLAT}; 2 drawings have no reader for it."
    )


def test_an_ifc_model_answers_an_area_and_is_not_added_to_the_sheets_of_its_flat(
    client: TestClient,
) -> None:
    """R4b-4: the model file used to be refused with "the sheet has no scale"."""
    project = sample(client)
    found = ask(client, project["id"], "What is the net floor area of all indoor rooms in m²?")
    parts = {part["name"]: part["answer"] for part in found["parts"]}
    model = parts["model/house.ifc"]
    assert model["refusal"] is None and (model["answer"], model["unit"]) == (48.0, "m2")
    assert (found["total"], found["total_unit"]) == (None, None)  # never the model + its sheets
    assert SAME_FLAT in found["total_note"]


def test_one_answering_drawing_is_the_total(client: TestClient, plan_pdf: bytes) -> None:
    found = ask(client, upload(client, plan_pdf), DOORS)
    (part,) = found["parts"]
    assert (found["total"], found["total_unit"]) == (part["answer"]["answer"], "count") == (
        2, "count",
    )  # fmt: skip
    assert found["total_note"] == "2 doors from 1 drawing."


def test_drawings_known_to_be_disjoint_are_summed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = sample(client)
    disjoint(monkeypatch)
    found = ask(client, project["id"], DOORS)
    values = [part["answer"]["answer"] for part in found["parts"] if not part["answer"]["refusal"]]
    assert len(values) >= 2
    assert (found["total"], found["total_unit"]) == (sum(values), "count")
    assert found["total_sure"] is False  # the sample's answers have no sure verdict
    assert found["total_note"] == (
        f"{sum(values)} doors over {len(values)} drawings; 2 drawings have no reader for it."
    )


def test_a_question_about_one_room_has_no_total(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = sample(client)
    disjoint(monkeypatch)  # even then: two kitchens are two rooms
    found = ask(client, project["id"], "What is the area of the kitchen?")
    answered = [part for part in found["parts"] if part["answer"]["refusal"] is None]
    assert len(answered) == 2  # the kitchen of flat-a and of flat-b
    assert (found["total"], found["total_unit"], found["total_sure"]) == (None, None, False)
    assert found["total_note"].startswith(
        "2 drawings answered, each about its own room, so there is no total;"
    )


def test_parts_in_different_units_have_no_total(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = sample(client)
    disjoint(monkeypatch)
    seen: list[str] = []

    def in_feet(view: AnswerView) -> AnswerView:  # the second drawing that answers is in ft²
        if view.refusal is None:
            seen.append(view.drawing_id)
        return view.model_copy(update={"unit": "ft2"}) if len(seen) == 2 else view

    changed(monkeypatch, in_feet)
    found = ask(client, project["id"], "What is the total indoor area?")
    assert found["total"] is None
    # the sample's IFC model answers an area too (R4b-4), so three drawings answered
    assert "3 drawings answered in different units, so there is no total" in found["total_note"]


def test_a_total_is_sure_only_when_every_summed_part_is(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = sample(client)
    disjoint(monkeypatch)

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
    disjoint(monkeypatch)
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


def test_a_project_question_is_logged_per_answering_drawing_under_one_id(
    client: TestClient,
) -> None:
    project = sample(client)
    url = f"/api/projects/{project['id']}/questions"
    found = ask(client, project["id"], DOORS)
    answered = [part for part in found["parts"] if part["answer"]["refusal"] is None]
    lines = client.get(url).json()["questions"][::-1]  # oldest first
    assert [
        (line["drawing_id"], line["answer"], line["unit"], line["refused"]) for line in lines
    ] == [(part["drawing_id"], part["answer"]["answer"], "count", False) for part in answered]
    assert len({line["project_ask"] for line in lines}) == 1 and lines[0]["project_ask"]
    # no drawing answers: one refused line per drawing, under a new id
    ask(client, project["id"], "What colour is the roof?")
    roof = client.get(url).json()["questions"][: len(project["drawings"])]
    assert {line["drawing_id"] for line in roof} == {d["drawing_id"] for d in project["drawings"]}
    assert all(line["refused"] and line["answer"] is None for line in roof)
    assert len({line["project_ask"] for line in roof} | {lines[0]["project_ask"]}) == 2
    # an ask on one drawing has no project_ask at all
    body = {"drawing_id": answered[0]["drawing_id"], "question": DOORS, "project_id": project["id"]}
    client.post("/api/ask", json=body)
    assert "project_ask" not in client.get(url).json()["questions"][0]


def sheet(storeys: tuple[str | None, ...], model: tuple[str, ...] = ("g1", "g2")) -> Drawing:
    """A sheet of a building model: one plan per storey, the model's objects by global id."""
    return Drawing.model_validate(
        {
            "file": "sheet.pdf",
            "pages": [{"page": 1, "width": 100, "height": 100, "unit": "pt"}],
            "scale": {"status": "no_scale"},
            "plans": [
                {"id": f"p{at}", "page": 1, "box": [0, 0, 1, 1], "storey": storey}
                for at, storey in enumerate(storeys)
            ],
            "model_objects": [
                {"id": f"o{at}", "class": "door", "global_id": gid} for at, gid in enumerate(model)
            ],
        }
    )


def row(model: bool = False) -> Row:
    return Row.model_construct(scope=Scope(model=model))


def test_disjoint_sheets_are_different_storeys_of_one_model() -> None:
    rows = [row(), row()]
    assert project_ask._disjoint([sheet(("Ground",)), sheet(("First",))], rows)
    # the same storey twice, a sheet of two storeys, no storey, another model, no model
    assert not project_ask._disjoint([sheet(("Ground",)), sheet(("Ground",))], rows)
    assert not project_ask._disjoint([sheet(("Ground", "First")), sheet(("Roof",))], rows)
    assert not project_ask._disjoint([sheet((None,)), sheet(("First",))], rows)
    assert not project_ask._disjoint([sheet(("Ground",)), sheet(("First",), ("g9",))], rows)
    assert not project_ask._disjoint([sheet(("Ground",), ()), sheet(("First",), ())], rows)
    # a question "in the model" asks the whole model on each sheet
    assert not project_ask._disjoint([sheet(("Ground",)), sheet(("First",))], [row(True), row()])


def test_a_model_file_is_never_disjoint_from_its_sheets() -> None:
    model = sheet(("Ground",)).model_copy(update={"pages": (), "plans": ()})
    assert not project_ask._disjoint([model, sheet(("First",))], [row(), row()])

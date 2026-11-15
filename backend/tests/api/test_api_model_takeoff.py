"""R4-B14 (Tudor's QA round 4): the takeoff of a building model asked on its own (an uploaded .ifc,
no page) listed every quantity twice, "door count (model)" next to "door count" with the same value
and marks, each signed off on its own. The model file is keyed both ways so a plain question
resolves on it (takeoff._add_model); the takeoff lists it once, on the plain row."""

from typing import Any

from fastapi.testclient import TestClient


def model_takeoff(client: TestClient) -> tuple[str, dict[str, Any]]:
    project = client.get(client.post("/api/projects/sample").json()["url"]).json()
    model = next(d["drawing_id"] for d in project["drawings"] if d["file"].endswith(".ifc"))
    found = client.get(f"/api/drawings/{model}/takeoff")
    assert found.status_code == 200, found.text
    return model, found.json()


def row(takeoff: dict[str, Any], key: str) -> dict[str, Any]:
    return next(found for found in takeoff["quantities"] if found["key"] == key)


def test_a_model_file_lists_each_quantity_once_on_its_plain_row(client: TestClient) -> None:
    _, takeoff = model_takeoff(client)
    keys = [found["key"] for found in takeoff["quantities"]]
    assert "door" in keys and "door|model" not in keys
    twins = [key for key in keys if key.endswith("|model") and key.removesuffix("|model") in keys]
    assert twins == []
    assert len(keys) == len(set(keys))


def test_a_sign_off_or_edit_of_the_model_key_lands_on_the_plain_row(client: TestClient) -> None:
    """An answer on the model file may cite "door|model" (a question about the whole model): its
    sign-off and edits are the one listed row's."""
    model, takeoff = model_takeoff(client)
    doors = row(takeoff, "door")["value"]
    url = f"/api/drawings/{model}/signoff"
    signed = client.post(url, json={"quantity": "door|model", "by": "Ana"})
    assert signed.status_code == 200, signed.text
    assert row(signed.json(), "door")["status"] == "signed"
    undone = client.post(url, json={"quantity": "door", "by": "Ana", "undo": True})
    assert row(undone.json(), "door")["status"] != "signed"

    edit = {"quantity": "door|model", "action": "settle", "value": doors + 1}
    settled = client.post(f"/api/drawings/{model}/review", json=edit)
    assert settled.status_code == 200, settled.text
    assert row(settled.json(), "door")["value"] == doors + 1

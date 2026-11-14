"""GET /api/projects/{id}/files/{file_id}/model.glb and FileStatus.model_3d (MODEL_3D): off, the
route is 404 and no payload changes; on, an IFC file's first GET starts its conversion (409),
then the GLB is served, gzipped when the client takes it."""

import gzip
import io
import json
import time
import zipfile
from pathlib import Path
from typing import Any

import pytest
from conftest import upload
from fastapi.testclient import TestClient
from test_api_chat import stream
from test_api_checks import RULES, checks_sheet
from test_api_issues_checks import serving
from test_ifc_glb import flat, house, node_names
from test_ifc_model import MODEL, SHEET, TWIN, demo

from app.composition import build_ingest
from app.main import create_app
from app.settings import Settings


@pytest.fixture
def on(settings: Settings) -> TestClient:
    turned = settings.model_copy(update={"model_3d": True})
    return TestClient(
        create_app(turned, build_ingest(turned, turned.projects_dir, background=False))
    )


def file_of(client: TestClient, project_id: str, path: str) -> dict[str, Any]:
    files = client.get(f"/api/projects/{project_id}").json()["files"]
    return next(file for file in files if file["path"] == path)


def fetched(client: TestClient, url: str, **headers: str) -> Any:
    """The route polled the way the view polls it, until it stops saying converting."""
    for _ in range(300):
        response = client.get(url, headers=headers)
        if response.status_code != 409:
            return response
        assert response.json()["code"] == "converting"
        time.sleep(0.1)
    raise AssertionError("still converting")


def test_off_the_route_is_404_and_files_have_no_model_3d(client: TestClient) -> None:
    data, _ = house()
    project_id = upload(client, data, "house.ifc")
    file = file_of(client, project_id, "house.ifc")
    assert file["kind"] == "ifc"
    assert "model_3d" not in file
    response = client.get(f"/api/projects/{project_id}/files/{file['id']}/model.glb")
    assert response.status_code == 404


def test_off_and_on_give_the_same_payload_for_a_project_without_ifc(
    client: TestClient, on: TestClient, plan_pdf: bytes
) -> None:
    project_id = upload(on, plan_pdf)
    shown = on.get(f"/api/projects/{project_id}").content
    assert client.get(f"/api/projects/{project_id}").content == shown
    assert b"model_3d" not in shown


def test_on_an_ifc_file_converts_on_first_get_then_is_served(on: TestClient) -> None:
    data, walls = house()
    project_id = upload(on, data, "house.ifc")
    file = file_of(on, project_id, "house.ifc")
    assert file["model_3d"] == {
        "state": "not_started",
        "code": None,
        "reason": "",
        "elements": None,
    }
    url = f"/api/projects/{project_id}/files/{file['id']}/model.glb"
    first = on.get(url)
    assert first.status_code == 409
    assert first.json()["code"] == "converting"
    zipped = fetched(on, url, **{"Accept-Encoding": "gzip"})
    assert zipped.status_code == 200
    assert zipped.headers["content-type"] == "model/gltf-binary"
    assert zipped.headers["content-encoding"] == "gzip"
    assert set(walls) <= set(node_names(zipped.content))  # httpx unzips it
    plain = on.get(url, headers={"Accept-Encoding": "identity"})
    assert "content-encoding" not in plain.headers
    assert plain.content == zipped.content
    assert file_of(on, project_id, "house.ifc")["model_3d"]["state"] == "ready"
    assert file_of(on, project_id, "house.ifc")["model_3d"]["elements"] == 3


def test_on_a_model_without_shapes_is_422_no_geometry(on: TestClient) -> None:
    project_id = upload(on, flat(), "flat.ifc")
    file = file_of(on, project_id, "flat.ifc")
    response = fetched(on, f"/api/projects/{project_id}/files/{file['id']}/model.glb")
    assert response.status_code == 422
    assert response.json()["code"] == "no_geometry"
    shown = file_of(on, project_id, "flat.ifc")["model_3d"]
    assert (shown["state"], shown["code"]) == ("unavailable", "no_geometry")


def test_on_a_file_that_is_no_ifc_is_404_and_has_no_model_3d(
    on: TestClient, plan_pdf: bytes
) -> None:
    project_id = upload(on, plan_pdf)
    file = file_of(on, project_id, "plan.pdf")
    assert "model_3d" not in file
    response = on.get(f"/api/projects/{project_id}/files/{file['id']}/model.glb")
    assert response.status_code == 404
    assert on.get(f"/api/projects/{project_id}/files/f99/model.glb").status_code == 404


def test_gzip_is_what_is_stored(on: TestClient, settings: Settings) -> None:
    """The stored file is the gzip the route sends as is: decompressed, a GLB."""
    data, _ = house()
    project_id = upload(on, data, "house.ifc")
    file = file_of(on, project_id, "house.ifc")
    fetched(on, f"/api/projects/{project_id}/files/{file['id']}/model.glb")
    (stored,) = (settings.projects_dir / "models-3d").glob("*.glb.gz")
    assert gzip.decompress(stored.read_bytes())[:4] == b"glTF"


def test_the_file_trace_has_model_3d_on_and_none_off(on: TestClient, client: TestClient) -> None:
    data, _ = house()
    project_id = upload(on, data, "house.ifc")
    file_id = file_of(on, project_id, "house.ifc")["id"]
    traced = on.get(f"/api/projects/{project_id}/files/{file_id}/trace").json()
    assert traced["file"]["model_3d"]["state"] == "not_started"
    fetched(on, f"/api/projects/{project_id}/files/{file_id}/model.glb")
    traced = on.get(f"/api/projects/{project_id}/files/{file_id}/trace").json()
    assert (traced["file"]["model_3d"]["state"], traced["file"]["model_3d"]["elements"]) == (
        "ready",
        3,
    )
    listed = on.get(f"/api/projects/{project_id}/trace").json()["files"]
    assert listed[0]["file"]["model_3d"]["state"] == "ready"
    off = client.get(f"/api/projects/{project_id}/files/{file_id}/trace").json()
    assert "model_3d" not in off["file"]


WALLS = {"question": "How many walls are there?"}


def parts_of(answer: dict[str, Any]) -> dict[str, Any]:
    (part,) = answer["parts"]
    return part


def test_an_ifc_answer_part_has_its_file_view_and_counted_elements(on: TestClient) -> None:
    data, walls = house()
    project_id = upload(on, data, "house.ifc")
    part = parts_of(on.post(f"/api/projects/{project_id}/ask", json=WALLS).json())
    assert part["answer"]["answer"] == 2
    assert part["file_id"] == part["model_file_id"] == file_of(on, project_id, "house.ifc")["id"]
    assert part["model_3d"]["state"] == "not_started"
    assert part["highlight"] == [{"global_id": guid, "role": "affected"} for guid in walls[:2]]


def test_off_a_part_has_file_id_and_highlight_but_no_model_3d(client: TestClient) -> None:
    data, walls = house()
    project_id = upload(client, data, "house.ifc")
    part = parts_of(client.post(f"/api/projects/{project_id}/ask", json=WALLS).json())
    assert part["file_id"] == part["model_file_id"] == "f1"
    assert "model_3d" not in part
    assert {item["global_id"] for item in part["highlight"]} == set(walls[:2])


def test_a_chat_answer_part_has_the_view_state_now_and_keeps_none(
    on: TestClient, settings: Settings
) -> None:
    data, walls = house()
    project_id = upload(on, data, "house.ifc")
    turn = on.post(f"/api/projects/{project_id}/chat", json={"message": WALLS["question"]})
    part = parts_of(turn.json()["answers"][0])
    assert (part["file_id"], part["model_3d"]["state"]) == ("f1", "not_started")
    assert {item["global_id"] for item in part["highlight"]} == set(walls[:2])
    kept = [
        path for path in settings.projects_dir.rglob("*.json") if b"model_3d" in path.read_bytes()
    ]
    assert kept == []  # the state is put on at response time only, never kept with the chat


def test_a_sheet_read_from_its_model_points_at_the_model_file(on: TestClient) -> None:
    built = demo()
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as packed:
        for path, data in ((SHEET, built.pdf), (TWIN, built.svg), (MODEL, built.ifc)):
            packed.writestr(path, data)
    project_id = upload(on, archive.getvalue(), "demo.zip")
    asked = on.post(f"/api/projects/{project_id}/ask", json={"question": "How many doors?"})
    parts = {part["name"]: part for part in asked.json()["parts"]}
    model_id = file_of(on, project_id, MODEL)["id"]
    sheet = parts[SHEET]
    assert sheet["file_id"] == file_of(on, project_id, SHEET)["id"] != model_id
    assert sheet["model_file_id"] == parts[MODEL]["model_file_id"] == model_id
    assert sheet["model_3d"]["state"] == "not_started"


def test_the_chat_stream_answer_has_the_view_state_and_keeps_none(
    on: TestClient, settings: Settings
) -> None:
    data, walls = house()
    project_id = upload(on, data, "house.ifc")
    events = stream(on, project_id, WALLS["question"])
    kind, turn = events[-1]
    assert kind == "answer"
    part = parts_of(turn["answers"][0])
    assert (part["model_file_id"], part["model_3d"]["state"]) == ("f1", "not_started")
    assert {item["global_id"] for item in part["highlight"]} == set(walls[:2])
    kept = [
        path for path in settings.projects_dir.rglob("*.json") if b"model_3d" in path.read_bytes()
    ]
    assert kept == []


def test_a_failed_check_on_a_sheet_with_its_model_highlights_the_element(
    settings: Settings, tmp_path: Path
) -> None:
    """Issue.model_file_id and Issue.highlight (board #14 c6883948897): a failed check of a door
    the sheet's model lists gets the model file and the door's GlobalId; additive only."""
    body = json.loads((RULES / "test.json").read_text())
    door = next(rule for rule in body["rules"] if rule["op"] == "door_width")
    (tmp_path / "test.json").write_text(json.dumps({**body, "rules": [{**door, "limit": 3.0}]}))
    on = serving(settings.model_copy(update={"model_3d": True}), tmp_path)
    built = demo()
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as packed:
        for path, data in ((SHEET, built.pdf), (TWIN, built.svg), (MODEL, built.ifc)):
            packed.writestr(path, data)
    project_id = upload(on, archive.getvalue(), "demo.zip")
    found = on.get(f"/api/projects/{project_id}/issues", params={"pack": "test"}).json()
    fails = [issue for issue in found["issues"] if issue["kind"] == "code_check_failed"]
    assert fails, "the 3 m door rule fails the demo's door"
    model_id = file_of(on, project_id, MODEL)["id"]
    drawing = on.get(f"/api/projects/{project_id}").json()["drawings"]
    sheet = next(d for d in drawing if d["file"] == SHEET)["drawing_id"]
    checks = on.get(
        f"/api/drawings/{sheet}/checks", params={"pack": "test", "project": project_id}
    ).json()
    ids = {
        f"test:{result['id']}": result["subject"].get("global_id")
        for rule in checks["rules"]
        for result in rule["results"]
    }
    on_sheet = [issue for issue in fails if issue["drawing_id"] == sheet]
    assert on_sheet
    for issue in on_sheet:
        assert issue["file"] == SHEET and issue["model_file_id"] == model_id
        assert ids[issue["check"]]  # the door is one the model lists
        assert issue["highlight"] == [{"global_id": ids[issue["check"]], "role": "affected"}]
    # other issues (conflicts) carry neither field
    for issue in found["issues"]:
        if issue["kind"] != "code_check_failed":
            assert "highlight" not in issue and "model_file_id" not in issue


def test_a_failed_check_on_a_plain_sheet_has_no_3d_fields(client: TestClient) -> None:
    project_id = upload(client, checks_sheet(), "flat-fi.pdf")
    found = client.get(f"/api/projects/{project_id}/issues", params={"pack": "fi"}).json()
    fails = [issue for issue in found["issues"] if issue["kind"] == "code_check_failed"]
    assert fails
    for issue in fails:
        assert "highlight" not in issue and "model_file_id" not in issue

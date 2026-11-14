"""GET /api/projects/{id}/files/{file_id}/model.glb and FileStatus.model_3d (MODEL_3D): off, the
route is 404 and no payload changes; on, an IFC file's first GET starts its conversion (409),
then the GLB is served, gzipped when the client takes it."""

import gzip
import time
from typing import Any

import pytest
from conftest import upload
from fastapi.testclient import TestClient
from test_ifc_glb import flat, house, node_names

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

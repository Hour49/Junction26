"""QA R4-G1 and R4-G2: an upload's name is a display name, never a path, and no response names
the server's folder; an image too large to open safely says so in plain words, never in Pillow's
"DecompressionBombError ... DOS attack" text."""

import io

import pytest
from conftest import upload
from fastapi.testclient import TestClient
from PIL import Image

from app.adapters.paths import inside
from app.core.errors import InvalidInputError
from app.settings import Settings

SCAN = (4000, 3000)  # 12 megapixels; the tests lower the limit to 6, so no huge image is made


def _blank(image_format: str) -> bytes:
    buffer = io.BytesIO()
    Image.new("1", SCAN, 1).save(buffer, image_format)
    return buffer.getvalue()


def _everything_shown(client: TestClient, project_id: str) -> str:
    urls = (f"/api/projects/{project_id}", "/api/projects", f"/api/projects/{project_id}/traces")
    return "".join(client.get(url).text for url in urls)


@pytest.mark.parametrize("name", ["..", ".", "a/..", "..\\", "", "C:"])
def test_an_upload_named_no_file_name_is_refused_at_the_door(
    client: TestClient, settings: Settings, plan_pdf: bytes, name: str
) -> None:
    response = client.post("/api/projects", params={"name": name}, content=plan_pdf)
    assert response.status_code == 422, response.text
    assert str(settings.projects_dir.parent) not in response.text
    assert client.get("/api/projects").json()["projects"] == []  # nothing was queued


@pytest.mark.parametrize("name", ["../x.zip", "/etc/passwd.zip", "..\\..\\plan.pdf"])
def test_an_upload_named_as_a_path_is_read_and_no_answer_names_the_server_folder(
    client: TestClient, settings: Settings, plan_pdf: bytes, name: str
) -> None:
    project_id = upload(client, plan_pdf, name)
    project = client.get(f"/api/projects/{project_id}").json()
    assert project["state"] == "done"
    assert project["name"] == name  # shown as given: a display name
    assert [file["path"] for file in project["files"]] == [name.replace("\\", "/").split("/")[-1]]
    assert str(settings.projects_dir.parent) not in _everything_shown(client, project_id)


def test_a_path_outside_its_folder_is_refused_without_naming_the_folder(settings: Settings) -> None:
    with pytest.raises(InvalidInputError) as refused:
        inside(settings.projects_dir, "..")
    assert str(settings.projects_dir) not in str(refused.value)
    assert "not a path inside its folder" in str(refused.value)


@pytest.mark.parametrize("name, image_format", [("scan.png", "PNG"), ("scan.tif", "TIFF")])
def test_an_image_too_large_to_open_is_set_aside_in_plain_words(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, name: str, image_format: str
) -> None:
    data = _blank(image_format)
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 3_000_000)  # Pillow refuses over twice that
    project_id = upload(client, data, name)
    project = client.get(f"/api/projects/{project_id}").json()
    [file] = project["files"]
    assert file["state"] == "set_aside"
    assert "an image too large to open safely (12 megapixels; the limit is 6)" in file["reason"]
    shown = _everything_shown(client, project_id)
    assert "DecompressionBomb" not in shown and "DOS attack" not in shown

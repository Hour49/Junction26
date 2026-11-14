"""Projects, traces, drawings, pages, info and errors (docs/API.md)."""

import io
import zipfile

import pytest
from conftest import plan_png, upload
from fastapi.testclient import TestClient
from PIL import Image
from test_vector_pdf import swiss_sheet

from app.api import projects
from app.api.info import info
from app.main import create_app
from app.settings import Settings


def test_an_upload_starts_a_project_and_says_where_to_poll(
    client: TestClient, plan_pdf: bytes
) -> None:
    response = client.post("/api/projects", params={"name": "plan.pdf"}, content=plan_pdf)
    assert response.status_code == 202
    body = response.json()
    assert body == {
        "id": body["id"],
        "name": "plan.pdf",
        "state": "done",  # the tests ingest inside start
        "url": f"/api/projects/{body['id']}",
    }


def test_project_status_lists_every_file_and_one_drawing_per_plan(client: TestClient) -> None:
    sheet = swiss_sheet()
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as files:
        files.writestr("plans/flat.pdf", sheet.pdf())
        files.writestr("plans/flat.png", sheet.png())  # another rendering of the same plan
        files.writestr("notes.txt", "site visit notes")
    status = client.get(f"/api/projects/{upload(client, archive.getvalue(), 'p.zip')}").json()
    assert status["state"] == "done"
    assert {file["path"]: file["state"] for file in status["files"]} == {
        "plans/flat.pdf": "ready",
        "plans/flat.png": "ready",
        "notes.txt": "text_only",
    }
    (drawing,) = status["drawings"]
    assert (drawing["file"], drawing["group"], drawing["route"]) == (
        "plans/flat.pdf", "plans/flat", "vector",
    )  # fmt: skip
    assert [other["file"] for other in drawing["other_renderings"]] == ["plans/flat.png"]


def test_an_upload_needs_a_name(client: TestClient, plan_pdf: bytes) -> None:
    response = client.post("/api/projects", content=plan_pdf)
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation"
    assert "name" in body["detail"]
    assert body["errors"][0]["loc"] == ["query", "name"]


def test_an_upload_over_the_cap_is_refused_before_ingest(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(projects, "MAX_UPLOAD", 10)
    response = client.post("/api/projects", params={"name": "big.zip"}, content=b"x" * 11)
    assert response.status_code == 413
    assert response.json()["code"] == "too-large"


def test_an_upload_is_refused_while_too_many_projects_wait(
    client: TestClient, plan_pdf: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(projects, "MAX_WAITING", 0)
    response = client.post("/api/projects", params={"name": "plan.pdf"}, content=plan_pdf)
    assert (response.status_code, response.json()["code"]) == (429, "busy")


@pytest.mark.parametrize(
    "path",
    [
        "/api/projects/0123456789ab",
        "/api/projects/nope",
        "/api/projects/0123456789ab/files/f1/trace",
        "/api/projects/0123456789ab/files/x1/trace",
        "/api/drawings/0123456789abcdef",
        "/api/drawings/..%2F..%2Fetc",
        "/api/drawings/0123456789abcdef/pages/1.png",
        "/api/drawings/0123456789abcdef/takeoff",
    ],
)
def test_unknown_or_malformed_ids_are_404_without_a_path(client: TestClient, path: str) -> None:
    response = client.get(path)
    assert response.status_code == 404, path
    body = response.json()
    assert body["code"] == "not-found"
    assert "projects" not in body["detail"] and "/" not in body["detail"]


def test_an_unexpected_error_is_a_500_in_the_same_shape(settings: Settings) -> None:
    class Broken:
        def start(self, name: str, data: bytes) -> str:
            raise RuntimeError("boom at /srv/data/secret")

        def status(self, project_id: str) -> object:
            raise RuntimeError("boom at /srv/data/secret")

        trace = drawing = sheet = status

        def close(self) -> None:
            pass

    client = TestClient(create_app(settings, Broken()), raise_server_exceptions=False)  # type: ignore[arg-type]
    response = client.get("/api/projects/0123456789ab")
    assert response.status_code == 500
    assert response.json() == {"detail": "internal error", "code": "internal"}


def test_the_trace_gives_each_stage_of_a_file(client: TestClient, plan_pdf: bytes) -> None:
    project_id = upload(client, plan_pdf)
    trace = client.get(f"/api/projects/{project_id}/files/f1/trace").json()
    assert trace["project_id"] == project_id
    assert trace["file"]["id"] == "f1"
    assert [stage["stage"] for stage in trace["stages"]][:3] == ["unpack", "hash", "identify"]


def test_a_drawing_has_its_pages_reader_and_suggestions(
    client: TestClient, drawing_id: str
) -> None:
    body = client.get(f"/api/drawings/{drawing_id}").json()
    assert body["file"] == "plan.pdf"
    assert body["pages"] == [
        {
            "page": 1,
            "width": 600.0,
            "height": 400.0,
            "unit": "pt",
            "url": f"/api/drawings/{drawing_id}/pages/1.png",
            "normalised": None,
        }
    ]
    assert body["reader"]["question_parser"] == "templates"
    assert "model" not in body
    questions = [suggestion["question"] for suggestion in body["suggestions"]]
    assert "How many doors are there?" in questions


def test_every_suggestion_is_answered(client: TestClient, drawing_id: str) -> None:
    for suggestion in client.get(f"/api/drawings/{drawing_id}").json()["suggestions"]:
        answer = client.post(
            "/api/ask", json={"drawing_id": drawing_id, "question": suggestion["question"]}
        ).json()
        assert answer["refusal"] is None, suggestion
        assert answer["quantity"]["key"] == suggestion["quantity"]


def test_the_model_is_its_own_extraction_v1_document(client: TestClient, drawing_id: str) -> None:
    model = client.get(f"/api/drawings/{drawing_id}/model").json()
    assert model["schema"] == "extraction_v1"
    assert sum(element["class"] == "door" for element in model["elements"]) == 2
    assert "tables" not in model  # an optional list the drawing has none of is left out


def test_a_page_renders_as_png_at_a_fixed_width_and_is_cached(
    client: TestClient, drawing_id: str
) -> None:
    response = client.get(f"/api/drawings/{drawing_id}/pages/1.png", params={"width": 400})
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"
    with Image.open(io.BytesIO(response.content)) as image:
        assert image.size == (400, 267)  # the 600 x 400 pt page, aspect kept


def test_a_page_that_does_not_exist_is_404_and_a_free_width_422(
    client: TestClient, drawing_id: str
) -> None:
    assert client.get(f"/api/drawings/{drawing_id}/pages/2.png").status_code == 404
    response = client.get(f"/api/drawings/{drawing_id}/pages/1.png", params={"width": 500})
    assert response.status_code == 422


def test_an_image_sheet_renders_at_the_width_asked(client: TestClient) -> None:
    status = client.get(f"/api/projects/{upload(client, plan_png(), 'scan.png')}").json()
    (drawing,) = status["drawings"]
    assert (drawing["kind"], drawing["route"]) == ("png_plan", "raster")
    url = f"/api/drawings/{drawing['drawing_id']}/pages/1.png"
    with Image.open(io.BytesIO(client.get(url, params={"width": 400}).content)) as image:
        assert image.size == (400, 200)


def test_info_names_the_readers_and_the_limits(client: TestClient) -> None:
    body = client.get("/api/info").json()
    assert body["no_keys"] is True
    assert body["readers"]["question_parser"] == "templates"
    assert body["limits"] == {
        "upload_mb": 200,
        "file_mb": 600,
        "unpacked_mb": 2048,
        "files": 5000,
        "question_chars": 2000,
    }


@pytest.mark.parametrize(
    ("keyed", "no_keys"),
    [
        ({"raster_components": "elements=region:C,plans=region:C,rooms=gemini"}, False),
        ({"raster_components": "elements=decisions:region:C,plans=one-plan"}, False),
        ({"raster_components": "elements=exp:detector/A,plans=one-plan"}, True),
        (
            {"raster_components": "elements=dir:arm,plans=dir:arm", "decisions_confidence": True},
            False,
        ),
    ],
)
def test_info_says_when_a_reader_calls_a_keyed_service(
    settings: Settings, keyed: dict[str, object], no_keys: bool
) -> None:
    settings = settings.model_copy(update={"extractor_raster": "composite", **keyed})
    assert info(settings).no_keys is no_keys


def test_info_names_every_reader_a_project_was_read_with(
    client: TestClient, plan_pdf: bytes
) -> None:
    """Every reader ingest records on a project is named by /api/info too, with the same adapter
    (the raster components are source names, some local paths, so info leaves them out)."""
    project = client.get(f"/api/projects/{upload(client, plan_pdf)}").json()
    named = client.get("/api/info").json()["readers"]
    used = {key: name for key, name in project["readers"].items() if key != "raster_components"}
    assert used.items() <= named.items()


def test_the_sample_needs_its_archive(client: TestClient) -> None:
    response = client.post("/api/projects/sample")
    assert (response.status_code, response.json()["code"]) == (404, "not-found")
    assert "make_sample_archive.py" in response.json()["detail"]


def test_a_fresh_sample_resets_the_reviews_of_the_last_one(
    client: TestClient, settings: Settings, plan_pdf: bytes
) -> None:
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as files:
        files.writestr("plans/flat.pdf", plan_pdf)
    settings.sample_archive.write_bytes(archive.getvalue())
    first = client.post("/api/projects/sample").json()
    drawing_id = client.get(first["url"]).json()["drawings"][0]["drawing_id"]
    client.post(f"/api/drawings/{drawing_id}/signoff", json={"quantity": "door", "by": "Ana"})

    client.post("/api/projects/sample")  # not fresh: the sign-off stays
    door = rows(client, drawing_id)["door"]
    assert door["status"] == "signed"
    again = client.post("/api/projects/sample", params={"fresh": True})
    assert again.status_code == 202
    assert rows(client, drawing_id)["door"]["status"] == "single"


def rows(client: TestClient, drawing_id: str) -> dict[str, dict[str, object]]:
    body = client.get(f"/api/drawings/{drawing_id}/takeoff").json()
    return {row["key"]: row for row in body["quantities"]}


def test_projects_are_listed_newest_first(client: TestClient, plan_pdf: bytes) -> None:
    first = upload(client, plan_pdf, "a.pdf")
    second = upload(client, plan_png(), "b.png")
    listed = client.get("/api/projects").json()["projects"]
    assert {project["id"] for project in listed} == {first, second}
    assert listed == sorted(listed, key=lambda project: project["created_at"], reverse=True)
    assert all(project["drawings"] == 1 for project in listed)


def test_a_drawing_names_the_route_and_reader_it_was_read_with(
    client: TestClient, drawing_id: str
) -> None:
    reader = client.get(f"/api/drawings/{drawing_id}").json()["reader"]
    assert reader == {
        "route": "vector",
        "source": "plan.pdf",
        "extractor": "pdf",
        "second_counter": "ifc",
        "question_parser": "templates",
    }


def turned_photo() -> bytes:
    """A plan shot in portrait: stored 800 x 400 with EXIF orientation 6 (turn 90° to view)."""
    image = Image.open(io.BytesIO(plan_png())).convert("RGB")
    exif = Image.Exif()
    exif[0x0112] = 6
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", exif=exif)
    return buffer.getvalue()


def test_an_exif_turned_photo_is_shown_upright_and_its_page_is_in_that_frame(
    client: TestClient,
) -> None:
    project_id = upload(client, turned_photo(), "photo.jpg")
    (drawing,) = client.get(f"/api/projects/{project_id}").json()["drawings"]
    (page,) = client.get(f"/api/drawings/{drawing['drawing_id']}").json()["pages"]
    assert (page["width"], page["height"]) == (400, 800)  # upright: the EXIF turn applied
    assert page["normalised"]["exif"] == 6
    served = client.get(page["url"], params={"width": 400}).content
    preview = client.get(
        f"/api/projects/{project_id}/files/f1/preview.png", params={"width": 400}
    ).content
    for png in (served, preview):
        with Image.open(io.BytesIO(png)) as image:
            assert image.size == (400, 800)


def test_a_file_that_is_no_image_or_pdf_has_no_preview(client: TestClient) -> None:
    project_id = upload(client, b"site visit notes\n", "notes.txt")
    response = client.get(f"/api/projects/{project_id}/files/f1/preview.png")
    assert response.status_code == 404


def test_a_fresh_sample_is_ingested_again_not_reused(
    client: TestClient, settings: Settings, plan_pdf: bytes
) -> None:
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as files:
        files.writestr("plans/flat.pdf", plan_pdf)
    settings.sample_archive.write_bytes(archive.getvalue())
    client.post("/api/projects/sample")
    again = client.get(client.post("/api/projects/sample").json()["url"]).json()
    assert [file["reused"] for file in again["files"]] == [True]
    fresh = client.post("/api/projects/sample", params={"fresh": True}).json()
    assert [file["reused"] for file in client.get(fresh["url"]).json()["files"]] == [False]

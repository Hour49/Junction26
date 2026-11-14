"""Projects, traces, drawings, pages, info and errors (docs/API.md)."""

import io
import json
import socket
import threading
import time
import zipfile
from contextlib import ExitStack

import pytest
import uvicorn
from conftest import plan_png, upload
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image
from test_review_core import BOX_A, disputed, quantity
from test_vector_pdf import swiss_sheet

from app.api import projects, takeoff
from app.api.info import info
from app.main import create_app
from app.settings import Settings
from scripts.make_sample_archive import build_archive


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


def test_the_same_drawing_under_two_names_lists_both(client: TestClient) -> None:
    """Two identical files are one drawing (same id); the copy is named under the shown one."""
    plan = swiss_sheet().pdf()
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as files:
        files.writestr("scans/ground-floor.pdf", plan)
        files.writestr("scans/ground-floor-copy.pdf", plan)
    status = client.get(f"/api/projects/{upload(client, archive.getvalue(), 'p.zip')}").json()
    ids = {file["path"]: file["drawing_id"] for file in status["files"]}
    assert ids["scans/ground-floor.pdf"] == ids["scans/ground-floor-copy.pdf"]
    (drawing,) = status["drawings"]
    assert drawing["file"] == "scans/ground-floor.pdf"
    assert drawing["other_renderings"] == [
        {"drawing_id": drawing["drawing_id"], "file": "scans/ground-floor-copy.pdf"}
    ]


def test_a_drawing_seen_before_is_named_as_this_project_uploaded_it(client: TestClient) -> None:
    """R1-3-6: the same bytes in a later project under another name are the same drawing (cache),
    but the screen of that project names the file it uploaded, never the earlier upload."""
    plan = swiss_sheet().pdf()
    upload(client, plan, "colorful-10706.pdf")
    later = upload(client, plan, "my-flat.pdf")
    (entry,) = client.get(f"/api/projects/{later}").json()["drawings"]
    drawing_id = entry["drawing_id"]
    shown = client.get(f"/api/drawings/{drawing_id}", params={"project": later}).json()
    assert (shown["file"], shown["reader"]["source"]) == ("my-flat.pdf", "my-flat.pdf")
    question = {"drawing_id": drawing_id, "question": "How many doors are there?"}
    answer = client.post("/api/ask", json={**question, "project_id": later}).json()
    assert (answer["file"], answer["reader"]["source"]) == ("my-flat.pdf", "my-flat.pdf")
    first = client.get(f"/api/drawings/{drawing_id}").json()  # no project: as before
    assert first["file"] == "colorful-10706.pdf"


def test_the_same_drawing_twice_in_a_project_is_named_as_listed(client: TestClient) -> None:
    """R1-4-4: two identical files; the drawing opened from the project is named as its entry."""
    plan = swiss_sheet().pdf()
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as files:
        files.writestr("scans/ground-floor.pdf", plan)
        files.writestr("scans/ground-floor-copy.pdf", plan)
    project = upload(client, archive.getvalue(), "p.zip")
    (entry,) = client.get(f"/api/projects/{project}").json()["drawings"]
    shown = client.get(f"/api/drawings/{entry['drawing_id']}", params={"project": project}).json()
    assert shown["file"] == entry["file"] == "scans/ground-floor.pdf"


def test_takeoff_and_csv_name_the_drawing_as_each_project_uploaded_it(client: TestClient) -> None:
    """R1-4-4/R1-3-6 in the surveyor: the same bytes in two projects under two names; each
    project's takeoff, edits, sign-offs and CSV name its own file."""
    plan = swiss_sheet().pdf()
    first = upload(client, plan, "colorful-10706.pdf")
    later = upload(client, plan, "my-flat.pdf")
    (entry,) = client.get(f"/api/projects/{later}").json()["drawings"]
    url = f"/api/drawings/{entry['drawing_id']}"
    for project, name in ((first, "colorful-10706.pdf"), (later, "my-flat.pdf")):
        at = {"project": project}
        assert client.get(f"{url}/takeoff", params=at).json()["file"] == name
        edited = client.post(f"{url}/review", params=at, json={"action": "reset"})
        assert edited.json()["file"] == name
        door = {"quantity": "door", "by": "Ana"}
        signed = client.post(f"{url}/signoff", params=at, json={**door, "undo": True})
        assert signed.json()["file"] == name
        sheet = client.get(f"{url}/takeoff.csv", params=at)
        assert sheet.text.splitlines()[1].startswith(f"{name},")
        stem = name.removesuffix(".pdf")
        assert sheet.headers["content-disposition"] == f'attachment; filename="{stem}-takeoff.csv"'
    other = upload(client, b"site notes", "notes.txt")
    assert client.get(f"{url}/takeoff", params={"project": other}).status_code == 404


def test_a_drawing_asked_in_a_project_without_it_is_404(
    client: TestClient, plan_pdf: bytes
) -> None:
    project = upload(client, plan_pdf)
    (entry,) = client.get(f"/api/projects/{project}").json()["drawings"]
    other = upload(client, b"site notes", "notes.txt")
    response = client.get(f"/api/drawings/{entry['drawing_id']}", params={"project": other})
    assert (response.status_code, response.json()["code"]) == (404, "not-found")
    asked = {"drawing_id": entry["drawing_id"], "question": "How many doors?", "project_id": other}
    assert client.post("/api/ask", json=asked).status_code == 404


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


def test_uploads_still_being_received_count_toward_the_limit(client: TestClient) -> None:
    """R1-5 429 race: the check and the count were apart, so 5 uploads got in with a limit of 3.
    Five threads each take a slot and hold it; exactly MAX_WAITING get one, the rest a 429."""
    admission: projects.Admission = client.app.state.admission  # type: ignore[attr-defined]
    ingest = client.app.state.ingest  # type: ignore[attr-defined]
    arrived, release = threading.Barrier(6), threading.Event()
    outcomes: list[int] = []

    def try_upload() -> None:
        try:
            with admission.slot(ingest):
                outcomes.append(202)
                arrived.wait()
                release.wait()
        except HTTPException as refused:
            outcomes.append(refused.status_code)
            arrived.wait()

    threads = [threading.Thread(target=try_upload) for _ in range(5)]
    for thread in threads:
        thread.start()
    arrived.wait()  # every thread holds a slot or was refused
    assert sorted(outcomes) == [202] * projects.MAX_WAITING + [429] * (5 - projects.MAX_WAITING)
    release.set()
    for thread in threads:
        thread.join()
    with admission.slot(ingest):  # the slots were given back
        pass


def test_the_sample_is_never_refused_as_busy(client: TestClient, plan_pdf: bytes) -> None:
    """A background ingest must not block "Try the sample project" at the demo (orchestrator)."""
    admission: projects.Admission = client.app.state.admission  # type: ignore[attr-defined]
    ingest = client.app.state.ingest  # type: ignore[attr-defined]
    with ExitStack() as held:
        for _ in range(projects.MAX_WAITING):
            held.enter_context(admission.slot(ingest))
        busy = client.post("/api/projects", params={"name": "plan.pdf"}, content=plan_pdf)
        assert (busy.status_code, busy.json()["code"]) == (429, "busy")
        assert client.post("/api/projects/sample", params={"fresh": True}).status_code == 202


def test_a_large_upload_refused_as_busy_gets_the_429_not_a_reset(client: TestClient) -> None:
    """R3-qa-3-1: the 429 went out before the body was read; uvicorn then closed the socket with
    megabytes unread, the kernel reset it, and a client still writing (urllib, the QA proxy, Vite
    sometimes) saw "connection reset" (shown as 502) instead of `busy`. A real server and a client
    that writes the whole 32 MB body (far over the socket buffers) before it reads."""
    app = client.app
    admission: projects.Admission = app.state.admission  # type: ignore[attr-defined]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning"))
    serving = threading.Thread(target=server.run, daemon=True)
    serving.start()
    while not server.started:
        time.sleep(0.01)
    port = server.servers[0].sockets[0].getsockname()[1]
    body = b"x" * (32 * 2**20)
    try:
        with ExitStack() as held:
            for _ in range(projects.MAX_WAITING):
                held.enter_context(admission.slot(app.state.ingest))  # type: ignore[attr-defined]
            with socket.create_connection(("127.0.0.1", port), timeout=30) as sock:
                sock.sendall(
                    b"POST /api/projects?name=big.zip HTTP/1.1\r\nHost: test\r\n"
                    + b"Connection: close\r\n"
                    + f"Content-Length: {len(body)}\r\n\r\n".encode()
                    + body
                )
                answer = sock.makefile("rb").read()
    finally:
        server.should_exit = True
        serving.join()
    head, _, payload = answer.partition(b"\r\n\r\n")
    assert head.startswith(b"HTTP/1.1 429")
    assert json.loads(payload)["code"] == "busy"


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


def test_a_missing_sample_archive_is_built_on_the_first_click(
    client: TestClient, settings: Settings
) -> None:
    """R1-5-1: a fresh deploy has no data/samples; "Try the sample project" still works."""
    assert not settings.sample_archive.exists()
    response = client.post("/api/projects/sample")
    assert response.status_code == 202
    assert settings.sample_archive.read_bytes() == build_archive()
    assert len(client.get(response.json()["url"]).json()["files"]) == 11


def test_a_sample_that_cannot_be_built_is_refused_in_plain_words(
    client: TestClient, settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    settings.sample_archive.parent.joinpath("blocked").write_text("a file, not a folder")
    settings.sample_archive = settings.sample_archive.parent / "blocked" / "sample-project.zip"
    response = client.post("/api/projects/sample")
    assert response.json() == {
        "detail": "The sample project isn't available on this server",
        "code": "not-found",
    }
    assert "make_sample_archive.py" in caplog.text  # the developer's hint goes to the log


def test_a_fresh_sample_resets_the_reviews_of_the_last_one(
    client: TestClient, settings: Settings, plan_pdf: bytes
) -> None:
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as files:
        files.writestr("plans/flat.pdf", plan_pdf)
    settings.sample_archive.write_bytes(archive.getvalue())
    first = client.post("/api/projects/sample").json()["id"]
    drawing_id = client.get(f"/api/projects/{first}").json()["drawings"][0]["drawing_id"]
    sign = {"quantity": "door", "by": "Ana"}
    client.post(f"/api/drawings/{drawing_id}/signoff", params={"project": first}, json=sign)

    again = client.post("/api/projects/sample").json()["id"]  # not fresh, a new project
    assert rows(client, drawing_id, again)["door"]["status"] == "single"  # its own review
    assert rows(client, drawing_id, first)["door"]["status"] == "signed"
    client.post(f"/api/drawings/{drawing_id}/signoff", params={"project": again}, json=sign)
    fresh = client.post("/api/projects/sample", params={"fresh": True})
    assert fresh.status_code == 202
    assert rows(client, drawing_id, again)["door"]["status"] == "single"  # the last one reset
    assert rows(client, drawing_id, fresh.json()["id"])["door"]["status"] == "single"


def rows(client: TestClient, drawing_id: str, project: str) -> dict[str, dict[str, object]]:
    body = client.get(f"/api/drawings/{drawing_id}/takeoff", params={"project": project}).json()
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
        "second_counter": "pdf",
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


def test_the_reader_names_a_second_counter_only_for_what_it_measured(
    client: TestClient, plan_pdf: bytes
) -> None:
    """R1-5-3 / R1-2-1: a raster plan, and a door count on a lone swiss PDF, read "second count
    by ifc" next to "no second check". The drawing names its second counter only when it measured
    something on it; an answer only when it measured the answered quantity."""

    def drawing_of(data: bytes, name: str) -> str:
        project = client.get(f"/api/projects/{upload(client, data, name)}").json()
        return project["drawings"][0]["drawing_id"]

    def counter(drawing_id: str, question: str | None = None) -> object:
        if question is None:
            return client.get(f"/api/drawings/{drawing_id}").json()["reader"]["second_counter"]
        body = {"drawing_id": drawing_id, "question": question}
        return client.post("/api/ask", json=body).json()["reader"]["second_counter"]

    png = drawing_of(plan_png(), "plan.png")
    assert (counter(png), counter(png, "How many doors are there?")) == ("none", "none")
    pdf = drawing_of(plan_pdf, "plan.pdf")  # its printed room areas are measured twice
    # R2-qa4-1, R2-qa-1-2: the IFC counter passes a file that is no model on to the PDF
    # counter, which measured it: the reader names that one
    assert counter(pdf) == "pdf"
    assert counter(pdf, "What is the net floor area of room 2.01?") == "pdf"
    assert counter(pdf, "How many doors are there?") == "none"  # one method
    assert counter(pdf, "What colour is the roof?") == "none"


def test_review_edits_and_sign_offs_belong_to_the_project(client: TestClient) -> None:
    """R1b-4-1 (decided 2026-11-14 06:14): the same bytes in two projects are one drawing, but a
    sign-off in one project never shows in the other, nor without a project."""
    plan = swiss_sheet().pdf()
    first, later = upload(client, plan, "A.pdf"), upload(client, plan, "B.pdf")
    (entry,) = client.get(f"/api/projects/{later}").json()["drawings"]
    drawing_id = entry["drawing_id"]
    url = f"/api/drawings/{drawing_id}"
    in_a = {"project": first}
    client.post(f"{url}/signoff", params=in_a, json={"quantity": "door", "by": "Ana"})

    def doors(project: str | None) -> str:
        params = {} if project is None else {"project": project}
        quantities = client.get(f"{url}/takeoff", params=params).json()["quantities"]
        return next(row["status"] for row in quantities if row["key"] == "door")

    assert (doors(first), doors(later), doors(None)) == ("signed", "single", "single")
    signed = {
        p: client.get(f"/api/projects/{p}/review").json()["drawings"][0]["signed"]
        for p in (first, later)
    }
    assert signed == {first: 1, later: 0}
    csv_b = client.get(f"{url}/takeoff.csv", params={"project": later}).text
    assert "Ana" not in csv_b

    def verified(project: str | None) -> bool:
        body = {"drawing_id": drawing_id, "question": "How many doors are there?"}
        if project is not None:
            body["project_id"] = project
        answer = client.post("/api/ask", json=body).json()
        return answer["quantity"]["signed"] is not None

    assert (verified(first), verified(later), verified(None)) == (True, False, False)
    # resetting B's edits leaves A's
    client.post(f"{url}/review", params={"project": later}, json={"action": "reset"})
    assert doors(first) == "signed"
    # a project that doesn't hold the drawing can't write its review
    other = upload(client, b"site notes", "notes.txt")
    door = {"quantity": "door", "by": "Eve"}
    assert client.post(f"{url}/signoff", params={"project": other}, json=door).status_code == 404


def test_settling_a_one_storey_sheet_s_row_decides_its_storey_twin_in_that_project_only(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """K4 per project (R1b-4-1): settling "window count" in project A also decides its storey
    twin "window count (storey p1)" in A, and neither row changes in project B."""
    windows = disputed(False)
    found = {
        key: quantity(key, 2, "count", BOX_A, conflict=windows)
        for key in ("window", "window|storey=p1")
    }
    monkeypatch.setattr(takeoff, "known_quantities", lambda drawing: found)
    plan = swiss_sheet().pdf()
    first, later = upload(client, plan, "A.pdf"), upload(client, plan, "B.pdf")
    (entry,) = client.get(f"/api/projects/{later}").json()["drawings"]
    url = f"/api/drawings/{entry['drawing_id']}"
    settle = {"quantity": "window", "action": "settle", "value": 3}
    assert client.post(f"{url}/review", params={"project": first}, json=settle).status_code == 200

    def twin(project: str) -> tuple[object, object]:
        quantities = client.get(f"{url}/takeoff", params={"project": project}).json()
        shown = next(row for row in quantities["quantities"] if row["key"] == "window|storey=p1")
        return shown["value"], shown["status"]

    assert twin(first) == (3, "edited")
    assert twin(later) == (2, "conflict")

"""GET /api/projects/{id}/issues and issues.csv: every finding of a project as a located issue
(decision 0008, story #140)."""

import csv
import io
import zipfile
from pathlib import PurePosixPath
from typing import Any

import pytest
from conftest import upload
from fastapi.testclient import TestClient
from PIL import Image
from test_review_core import BOX_A, disputed, quantity

from app.adapters.evidence_render import render as render_evidence
from app.api import issues, projects, takeoff
from app.api.questions import AskedQuestion, record
from app.core.drawing.model import Drawing
from app.core.review.proof import NO_PROOF
from app.settings import Settings
from scripts.make_sample_archive import build_archive

DOORS = "How many doors are there?"


def blank_jpeg() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (64, 64), "white").save(out, "JPEG")
    return out.getvalue()


def sample(client: TestClient) -> dict[str, Any]:
    return client.get(client.post("/api/projects/sample").json()["url"]).json()


def listed(client: TestClient, project_id: str) -> list[dict[str, Any]]:
    reply = client.get(f"/api/projects/{project_id}/issues")
    assert reply.status_code == 200, reply.text
    body = reply.json()
    assert (body["project_id"], body["pack"]) == (project_id, None)
    return body["issues"]


def drawing_of(project: dict[str, Any], path: str) -> str:
    return next(file["drawing_id"] for file in project["files"] if file["path"] == path)


def test_an_unknown_project_or_pack_is_404_and_a_running_one_409(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    for path in ("issues", "issues.csv"):
        assert client.get(f"/api/projects/0123456789ab/{path}").status_code == 404
    project = sample(client)
    reply = client.get(f"/api/projects/{project['id']}/issues", params={"pack": "fi"})
    assert reply.status_code == 404 and "fi" in reply.json()["detail"]  # no pack exists yet
    ingest = client.app.state.ingest  # type: ignore[attr-defined]
    running = ingest.status(project["id"]).model_copy(update={"state": "running"})
    monkeypatch.setattr(ingest, "status", lambda project_id: running)
    for path in ("issues", "issues.csv"):
        reply = client.get(f"/api/projects/{project['id']}/{path}")
        assert reply.status_code == 409 and reply.json()["code"] == "not-allowed"


def test_the_sample_lists_its_conflict_reading_flags_and_set_aside_files(
    client: TestClient,
) -> None:
    project = sample(client)
    found = {(issue["kind"], issue["file"]): issue for issue in listed(client, project["id"])}
    assert set(found) == {
        ("conflict", "plans/flat-b.pdf"),
        ("reading_flag", "scans/ground-floor.png"),
        ("reading_flag", "photos/plan-photo.jpg"),
        ("set_aside", "photos/site.jpg"),
        ("set_aside", "cad/detail.dxf"),
    }
    room = found[("conflict", "plans/flat-b.pdf")]  # a rule keeps the printed label's 30 m²
    assert (room["severity"], room["state"], room["quantity"]) == (
        "note", "settled", "area:room|name=1.01",
    )  # fmt: skip
    assert room["page"] == 1 and room["box"] == [0.16667, 0.125, 0.5, 0.375]  # the outline read
    assert room["why"].startswith("Area of room (name Küche · 1.01): checked twice, they disagree")
    assert room["why"].endswith(
        "kept 30 m²: the printed label over the outline at the sheet's scale."
    )
    assert room["floor"] is None  # a vector PDF names no storey: not guessed
    assert room["links"] == {
        "drawing": f"/api/drawings/{room['drawing_id']}?project={project['id']}",
        "takeoff": f"/api/drawings/{room['drawing_id']}/takeoff?project={project['id']}",
        "trace": f"/api/projects/{project['id']}/files/{room['file_id']}/trace",
        "checks": None,
    }
    photo = found[("reading_flag", "photos/plan-photo.jpg")]
    assert photo["why"] == (
        "A phone photo, read without perspective correction; no reader for the raster route "
        "yet: nothing was read."
    )
    assert (photo["page"], photo["box"], photo["state"]) == (1, None, "open")
    dxf = found[("set_aside", "cad/detail.dxf")]
    assert (dxf["drawing_id"], dxf["page"], dxf["links"]["drawing"]) == (None, None, None)
    assert dxf["why"] == f"Set aside at ingest: {dxf['reason']}."


def test_a_refused_answer_about_the_drawing_is_an_issue_a_parser_miss_is_not(
    client: TestClient, settings: Settings
) -> None:
    project = sample(client)
    scan = drawing_of(project, "scans/ground-floor.png")
    for question in (DOORS, "What colour is the roof?"):
        body = {"drawing_id": scan, "question": question, "project_id": project["id"]}
        assert client.post("/api/ask", json=body).status_code == 200
    older = AskedQuestion(  # a line from before the log kept the refusal code
        question="How many windows are there?", answer=None, unit=None, drawing_id=scan,
        at="2026-11-14T08:00:00Z", refused=True,
    )  # fmt: skip
    record(settings.projects_dir, project["id"], older)
    refused = [
        issue for issue in listed(client, project["id"]) if issue["kind"] == "refused_answer"
    ]
    assert [(issue["question"], issue["file"], issue["page"]) for issue in refused] == [
        (DOORS, "scans/ground-floor.png", None)
    ]
    assert refused[0]["why"] == f'No answer to "{DOORS}": the drawing has no reader for it.'
    lines = client.get(f"/api/projects/{project['id']}/questions").json()["questions"]
    assert [line.get("refusal") for line in lines] == [None, "unsupported-question", "no-reader"]


def test_a_conflict_nobody_decided_needs_a_person_and_keeps_its_id_when_settled_and_signed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, plan_pdf: bytes
) -> None:
    found = {"window": quantity("window", 2, "count", BOX_A, conflict=disputed(False))}
    monkeypatch.setattr(takeoff, "known_quantities", lambda drawing: found)
    project_id = upload(client, plan_pdf)
    (issue,) = listed(client, project_id)
    assert (issue["kind"], issue["severity"], issue["state"]) == (
        "conflict",
        "needs_person",
        "open",
    )
    assert (issue["page"], issue["box"]) == (1, list(BOX_A))  # the row's one mark
    assert issue["why"].endswith("no rule decides, a person must settle it.")
    assert listed(client, project_id) == [issue]  # the same id on every call
    url = f"/api/drawings/{issue['drawing_id']}"
    at = {"project": project_id}
    edit = {"quantity": "window", "action": "settle", "value": 3}
    assert client.post(f"{url}/review", params=at, json=edit).status_code == 200
    (settled,) = listed(client, project_id)
    assert (settled["id"], settled["severity"], settled["state"]) == (
        issue["id"],
        "note",
        "settled",
    )
    sign = {"quantity": "window", "by": "Ana"}
    assert client.post(f"{url}/signoff", params=at, json=sign).status_code == 200
    (signed,) = listed(client, project_id)
    assert (signed["id"], signed["state"]) == (issue["id"], "signed_off")
    assert signed["why"].endswith("; signed off by Ana.")


def test_issues_that_need_a_person_come_first(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    found = {"window": quantity("window", 2, "count", BOX_A, conflict=disputed(False))}
    monkeypatch.setattr(takeoff, "known_quantities", lambda drawing: found)
    severities = [issue["severity"] for issue in listed(client, sample(client)["id"])]
    assert severities[0] == "needs_person" and severities == sorted(
        severities, key=issues.SEVERITIES.index
    )


def test_a_floor_is_the_storey_its_source_names_and_null_otherwise() -> None:
    def sheet(*storeys: str | None) -> Drawing:
        return Drawing.model_validate(
            {
                "file": "sheet.pdf",
                "pages": [{"page": 1, "width": 100, "height": 100, "unit": "pt"}],
                "scale": {"status": "no_scale"},
                "plans": [
                    {"id": f"p{at}", "page": 1, "box": [0, 0, 1, 1], "storey": storey}
                    for at, storey in enumerate(storeys)
                ],
            }
        )

    assert issues._floor(sheet("01 - Entry Level"), 1) == "01 - Entry Level"
    assert issues._floor(sheet(None), 1) is None  # the plan names no storey
    assert issues._floor(sheet("Level 1", "Level 2"), 1) is None  # two storeys on the page
    assert issues._floor(sheet("Level 1"), None) is None  # no page: no plan to read it from


def test_the_csv_has_the_same_rows_and_text_from_a_file_cannot_run_as_a_formula(
    client: TestClient,
) -> None:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as zipped:
        zipped.writestr("=cmd.jpg", blank_jpeg())  # set aside: no line in it
    project_id = upload(client, out.getvalue(), "drawings.zip")
    found = listed(client, project_id)
    reply = client.get(f"/api/projects/{project_id}/issues.csv")
    assert reply.status_code == 200
    assert reply.headers["content-type"] == "text/csv; charset=utf-8"
    assert reply.headers["content-disposition"] == 'attachment; filename="drawings-issues.csv"'
    header, *rows = list(csv.reader(io.StringIO(reply.text)))
    assert tuple(header) == issues.CSV_COLUMNS
    assert [row[0] for row in rows] == [issue["id"] for issue in found] and len(rows) == 1
    (row,) = rows
    assert row[header.index("file")] == "'=cmd.jpg"  # escaped, as in the takeoff CSV
    assert row[header.index("drawing_id")] == "" and row[header.index("x0")] == ""


def test_the_csv_carries_a_box_as_four_numbers(client: TestClient) -> None:
    project = sample(client)
    reply = client.get(f"/api/projects/{project['id']}/issues.csv")
    rows = list(csv.DictReader(io.StringIO(reply.text)))
    room = next(row for row in rows if row["kind"] == "conflict")
    assert [room[key] for key in ("page", "x0", "y0", "x1", "y1")] == [
        "1", "0.16667", "0.125", "0.5", "0.375",
    ]  # fmt: skip


def test_a_room_conflict_is_placed_on_the_takeoff_mark_with_its_outline(client: TestClient) -> None:
    project = sample(client)
    (room,) = [issue for issue in listed(client, project["id"]) if issue["kind"] == "conflict"]
    rows = client.get(room["links"]["takeoff"]).json()["quantities"]
    (mark,) = next(row for row in rows if row["key"] == room["quantity"])["marks"]
    assert (room["mark_id"], room["page"], room["box"], room["polygon"]) == (
        mark["id"], mark["page"], mark["box"], mark["polygon"],
    )  # fmt: skip
    assert room["polygon"] is not None  # a room's outline, not only its box
    others = [issue for issue in listed(client, project["id"]) if issue["kind"] != "conflict"]
    assert all(issue["mark_id"] is None and issue["polygon"] is None for issue in others)


def test_an_unknown_pack_has_its_own_code(client: TestClient) -> None:
    project = sample(client)
    for path in ("issues", "issues.csv", "issues.zip"):
        reply = client.get(f"/api/projects/{project['id']}/{path}", params={"pack": "fi"})
        assert (reply.status_code, reply.json()["code"]) == (404, "unknown-pack")
        missing = client.get(f"/api/projects/0123456789ab/{path}", params={"pack": "fi"})
        assert (missing.status_code, missing.json()["code"]) == (404, "not-found")


def test_an_issue_names_the_file_as_this_project_uploaded_it(client: TestClient) -> None:
    with zipfile.ZipFile(io.BytesIO(build_archive())) as archive:
        flat_b = archive.read("plans/flat-b.pdf")
    sample(client)  # the same drawing, uploaded first as plans/flat-b.pdf
    project_id = upload(client, flat_b, "site-visit.pdf")
    (room,) = [issue for issue in listed(client, project_id) if issue["kind"] == "conflict"]
    assert (room["file"], room["file_id"]) == ("site-visit.pdf", "f1")


def test_issues_are_ordered_by_severity_drawing_page_and_box_top(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, plan_pdf: bytes
) -> None:
    low, high = (0.2, 0.6, 0.25, 0.65), (0.6, 0.1, 0.7, 0.2)
    found = {
        "door": quantity("door", 2, "count", (0.4, 0.4, 0.5, 0.5), conflict=disputed(True)),
        "window": quantity("window", 2, "count", low, conflict=disputed(False)),
        "toilet": quantity("toilet", 1, "count", high, conflict=disputed(False)),
    }
    monkeypatch.setattr(takeoff, "known_quantities", lambda drawing: found)
    project_id = upload(client, plan_pdf)
    order = [(issue["quantity"], issue["severity"]) for issue in listed(client, project_id)]
    assert order == [("toilet", "needs_person"), ("window", "needs_person"), ("door", "note")]


def test_the_project_list_counts_open_issues(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    found = {"window": quantity("window", 2, "count", BOX_A, conflict=disputed(False))}
    monkeypatch.setattr(takeoff, "known_quantities", lambda drawing: found)
    project = sample(client)
    (summary,) = client.get("/api/projects").json()["projects"]
    open_ones = [issue for issue in listed(client, project["id"]) if issue["state"] == "open"]
    assert summary["issues_open"] == len(open_ones) > 0


def test_the_project_list_counts_issues_once_and_again_after_a_refused_ask(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#145 keeps the list's counts until what they are made of changes; issues_open reads the
    question log too, so a new refused answer must show on the next list."""
    calls: list[str] = []
    open_count = projects.open_count

    def counted(status: Any, *args: Any) -> int:
        calls.append(status.id)
        return open_count(status, *args)

    monkeypatch.setattr(projects, "open_count", counted)
    project = sample(client)
    (before,) = client.get("/api/projects").json()["projects"]
    assert client.get("/api/projects").json()["projects"] == [before]
    assert calls == [project["id"]]
    body = {
        "drawing_id": drawing_of(project, "scans/ground-floor.png"),
        "question": DOORS,
        "project_id": project["id"],
    }
    assert client.post("/api/ask", json=body).status_code == 200  # refused: no reader
    (after,) = client.get("/api/projects").json()["projects"]
    assert after["issues_open"] == before["issues_open"] + 1
    assert calls == [project["id"]] * 2


def test_a_download_is_named_after_the_project_and_its_pack() -> None:
    assert issues._download("Site visit 2.zip", None, "csv") == "Site_visit_2-issues.csv"
    assert issues._download("site.zip", "fi", "zip") == "site-issues-fi.zip"


def zip_of(client: TestClient, project_id: str) -> zipfile.ZipFile:
    reply = client.get(f"/api/projects/{project_id}/issues.zip")
    assert reply.status_code == 200, reply.text
    assert reply.headers["content-type"] == "application/zip"
    assert reply.headers["content-disposition"].startswith("attachment; filename=")
    return zipfile.ZipFile(io.BytesIO(reply.content))


def test_the_zip_holds_the_numbered_csv_and_one_marked_png_per_page_with_boxes(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    found = {
        "window": quantity("window", 2, "count", BOX_A, conflict=disputed(False)),
        "door": quantity("door", 2, "count", (0.6, 0.5, 0.7, 0.6), conflict=disputed(True)),
    }
    monkeypatch.setattr(takeoff, "known_quantities", lambda drawing: found)
    project = sample(client)
    listing = listed(client, project["id"])
    archive = zip_of(client, project["id"])
    rows = list(csv.DictReader(io.StringIO(archive.read("issues.csv").decode())))
    assert [(int(row["n"]), row["id"]) for row in rows] == [
        (n, issue["id"]) for n, issue in enumerate(listing, start=1)
    ]
    model = [issue for issue in listing if issue["file"] == "model/house.ifc"]
    assert model and all(issue["page"] is None and issue["box"] is None for issue in model)
    boxed = {(issue["file"], issue["page"]) for issue in listing if issue["box"] is not None}
    pngs = sorted(name for name in archive.namelist() if name.endswith(".png"))
    # every drawing with a page has the patched conflicts; set-aside files and reading flags
    # have no box, so they are only in the CSV
    assert pngs == sorted({f"{PurePosixPath(file).stem}-p{page}.png" for file, page in boxed})
    assert {"photos/site.jpg", "cad/detail.dxf"} <= {row["file"] for row in rows}
    with Image.open(io.BytesIO(archive.read(pngs[0]))) as picture:
        assert picture.format == "PNG" and picture.width == issues.PAGE_WIDTH


def test_each_issue_sentence_under_a_marked_page_starts_its_own_line() -> None:
    """The zip's footer ran the issues' sentences together as one paragraph (#147 review)."""
    page = io.BytesIO()
    Image.new("RGB", (800, 600), "white").save(page, "PNG")

    def height(said: str) -> int:
        proof = NO_PROOF.model_copy(update={"kind": "count", "arithmetic": said})
        png = render_evidence(page.getvalue(), 1, [], proof, "plan.pdf, page 1", None, 800)
        with Image.open(io.BytesIO(png)) as picture:
            return picture.height

    one_line = height("1. A door.  2. A window.")
    assert height("1. A door.\n2. A window.") > one_line == height("1. A door.")


def test_a_page_without_issues_has_no_png(client: TestClient, plan_pdf: bytes) -> None:
    archive = zip_of(client, upload(client, plan_pdf))  # a clean sheet: no issue at all
    assert archive.namelist() == ["issues.csv"]
    (header,) = list(csv.reader(io.StringIO(archive.read("issues.csv").decode())))
    assert tuple(header) == ("n", *issues.CSV_COLUMNS)


def test_two_files_with_the_same_stem_get_two_png_names() -> None:
    taken: set[str] = {"issues.csv"}
    names = [issues._unique(name, taken) for name in ("plan-p1.png", "plan-p1.png", "plan-p1.png")]
    assert names == ["plan-p1.png", "plan-p1-2.png", "plan-p1-3.png"]

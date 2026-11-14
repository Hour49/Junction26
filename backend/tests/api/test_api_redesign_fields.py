"""The fields the Vellum redesign asked for (board #14, 2026-11-14), all optional and additive."""

import io
import zipfile
from typing import Any

from conftest import upload
from fastapi.testclient import TestClient
from test_vector_pdf import swiss_sheet

from app.api.views import expected_drawings_of, page_views
from app.core.drawing.model import Drawing, Page, Plan, Scale
from app.core.ingest.model import FileStatus, ProjectStatus

ROOM = "area:room|name=1.01"  # the sample's flat-b conflict


def archive(**files: bytes | str) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as zipped:
        for name, content in files.items():
            zipped.writestr(name.replace("__", "/"), content)
        zipped.writestr(zipfile.ZipInfo("../outside.pdf"), b"%PDF-1.4")  # refused at unpack
    return out.getvalue()


def sample(client: TestClient) -> tuple[str, dict[str, Any]]:
    url = client.post("/api/projects/sample").json()["url"]
    return url, client.get(url).json()


def test_a_project_says_when_its_run_started_and_finished(
    client: TestClient, plan_pdf: bytes
) -> None:
    project = client.get(f"/api/projects/{upload(client, plan_pdf)}").json()
    assert project["created_at"] <= project["started_at"] <= project["finished_at"]


def test_a_project_lists_the_files_set_aside_with_their_reason(client: TestClient) -> None:
    data = archive(plans__flat=swiss_sheet().pdf())
    project = client.get(f"/api/projects/{upload(client, data, 'p.zip')}").json()
    assert project["skipped"] == [
        {"path": file["path"], "reason": file["reason"]}
        for file in project["files"]
        if file["state"] == "set_aside"
    ]
    assert [found["path"] for found in project["skipped"]] == ["../outside.pdf"]
    assert project["skipped"][0]["reason"]


def test_expected_drawings_counts_a_group_and_a_copy_once() -> None:
    def file(path: str, group: str, sha: str, state: str = "ready") -> FileStatus:
        return FileStatus.model_validate(
            {"id": "f1", "path": path, "size": 1, "sha256": sha, "kind": "png_plan",
             "group": group, "state": state}
        )  # fmt: skip

    files = (
        file("a.pdf", "a", "1"),
        file("a.png", "a", "2"),  # another rendering of a
        file("copy.png", "copy", "2"),  # a copy of a's png under another name
        file("b.png", "b", "3"),
        file("c.png", "c", "4", state="set_aside"),
    )

    def status(state: str) -> ProjectStatus:
        return ProjectStatus.model_validate(
            {"id": "p", "name": "p", "state": state, "created_at": "t", "files": files}
        )

    assert expected_drawings_of(status("running")) == 2
    assert expected_drawings_of(status("queued")) is None


def test_the_sample_expects_the_drawings_it_ends_with(client: TestClient) -> None:
    _, project = sample(client)
    assert project["expected_drawings"] == len(project["drawings"]) == 5


def test_every_trace_of_a_project_in_one_request(client: TestClient) -> None:
    url, project = sample(client)
    together = client.get(f"{url}/trace").json()
    assert together["project_id"] == project["id"]
    assert [found["file"]["id"] for found in together["files"]] == [
        file["id"] for file in project["files"]
    ]
    for found in together["files"]:
        alone = client.get(f"{url}/files/{found['file']['id']}/trace").json()
        assert found == alone
    assert client.get("/api/projects/0123456789ab/trace").status_code == 404


def test_a_trace_counts_what_the_second_method_measured(client: TestClient) -> None:
    url, project = sample(client)
    seconds = {
        file["path"]: client.get(f"{url}/files/{file['id']}/trace").json()["second_count"]
        for file in project["files"]
    }
    assert seconds["plans/flat-b.pdf"] == {"measured": 5, "conflicts": 1}
    assert seconds["plans/flat-a.pdf"] == {"measured": 5, "conflicts": 0}
    assert seconds["docs/notes.txt"] is None  # no drawing


def test_a_conflict_carries_its_value_and_sign_off(client: TestClient) -> None:
    url, project = sample(client)
    flat_b = next(file for file in project["files"] if file["path"] == "plans/flat-b.pdf")
    drawing = f"/api/drawings/{flat_b['drawing_id']}"
    at = {"project": project["id"]}

    def entry() -> dict[str, Any]:
        conflicts = client.get(f"{url}/review").json()["conflicts"]
        return next(found for found in conflicts if found["quantity"] == ROOM)

    assert entry()["signed"] is None
    settle = {"quantity": ROOM, "action": "settle", "value": 30}
    assert client.post(f"{drawing}/review", params=at, json=settle).status_code == 200
    assert (entry()["value"], entry()["signed"]) == (30, None)
    sign = {"quantity": ROOM, "by": "Ana"}
    assert client.post(f"{drawing}/signoff", params=at, json=sign).status_code == 200
    signed = entry()["signed"]
    assert (signed["by"], signed["value"]) == ("Ana", 30)


def test_a_page_has_its_scale_and_storey(client: TestClient, plan_pdf: bytes) -> None:
    project = client.get(f"/api/projects/{upload(client, plan_pdf)}").json()
    page = client.get(f"/api/drawings/{project['drawings'][0]['drawing_id']}").json()["pages"][0]
    assert page["scale_text"] == "1:100"
    assert page["scale"]["ratio"] == 100.0
    assert page["scale"]["status"] == "scaled"
    assert page["storey"] is None  # the plan names none


def test_page_views_read_the_ratio_and_the_one_storey_of_the_page() -> None:
    def views(text: str | None, *storeys: int | str | None) -> Any:
        plans = tuple(
            Plan(id=f"p{at}", page=1, box=(0, 0, 1, 1), storey=storey)
            for at, storey in enumerate(storeys)
        )
        drawing = Drawing(
            file="a.pdf",
            pages=(Page(page=1, width=10, height=10, unit="px"),),
            scale=Scale(status="scaled", m_per_unit=0.01, text=text),
            plans=plans,
        )
        return page_views("d", drawing, None)[0]

    assert (views("1:50", 2).scale.ratio, views("1:50", 2).storey) == (50.0, "2")
    assert views("1 : 100").scale.ratio == 100.0
    assert views("scale 1:100").scale.ratio is None  # not a bare ratio
    assert views("scale 1:100").scale_text == "scale 1:100"
    assert views(None).scale.ratio is None
    assert views("1:50", "A", "B").storey is None  # two storeys on one page


def test_a_row_names_what_it_counts_and_a_mark_its_room_type(client: TestClient) -> None:
    _, project = sample(client)
    flat_a = next(file for file in project["files"] if file["path"] == "plans/flat-a.pdf")
    rows = client.get(f"/api/drawings/{flat_a['drawing_id']}/takeoff").json()["quantities"]
    by_key = {row["key"]: row for row in rows}
    assert by_key["door"]["noun"] == "doors"
    assert by_key["area:room|indoor"]["noun"] is None
    marks = [mark for row in rows for mark in row["marks"]]
    assert {mark["room_type"] for mark in marks if mark["label"] == "Küche"} == {"kitchen"}
    assert all(mark["room_type"] is None for row in rows if row["key"] == "door"
               for mark in row["marks"])  # fmt: skip

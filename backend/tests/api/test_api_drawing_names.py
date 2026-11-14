"""Each drawing of the project response has a plain name and its licence credit (board #14 item 6,
2026-11-14): the name never shows the dataset file name, and the credit stays reachable when the
screen moves credits to an About page."""

import io
import zipfile
from typing import Any

from conftest import upload
from fastapi.testclient import TestClient
from test_api_credits import TABLE, drawing_set, write

from app.adapters.credits import SAMPLE
from app.api.views import drawings_of
from app.composition import build_ingest
from app.core.ingest.model import ProjectStatus
from app.main import create_app
from app.settings import Settings


def status(*files: dict[str, Any]) -> ProjectStatus:
    rows = [{"id": f"f{n}", "size": 1, "state": "ready", **file} for n, file in enumerate(files, 1)]
    return ProjectStatus.model_validate(
        {"id": "p", "name": "p", "state": "done", "created_at": "t", "files": rows}
    )


def read(path: str, kind: str, drawing_id: str, group: str | None = None) -> dict[str, Any]:
    """A file read as a drawing; its group is its own name unless it is given."""
    return {
        "path": path,
        "kind": kind,
        "sha256": drawing_id,
        "group": group or path.rsplit(".", 1)[0],
        "drawing_id": drawing_id,
    }


def test_a_drawing_is_named_by_its_kind_and_number_never_by_its_file_name() -> None:
    project = status(
        read("plans/site1029_bldg2117_floor9641.pdf", "pdf_vector", "d1", group="g1"),
        read("plans/site1029_bldg2117_floor9641.png", "png_plan", "d2", group="g1"),  # rendering
        read("scans/colorful-9392.png", "png_plan", "d3"),
        read("plans/b.pdf", "pdf_vector", "d4"),
        read("photos/042.jpg", "photo_plan", "d5"),
        read("bim/house.ifc", "ifc", "d6"),
        read("scans/permit.pdf", "pdf_scan", "d7"),
        read("sets/permit-set#p2.pdf", "pdf_vector", "d8"),
        read("copy-of-the-first.pdf", "pdf_vector", "d1"),  # the first one's content again
        read("site.dxf", "dxf", "d9"),
        read("camera.jpeg", "jpeg_plan", "d10"),
    )
    assert {entry.file: entry.name for entry in drawings_of(project)} == {
        "plans/site1029_bldg2117_floor9641.pdf": "Drawn plan 1",
        "scans/colorful-9392.png": "Plan image 1",
        "plans/b.pdf": "Drawn plan 2",
        "photos/042.jpg": "Plan photo 1",
        "bim/house.ifc": "Building model 1",
        "scans/permit.pdf": "Scanned plan 1",
        "sets/permit-set#p2.pdf": "Drawn plan 3, page 2",
        "site.dxf": "Drawn plan 4",
        "camera.jpeg": "Plan image 2",
    }


def test_a_drawing_has_no_credit_unless_a_lookup_is_given() -> None:
    project = status(read("a.pdf", "pdf_vector", "d1"), read("b.png", "png_plan", "d2"))
    assert [entry.credit for entry in drawings_of(project)] == [None, None]
    credited = drawings_of(project, credit_of={"a.pdf": "Ana (CC BY 4.0)"}.get)
    assert [entry.credit for entry in credited] == ["Ana (CC BY 4.0)", None]


def test_the_sample_project_names_and_credits_every_drawing(client: TestClient) -> None:
    project = client.get(client.post("/api/projects/sample").json()["url"]).json()
    assert [(entry["file"], entry["name"], entry["credit"]) for entry in project["drawings"]] == [
        ("plans/flat-a.pdf", "Drawn plan 1", SAMPLE),
        ("plans/flat-b.pdf", "Drawn plan 2", SAMPLE),
        ("plans/flat-c.pdf", "Drawn plan 3", SAMPLE),
        ("scans/ground-floor.png", "Plan image 1", SAMPLE),
        ("photos/plan-photo.jpg", "Plan photo 1", SAMPLE),
        ("model/house.ifc", "Building model 1", SAMPLE),
    ]


def test_a_dataset_file_under_any_name_is_credited_and_a_users_own_file_is_not(
    settings: Settings, plan_pdf: bytes
) -> None:
    source = settings.credit_dataset / "data" / "plans"
    write(source / "LICENSE.md", TABLE.encode())
    write(source / "a.pdf", plan_pdf)  # its own row of the table
    bundle = write(source / "set.pdf", drawing_set())  # the source's "All files" line
    own = plan_pdf.replace(b"%%EOF", b"%%EOF\n% own copy")
    upload_zip = io.BytesIO()
    with zipfile.ZipFile(upload_zip, "w") as out:
        out.writestr("renamed/my-plan.pdf", plan_pdf)
        out.writestr("own.pdf", own)
        out.writestr("bundle.pdf", bundle)
    client = TestClient(
        create_app(settings, build_ingest(settings, settings.projects_dir, background=False))
    )

    project = client.get(f"/api/projects/{upload(client, upload_zip.getvalue(), 'p.zip')}").json()
    assert {entry["file"]: entry["credit"] for entry in project["drawings"]} == {
        "renamed/my-plan.pdf": "Ana; Own work (CC BY-SA 4.0)",
        "own.pdf": None,
        "bundle#p2.pdf": "Plans dataset, CC BY 4.0.",  # the page has the credit of its set
    }

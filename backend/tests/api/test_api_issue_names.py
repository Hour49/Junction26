"""Issue texts name a drawing by its plain name (#224's `DrawingEntry.name`), never by the
dataset file it was uploaded as; machine fields (`file`, ids) keep the path."""

import io
import zipfile
from typing import Any

import pytest
from conftest import upload
from fastapi.testclient import TestClient
from test_api_issue_answers import window_conflict
from test_api_issues import listed

from app.api import issues

DATASET_NAME = "cubicasa5k_0042_F1_original.pdf"


def test_an_issue_on_a_dataset_named_file_names_its_drawing_not_the_file(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, plan_pdf: bytes
) -> None:
    window_conflict(monkeypatch)
    project_id = upload(client, plan_pdf, DATASET_NAME)
    project = client.get(f"/api/projects/{project_id}").json()
    (entry,) = project["drawings"]
    (issue,) = listed(client, project_id)
    assert issue["drawing_name"] == entry["name"] == "Drawn plan 1"  # as the project GET names it
    assert issue["file"] == DATASET_NAME  # the machine field keeps the path
    shown: list[str] = []
    render = issues.render_evidence

    def captured(*args: Any) -> bytes:
        shown.append(args[4])  # the line over the marked page
        return render(*args)

    monkeypatch.setattr(issues, "render_evidence", captured)
    reply = client.get(f"/api/projects/{project_id}/issues.zip")
    assert reply.status_code == 200
    assert len(zipfile.ZipFile(io.BytesIO(reply.content)).namelist()) == 2  # csv + one page
    (line,) = shown
    assert "cubicasa" not in line and line.startswith("Drawn plan 1, page 1")


def test_an_issue_without_a_drawing_has_no_drawing_name(client: TestClient) -> None:
    project = client.get(client.post("/api/projects/sample").json()["url"]).json()
    found = listed(client, project["id"])
    names = {entry["drawing_id"]: entry["name"] for entry in project["drawings"]}
    for entry in project["drawings"]:  # another rendering: the drawing's name
        for rendering in entry["other_renderings"]:
            names.setdefault(rendering["drawing_id"], entry["name"])
    for issue in found:
        expected = None if issue["drawing_id"] is None else names.get(issue["drawing_id"])
        assert issue["drawing_name"] == expected, issue
    assert any(issue["drawing_name"] for issue in found)

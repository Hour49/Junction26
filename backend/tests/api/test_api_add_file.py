"""POST /api/projects/{project_id}/files (board #203): a photo added to a finished project."""

from conftest import plan_png, upload
from fastapi.testclient import TestClient


def test_an_added_png_answers_202_queued_then_becomes_a_drawing(
    client: TestClient, plan_pdf: bytes
) -> None:
    pid = upload(client, plan_pdf)
    before = len(client.get(f"/api/projects/{pid}").json()["drawings"])
    added = client.post(f"/api/projects/{pid}/files", params={"name": "a.png"}, content=plan_png())
    assert added.status_code == 202, added.text
    file = added.json()
    assert (file["id"], file["path"], file["state"]) == ("f2", "a.png", "queued")
    project = client.get(f"/api/projects/{pid}").json()
    assert project["state"] == "done"
    assert next(f for f in project["files"] if f["id"] == "f2")["state"] in ("ready", "flagged")
    assert len(project["drawings"]) == before + 1


def test_refusals_are_404_415_and_422(client: TestClient, plan_pdf: bytes) -> None:
    pid = upload(client, plan_pdf)
    missing = client.post("/api/projects/nope/files", params={"name": "a.png"}, content=plan_png())
    assert missing.status_code == 404
    pdf = client.post(f"/api/projects/{pid}/files", params={"name": "b.pdf"}, content=plan_pdf)
    assert (pdf.status_code, pdf.json()["code"]) == (415, "unsupported")
    unnamed = client.post(f"/api/projects/{pid}/files", content=plan_png())
    assert unnamed.status_code == 422

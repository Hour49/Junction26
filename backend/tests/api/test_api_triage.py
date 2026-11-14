"""File triage in the API (decision 0010, board #152): `FileStatus.triage`, `not_plans`, a
person's relevance call (POST …/files/{file_id}/relevance) and the `unrelated_file` issues."""

import io
import zipfile
from typing import Any

import pytest
from conftest import plan_png
from fastapi.testclient import TestClient
from test_vector_pdf import swiss_sheet
from triage_fakes import FakeClassifier, FakeDescriber, WordJudge, steps

from app.adapters.archive import DiskProjectStore
from app.composition import build_ingest
from app.core.ingest.model import ProjectStatus
from app.main import create_app
from app.settings import Settings
from scripts.make_sample_archive import jpeg_bytes, png_bytes, raster_plan, site_photo

PLAN = swiss_sheet().pdf()  # room labels Küche, Bad, Balkon...
ELEVATION = png_bytes(raster_plan())  # judged related: "Küche" is printed on it
SCORE = png_bytes(raster_plan().rotate(90, expand=True))  # judged unrelated
PHOTO = jpeg_bytes(site_photo())  # not described: the fake model refuses it
DRAWING = plan_png()  # unsure: judged in a project with no plan


@pytest.fixture
def triaged(settings: Settings) -> TestClient:
    classifier = FakeClassifier(
        {
            ELEVATION: "other_drawing",
            SCORE: "other_drawing",
            PHOTO: "not_drawing",
            DRAWING: "other_drawing",
        }
    )
    describer = FakeDescriber(
        {
            ELEVATION: ("the south elevation", ("Küche",)),
            SCORE: ("a music score", ("Allegro",)),
            DRAWING: ("a section through a house", ()),
        }
    )
    found = steps(classifier, describer, WordJudge())
    ingest = build_ingest(settings, settings.projects_dir, background=False, triage=found)
    return TestClient(create_app(settings, ingest))


def zipped(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, data in files.items():
            archive.writestr(path, data)
    return buffer.getvalue()


def project(client: TestClient, files: dict[str, bytes]) -> dict[str, Any]:
    started = client.post("/api/projects", params={"name": "site.zip"}, content=zipped(files))
    assert started.status_code == 202, started.text
    return client.get(started.json()["url"]).json()


def site(client: TestClient) -> dict[str, Any]:
    files = {"plan.pdf": PLAN, "elevation.png": ELEVATION, "score.png": SCORE, "photo.jpg": PHOTO}
    return project(client, files)


def file_id(found: dict[str, Any], path: str) -> str:
    return next(file["id"] for file in found["files"] if file["path"] == path)


def issues(client: TestClient, project_id: str) -> list[dict[str, Any]]:
    reply = client.get(f"/api/projects/{project_id}/issues")
    assert reply.status_code == 200, reply.text
    return reply.json()["issues"]


def call(client: TestClient, found: dict[str, Any], path: str, body: dict[str, Any]) -> Any:
    url = f"/api/projects/{found['id']}/files/{file_id(found, path)}/relevance"
    return client.post(url, json=body)


def test_a_triaged_file_shows_its_class_description_verdict_and_the_project_counts_non_plans(
    triaged: TestClient,
) -> None:
    found = site(triaged)
    files = {file["path"]: file for file in found["files"]}
    elevation = files["elevation.png"]
    assert elevation["state"] == "set_aside"
    assert elevation["triage"]["class"] == "other_drawing"
    assert elevation["triage"]["verdict"] == "related"
    assert elevation["triage"]["relevance"]["plans"] == [files["plan.pdf"]["drawing_id"]]
    assert elevation["triage"]["note"] is None
    assert files["photo.jpg"]["triage"]["note"] == "not described: the model refused"
    assert "triage" not in files["plan.pdf"]  # a vector PDF is not triaged
    assert found["not_plans"] == 3
    (summary,) = triaged.get("/api/projects").json()["projects"]
    assert summary["not_plans"] == 3
    trace = triaged.get(f"/api/projects/{found['id']}/files/{elevation['id']}/trace").json()
    assert trace["file"]["triage"] == elevation["triage"]
    assert {stage["stage"] for stage in trace["stages"]} <= {"unpack", "hash", "identify"}  # no new


def test_each_non_plan_whose_verdict_is_not_related_is_one_issue_and_never_also_set_aside(
    triaged: TestClient,
) -> None:
    found = site(triaged)
    listed = issues(triaged, found["id"])
    kinds = {(issue["file"], issue["kind"]) for issue in listed if issue["file"] != "plan.pdf"}
    assert kinds == {("score.png", "unrelated_file"), ("photo.jpg", "unrelated_file")}
    score = next(issue for issue in listed if issue["file"] == "score.png")
    assert (score["severity"], score["state"], score["reason"]) == ("note", "open", "unrelated")
    assert score["why"] == (
        "Not a floor plan (another kind of drawing (an elevation, section, site plan, detail or "
        "cover): a music score). Unrelated: no word on it is on the project's plans or in its "
        "file names."
    )
    assert (score["page"], score["box"], score["drawing_id"]) == (None, None, None)
    photo = next(issue for issue in listed if issue["file"] == "photo.jpg")
    assert (photo["severity"], photo["reason"]) == ("note", None)
    assert photo["why"].endswith("Not described: the model refused.")


def test_an_unsure_file_needs_a_person_and_keeps_that_place_once_a_person_decides(
    triaged: TestClient,
) -> None:
    found = project(triaged, {"section.png": DRAWING, "score.png": SCORE})  # no plan: unsure
    first = issues(triaged, found["id"])
    assert [(issue["file"], issue["severity"], issue["reason"]) for issue in first] == [
        ("section.png", "needs_person", "unsure"), ("score.png", "needs_person", "unsure"),
    ]  # fmt: skip
    assert call(triaged, found, "section.png", {"verdict": "related", "by": "Ana"}).is_success
    after = issues(triaged, found["id"])
    assert [(issue["id"], issue["severity"]) for issue in after] == [
        (issue["id"], "needs_person") for issue in first
    ]
    assert [issue["state"] for issue in after] == ["settled", "open"]


def test_a_persons_call_settles_the_issue_in_place_and_undo_takes_it_back(
    triaged: TestClient,
) -> None:
    found = site(triaged)
    before = issues(triaged, found["id"])
    reply = call(triaged, found, "score.png", {"verdict": "related", "by": "Ana"})
    assert reply.status_code == 200, reply.text
    triage = reply.json()["triage"]
    assert (triage["verdict"], triage["relevance"]["verdict"]) == ("related", "unrelated")
    assert (triage["overruled"]["verdict"], triage["overruled"]["by"]) == ("related", "Ana")
    assert reply.json()["state"] == "set_aside"  # a call is no reading
    after = issues(triaged, found["id"])
    assert [issue["id"] for issue in after] == [issue["id"] for issue in before]
    score = next(issue for issue in after if issue["file"] == "score.png")
    assert (score["state"], score["reason"]) == ("settled", "related")
    assert score["why"].endswith("Ana says it is related.")
    (summary,) = triaged.get("/api/projects").json()["projects"]
    assert summary["issues_open"] == sum(issue["state"] == "open" for issue in after)
    reply = call(triaged, found, "score.png", {"undo": True})
    assert reply.status_code == 200 and reply.json()["triage"]["overruled"] is None
    assert issues(triaged, found["id"]) == before
    unchanged = call(triaged, found, "score.png", {"undo": True})  # nothing to take back
    assert unchanged.status_code == 200 and unchanged.json() == reply.json()


def test_confirming_unrelated_settles_and_a_related_file_called_related_has_no_issue_until_called(
    triaged: TestClient,
) -> None:
    found = site(triaged)
    assert "elevation.png" not in {issue["file"] for issue in issues(triaged, found["id"])}
    unrelated = {"verdict": "unrelated", "by": "Ana"}
    assert call(triaged, found, "score.png", unrelated).status_code == 200  # the judge's own
    score = next(issue for issue in issues(triaged, found["id"]) if issue["file"] == "score.png")
    assert score["state"] == "settled"
    assert call(triaged, found, "elevation.png", unrelated).status_code == 200
    elevation = [
        issue for issue in issues(triaged, found["id"]) if issue["file"] == "elevation.png"
    ]
    assert [(issue["state"], issue["reason"]) for issue in elevation] == [("settled", "unrelated")]


@pytest.mark.parametrize(
    "body",
    [
        {"verdict": "unsure", "by": "Ana"},
        {"verdict": "related", "by": ""},
        {"verdict": "related", "by": "x" * 101},
        {"verdict": "related"},
        {"undo": True, "verdict": "related"},
    ],
)
def test_a_body_outside_the_shape_is_a_validation_error(
    triaged: TestClient, body: dict[str, Any]
) -> None:
    reply = call(triaged, site(triaged), "score.png", body)
    assert (reply.status_code, reply.json()["code"]) == (422, "validation")


def test_a_file_with_no_description_has_its_own_code_and_unknown_or_unfinished_ones_the_usual(
    triaged: TestClient, settings: Settings
) -> None:
    found = site(triaged)
    reply = call(triaged, found, "photo.jpg", {"verdict": "related", "by": "Ana"})
    assert (reply.status_code, reply.json()["code"]) == (422, "no-description")
    plan = call(triaged, found, "plan.pdf", {"verdict": "related", "by": "Ana"})  # never triaged
    assert plan.json()["code"] == "no-description"
    url = f"/api/projects/{found['id']}/files/f99/relevance"
    reply = triaged.post(url, json={"verdict": "related", "by": "Ana"})
    assert (reply.status_code, reply.json()["code"]) == (404, "not-found")
    running = ProjectStatus(id="aaaaaaaaaaaa", name="r.zip", state="running", created_at="t")
    DiskProjectStore(settings.projects_dir).save_project(running, {})
    reply = triaged.post(
        "/api/projects/aaaaaaaaaaaa/files/f1/relevance", json={"verdict": "related", "by": "Ana"}
    )
    assert (reply.status_code, reply.json()["code"]) == (409, "not-allowed")


def test_with_triage_off_the_fields_are_left_out(client: TestClient) -> None:
    found = project(client, {"plan.pdf": PLAN, "elevation.png": ELEVATION})
    assert "not_plans" not in found
    assert all("triage" not in file for file in found["files"])
    (summary,) = client.get("/api/projects").json()["projects"]
    assert "not_plans" not in summary


def test_the_rules_classifier_triages_what_ingest_set_aside_anyway_at_no_cost(
    settings: Settings,
) -> None:
    """TRIAGE_CLASSIFIER=rules, no keys: the sample's site photo is triaged and not described;
    every drawing is read as with triage off."""
    ruled = settings.model_copy(update={"triage_classifier": "rules"})
    client = TestClient(
        create_app(ruled, build_ingest(ruled, ruled.projects_dir, background=False))
    )
    found = client.get(client.post("/api/projects/sample").json()["url"]).json()
    files = {file["path"]: file for file in found["files"]}
    photo = files["photos/site.jpg"]
    assert (photo["state"], photo["triage"]["class"], photo["triage"]["verdict"]) == (
        "set_aside", "not_drawing", None,
    )  # fmt: skip
    assert (
        photo["triage"]["note"]
        == "not described: no description model is set up, so it is not judged"
    )
    assert files["scans/ground-floor.png"]["triage"]["class"] == "floor_plan"
    assert files["scans/ground-floor.png"]["drawing_id"] is not None
    assert (found["not_plans"], found["cost_usd"], found["readers"]["triage"]) == (
        1, 0.0, "classifier=rules, describer=off, judge=off",
    )  # fmt: skip
    (issue,) = [
        issue for issue in issues(client, found["id"]) if issue["file"] == "photos/site.jpg"
    ]
    assert (issue["kind"], issue["severity"], issue["reason"]) == ("unrelated_file", "note", None)

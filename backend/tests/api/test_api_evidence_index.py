"""The evidence index over REST (decision 0012): GET /api/projects/{project_id}/evidence/search and
/evidence/{evidence_id}, on a project whose non-plans fake triage described, as ingest keeps the
index in step (judging, a person's relevance call, read as a plan)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from test_api_triage import (
    DRAWING,
    ELEVATION,
    PHOTO,
    SCORE,
    call,
    file_id,
    read_as_plan,
    site,
)
from triage_fakes import FakeClassifier, FakeDescriber, WordJudge, steps

from app.composition import build_ingest
from app.main import create_app
from app.settings import Settings


@pytest.fixture
def described(settings: Settings) -> TestClient:
    classifier = FakeClassifier(
        {
            ELEVATION: "other_drawing",
            SCORE: "other_drawing",
            PHOTO: "not_drawing",
            DRAWING: "other_drawing",
        }
    )
    describer = FakeDescriber(
        {ELEVATION: ("the south elevation", ("Küche",)), SCORE: ("a music score", ("Allegro",))}
    )
    found = steps(classifier, describer, WordJudge())
    ingest = build_ingest(settings, settings.projects_dir, background=False, triage=found)
    return TestClient(create_app(settings, ingest))


def search(client: TestClient, project_id: str, **params: Any) -> dict[str, Any]:
    reply = client.get(f"/api/projects/{project_id}/evidence/search", params=params)
    assert reply.status_code == 200, reply.text
    return reply.json()


def test_search_finds_a_described_non_plan_by_what_it_shows_and_what_is_printed(
    described: TestClient,
) -> None:
    found = site(described)
    elevation = file_id(found, "elevation.png")
    reply = search(described, found["id"], q="south elevation")
    assert reply["method"] == "BM25 (no embedder model on this machine)"
    assert (reply["indexed_files"], reply["unrelated_left_out"], reply["note"]) == (2, 1, None)
    (hit,) = reply["hits"]
    assert (hit["file_id"], hit["file"], hit["verdict"]) == (elevation, "elevation.png", "related")
    assert set(hit) == {
        "id", "file_id", "file", "page", "part", "how", "kind", "subject", "snippet",
        "language", "verdict", "credit", "score", "why",
    }  # fmt: skip
    assert hit["how"] == "described"
    printed = search(described, found["id"], q="Kuche")  # diacritics folded
    assert [hit["id"] for hit in printed["hits"]] == [f"{elevation}-visible_text-1"]


def test_unrelated_files_are_searched_only_when_asked(described: TestClient) -> None:
    found = site(described)
    assert search(described, found["id"], q="music score")["hits"] == []
    asked = search(described, found["id"], q="music score", include_unrelated="true")
    assert [hit["file"] for hit in asked["hits"]] == ["score.png"]
    assert asked["unrelated_left_out"] == 0


def test_get_answers_a_passage_or_a_file_with_its_description(described: TestClient) -> None:
    found = site(described)
    elevation = file_id(found, "elevation.png")
    reply = described.get(f"/api/projects/{found['id']}/evidence/{elevation}")
    assert reply.status_code == 200, reply.text
    body = reply.json()
    assert body["id"] == f"{elevation}-summary"
    assert body["description"]["subject"] == "the south elevation"
    assert body["relevance"]["verdict"] == "related" and "register" in body
    detail = described.get(f"/api/projects/{found['id']}/evidence/{elevation}-detail-1").json()
    assert detail["text"] == "A longer account of the south elevation, for later use."
    score = file_id(found, "score.png")
    unrelated = described.get(f"/api/projects/{found['id']}/evidence/{score}")
    assert unrelated.status_code == 200 and unrelated.json()["verdict"] == "unrelated"


def test_a_persons_relevance_call_and_read_as_plan_change_what_search_finds(
    described: TestClient,
) -> None:
    found = site(described)
    reply = call(described, found, "score.png", {"verdict": "related", "by": "Ana"})
    assert reply.status_code == 200, reply.text
    assert [hit["file"] for hit in search(described, found["id"], q="score")["hits"]] == [
        "score.png"
    ]
    assert read_as_plan(described, found, "elevation.png").status_code == 202
    after = search(described, found["id"], q="south elevation")
    assert after["hits"] == [] and after["indexed_files"] == 1


@pytest.mark.parametrize(
    "params",
    [{}, {"q": ""}, {"q": "   "}, {"q": "x", "k": 0}, {"q": "x", "k": 21}, {"q": "x" * 501}],
)
def test_a_bad_search_is_422_validation(described: TestClient, params: dict[str, Any]) -> None:
    found = site(described)
    reply = described.get(f"/api/projects/{found['id']}/evidence/search", params=params)
    assert reply.status_code == 422, reply.text
    assert reply.json()["code"] == "validation"


def test_unknown_projects_and_ids_are_404_not_found(described: TestClient) -> None:
    found = site(described)
    for url in [
        "/api/projects/aaaaaaaaaaaa/evidence/search?q=x",
        "/api/projects/aaaaaaaaaaaa/evidence/f1",
        f"/api/projects/{found['id']}/evidence/f99",
        f"/api/projects/{found['id']}/evidence/not-an-id",
        f"/api/projects/{found['id']}/evidence/{file_id(found, 'plan.pdf')}",  # a plan: not in it
    ]:
        reply = described.get(url)
        assert (reply.status_code, reply.json()["code"]) == (404, "not-found"), url


def test_a_project_without_descriptions_has_an_empty_index_and_says_why(
    client: TestClient, plan_pdf: bytes
) -> None:
    started = client.post("/api/projects", params={"name": "plan.pdf"}, content=plan_pdf)
    reply = search(client, started.json()["id"], q="anything")
    assert (reply["indexed_files"], reply["hits"]) == (0, [])
    assert reply["note"].startswith("No file of this project is in the evidence index")

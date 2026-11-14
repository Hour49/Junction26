"""The building-law API (decision 0011, docs/API.md "Building law") on the made-up laws of
tests/fixtures/laws."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings

LAWS = Path(__file__).parents[1] / "fixtures" / "laws"


class _NoIngest:
    def close(self) -> None:
        pass


@pytest.fixture
def laws(settings: Settings) -> TestClient:
    configured = settings.model_copy(update={"laws_dir": LAWS})
    return TestClient(create_app(configured, _NoIngest()))  # pyright: ignore[reportArgumentType]


def test_the_packs_and_their_laws(laws: TestClient) -> None:
    body = laws.get("/api/laws").json()
    assert [pack["id"] for pack in body["packs"]] == ["fi", "ch-zh"]
    assert body["packs"][0]["laws"] == [
        {
            "law_id": "fi-test-1",
            "number": "1/2026",
            "title_en": "Test decree on residential spaces",
            "clauses": 2,
            "topics": ["rooms", "fire", "escape-routes"],
        }
    ]


def test_search(laws: TestClient) -> None:
    reply = laws.get("/api/laws/ch-zh/search", params={"q": "Fluchtweg"})
    assert reply.status_code == 200, reply.text
    body = reply.json()
    assert (body["pack"], body["query"]) == ("ch-zh", "Fluchtweg")
    (hit,) = body["hits"]
    assert set(hit) == {"id", "law_id", "ref", "title_en", "summary_en", "url", "score"}
    assert hit["id"] == "ch-zh-test-1-12-1"


def test_search_by_topic_and_limit(laws: TestClient) -> None:
    hits = laws.get("/api/laws/fi/search", params={"q": "room exit", "topic": "fire"}).json()
    assert [hit["id"] for hit in hits["hits"]] == ["fi-test-1-9-1"]
    one = laws.get("/api/laws/fi/search", params={"q": "room exit", "limit": 1}).json()
    assert len(one["hits"]) == 1


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"q": ""},
        {"q": "x" * 501},
        {"q": "room", "limit": 0},
        {"q": "room", "limit": 21},
        {"q": "room", "topic": "tax"},
    ],
)
def test_a_bad_search_is_a_validation_error(laws: TestClient, params: dict[str, str | int]) -> None:
    reply = laws.get("/api/laws/fi/search", params=params)
    assert (reply.status_code, reply.json()["code"]) == (422, "validation")


def test_an_unknown_pack_is_404_unknown_pack(laws: TestClient) -> None:
    reply = laws.get("/api/laws/xx/search", params={"q": "room"})
    assert (reply.status_code, reply.json()) == (
        404,
        {"detail": "no law pack 'xx'", "code": "unknown-pack"},
    )


def test_a_clause(laws: TestClient) -> None:
    body = laws.get("/api/laws/clauses/fi-test-1-4-2").json()
    assert body["text"] == "Asuintilan huonealan on oltava vähintään 7 neliömetriä."
    assert (body["law_id"], body["url"], body["language"]) == (
        "fi-test-1",
        "https://www.finlex.fi/fi/lainsaadanto/2026/1",
        "fi",
    )
    assert body["limits"] == [
        {"what": "habitable room area", "comparison": ">=", "value": 7.0, "unit": "m2"}
    ]


def test_an_unknown_clause_is_404(laws: TestClient) -> None:
    reply = laws.get("/api/laws/clauses/fi-none")
    assert (reply.status_code, reply.json()["code"]) == (404, "not-found")

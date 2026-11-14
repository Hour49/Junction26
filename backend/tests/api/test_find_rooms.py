"""Refusal recovery (phase 2 item 6): when ask_drawings can't parse a question that names a room
("the office"), find_rooms looks the words up in the room labels the drawings print, so the
agent offers those rooms instead of a dead end. Labels only: never a room the drawing lacks."""

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from swiss_walls import walled_flat
from test_agent_loop import Tools

from app.adapters.agent_tools import project_toolbox
from app.adapters.chat_rules import RulesChatModel
from app.composition import build_ingest
from app.core.agent.loop import run_turn
from app.core.agent.model import Caps, Chat
from app.core.spend import SpendGuard
from app.main import create_app
from app.settings import Settings

DRAWING = "0123456789abcdef"
NOT_WHICH = "I can see what this asks to measure, but not which room or element it is about."
REFUSED: dict[str, Any] = {
    "question": "What is the area of the office?",
    "parts": [{"drawing_id": DRAWING, "name": "plan.png", "answer": {
        "answer": None, "refusal": {"code": "unsupported-question", "text": NOT_WHICH,
                                    "can_answer": []}}}],
}  # fmt: skip


def office(label: str, x: float) -> dict[str, Any]:
    return {"room": f"r{x}", "label": label, "drawing_id": DRAWING, "name": "plan.png",
            "page": 1, "box": [x, 0.1, x + 0.1, 0.2]}  # fmt: skip


OFFICES = {"status": "ok", "count": 3,
           "rooms": [office("OPEN OFFICE 102", 0.1), office("OFFICE 103", 0.3),
                     office("OFFICE 107", 0.5)]}  # fmt: skip


def rules_turn(message: str, **results: Any) -> Any:
    tools = Tools(**results)
    turn = run_turn(Chat("c3f9a1b2c4d5"), message, (), RulesChatModel(), tools, Caps(),
                    SpendGuard())  # fmt: skip
    return turn, tools


def test_rules_offers_the_printed_rooms_when_the_question_is_refused() -> None:
    got, tools = rules_turn("What is the area of the office?", ask_drawings=REFUSED,
                            find_rooms=OFFICES)  # fmt: skip
    assert [name for name, _ in tools.ran] == ["ask_drawings", "find_rooms"]
    assert json.loads(tools.ran[1][1]) == {"query": "office"}
    assert got.kind == "needs_input"
    assert got.text.startswith("The drawings print 3 rooms with that name")
    assert got.options is not None
    assert [(o.label, o.message) for o in got.options] == [
        ("OPEN OFFICE 102", "Where is OPEN OFFICE 102?"),
        ("OFFICE 103", "Where is OFFICE 103?"),
        ("OFFICE 107", "Where is OFFICE 107?"),
    ]
    assert [e.label for e in got.evidence] == ["OPEN OFFICE 102", "OFFICE 103", "OFFICE 107"]


def test_rules_shows_the_one_printed_room_a_chip_names() -> None:
    one = {"status": "ok", "count": 1, "rooms": [office("OPEN OFFICE 102", 0.1)]}
    got, tools = rules_turn("Where is OPEN OFFICE 102?", ask_drawings=REFUSED, find_rooms=one)
    assert json.loads(tools.ran[1][1]) == {"query": "open office 102"}
    assert got.kind == "answer" and "OPEN OFFICE 102 is printed here [1]" in got.text
    assert got.view is not None and got.view.marks[0].box == (0.1, 0.1, 0.2, 0.2)


def test_rules_looks_rooms_up_only_when_the_question_lacks_its_room() -> None:
    other = json.loads(json.dumps(REFUSED))
    other["parts"][0]["answer"]["refusal"]["text"] = "This question isn't one I can count."
    got, tools = rules_turn("What is the fire rating of the doors?", ask_drawings=other,
                            find_rooms=OFFICES)  # fmt: skip
    assert [name for name, _ in tools.ran] == ["ask_drawings"] and got.kind == "dont_know"


def test_rules_keeps_the_refusal_when_no_printed_room_matches() -> None:
    none = {"status": "unknown", "reason": "no room label printed on the drawings holds office"}
    got, _ = rules_turn("What is the area of the office?", ask_drawings=REFUSED, find_rooms=none)
    assert got.kind == "dont_know"


@pytest.fixture
def client(settings: Settings) -> TestClient:
    return TestClient(
        create_app(settings, build_ingest(settings, settings.projects_dir, background=False))
    )


def find(client: TestClient, query: str) -> Any:
    project = client.post("/api/projects", params={"name": "flat.pdf"},
                          content=walled_flat()).json()["id"]  # fmt: skip
    return json.loads(project_toolbox(client.app, project, [], {}).run(
        "find_rooms", json.dumps({"query": query})))  # fmt: skip


def test_find_rooms_matches_every_word_of_the_printed_label(client: TestClient) -> None:
    found = find(client, "stanza")
    assert found["status"] == "ok" and found["count"] == 1
    [room] = found["rooms"]
    assert room["label"] == "Stanza 1.02" and room["page"] == 1 and len(room["box"]) == 4
    assert [r["label"] for r in find(client, "the 1.01")["rooms"]] == ["Bagno 1.01"]
    assert find(client, "office")["status"] == "unknown"
    assert "error" in find(client, "the room")

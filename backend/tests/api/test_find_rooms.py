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


def test_review_360_s3_a_room_holds_every_word_not_just_one(client: TestClient) -> None:
    """The flat prints Bagno 1.01 and Stanza 1.02: any one word of 'stanza 1.01' would offer
    both rooms."""
    assert find(client, "stanza 1.01")["status"] == "unknown"
    assert [r["label"] for r in find(client, "stanza 1.02")["rooms"]] == ["Stanza 1.02"]


def test_review_360_s1_offered_rooms_are_only_the_ones_find_rooms_returned() -> None:
    """Gemini mode: the server drops a chip for a room find_rooms did not return."""
    from test_agent_loop import Model, call, final, step

    made_up = [{"label": "OPEN OFFICE 102", "message": "Where is OPEN OFFICE 102?"},
               {"label": "CEO OFFICE", "message": "Where is the CEO office?"},
               {"label": "OFFICE 103", "message": "Where is OFFICE 103?"}]  # fmt: skip
    model = Model(
        step(call("ask_drawings", question="What is the area of the office?")),
        step(call("find_rooms", 2, query="office")),
        final(kind="needs_input", text="Which office?", options=made_up),
    )
    tools = Tools(ask_drawings=REFUSED, find_rooms=OFFICES)
    got = run_turn(Chat("c3f9a1b2c4d5"), "What is the area of the office?", (), model, tools,
                   Caps(), SpendGuard())  # fmt: skip
    assert got.kind == "needs_input" and got.options is not None
    assert [o.label for o in got.options] == ["OPEN OFFICE 102", "OFFICE 103"]


def test_review_360_s1_too_few_printed_rooms_left_asks_the_model_again() -> None:
    from test_agent_loop import Model, call, final, step

    made_up = [{"label": "OPEN OFFICE 102", "message": "Where is OPEN OFFICE 102?"},
               {"label": "CEO OFFICE", "message": "Where is the CEO office?"}]  # fmt: skip
    fixed = [{"label": "OPEN OFFICE 102", "message": "Where is OPEN OFFICE 102?"},
             {"label": "OFFICE 107", "message": "Where is OFFICE 107?"}]  # fmt: skip
    model = Model(
        step(call("ask_drawings", question="What is the area of the office?")),
        step(call("find_rooms", 2, query="office")),
        final(kind="needs_input", text="Which office?", options=made_up),
        final(kind="needs_input", text="Which office?", options=fixed),
    )
    tools = Tools(ask_drawings=REFUSED, find_rooms=OFFICES)
    got = run_turn(Chat("c3f9a1b2c4d5"), "What is the area of the office?", (), model, tools,
                   Caps(), SpendGuard())  # fmt: skip
    assert "CEO OFFICE" in model.sent[3][-1]["content"]  # the retry says which one
    assert got.options is not None and [o.label for o in got.options] == [
        "OPEN OFFICE 102", "OFFICE 107"]  # fmt: skip


def test_review_360_n1_units_and_a_floor_are_no_label_words() -> None:
    from app.core.agent.rooms import name_words

    assert name_words("How big is office 102 in m2?") == ["office", "102"]
    assert name_words("How big is the kitchen in sqm?") == ["kitchen"]
    assert name_words("open-plan office on level 2?") == ["open", "office"]


def test_review_360_n3_more_rooms_than_chips_says_so() -> None:
    many = {**OFFICES, "count": 15}
    got, _ = rules_turn("What is the area of the office?", ask_drawings=REFUSED, find_rooms=many)
    assert got.text.startswith("The drawings print 15 rooms with that name; here are 3:")


def test_r4_a14_find_rooms_says_it_lists_only_the_rooms_a_reader_found(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """eu-big live T1 (05:22): the chat said "There are 2 rooms labeled Secondary Classroom" for
    8 classrooms. find_rooms lists the labels a reader found; the result says so, with how many
    rooms were read and how many of those carry no printed label."""
    project = client.post("/api/projects", params={"name": "flat.pdf"},
                          content=walled_flat()).json()["id"]  # fmt: skip
    app: Any = client.app
    ingest = app.state.ingest
    [entry] = client.get(f"/api/projects/{project}").json()["drawings"]
    rooms = ingest.drawing(entry["drawing_id"]).rooms
    toolbox = project_toolbox(client.app, project, [], {})
    for query, status in (("stanza", "ok"), ("office", "unknown")):
        found = json.loads(toolbox.run("find_rooms", json.dumps({"query": query})))
        assert found["status"] == status
        assert found["rooms_read"] == len(rooms) > 0
        assert found["unlabelled"] == sum(not room.label for room in rooms)
        assert found["counts"] == (
            "only the rooms a reader found on the drawings and read a label for: rooms it "
            "missed, or found without a label, are not in it, so this is no count of them all"
        )
    read = ingest.drawing  # a room read without a label is counted as unlabelled

    def blank(drawing_id: str) -> Any:
        drawing = read(drawing_id)
        last = drawing.rooms[-1].model_copy(update={"label": None})
        return drawing.model_copy(update={"rooms": (*drawing.rooms[:-1], last)})

    monkeypatch.setattr(ingest, "drawing", blank)
    found = json.loads(toolbox.run("find_rooms", json.dumps({"query": "stanza"})))
    assert (found["rooms_read"], found["unlabelled"]) == (
        len(rooms),
        1 + sum(not r.label for r in rooms),
    )

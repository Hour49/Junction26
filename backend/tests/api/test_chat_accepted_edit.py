"""R4-F5 (Tudor, #14 c6888351556): answers read the drawing as drawn, so after an accepted plan
edit a room's area is still its drawn one. The turn says so, and gives the room's area with the
edit, instead of reading as if the edit was lost. CHAT_MODEL=rules, no keys."""

from typing import Any

from conftest import upload
from fastapi.testclient import TestClient
from swiss_walls import walled_flat

from app.core.agent.accepted_edits import with_accepted_edits
from app.core.agent.model import ChatTurn
from app.core.plan_edit.model import Item, Proposal

REMOVE = "Remove the wall between Bagno 1.01 and Stanza 1.02"
AREA = "What is the area of Bagno 1.01?"


def edited(client: TestClient, decision: str | None) -> tuple[str, str]:
    project = upload(client, walled_flat(), "flat.pdf")
    chat = f"/api/projects/{project}/chat"
    turn = client.post(chat, json={"message": REMOVE}).json()
    assert turn["kind"] == "edit", turn["text"]
    if decision:
        decided = client.post(f"{chat}/{turn['chat_id']}/proposals/p1", json={"action": decision})
        assert decided.status_code == 200, decided.text
    return chat, turn["chat_id"]


def ask(client: TestClient, chat: str, chat_id: str, message: str) -> dict[str, Any]:
    response = client.post(chat, json={"message": message, "chat_id": chat_id})
    assert response.status_code == 200, response.text
    return response.json()


def test_r4_f5_an_area_after_an_accepted_edit_says_as_drawn_and_with_the_edit(
    client: TestClient,
) -> None:
    chat, chat_id = edited(client, "accept")
    turn = ask(client, chat, chat_id, AREA)
    assert turn["kind"] == "answer"
    assert "9 m²" in turn["text"]  # the drawing's own answer stays: it is what the drawing says
    assert (
        "As drawn; the plan edit you accepted (Bagno 1.01 + Stanza 1.02) isn't applied to answers; "
        "with it, Bagno 1.01 is part of Bagno 1.01 + Stanza 1.02: 21.02 m²."
    ) in turn["text"]
    # kept with the chat: the turn reads the same when the chat is opened again
    project = chat.split("/")[3]
    app: Any = client.app
    stored = app.state.chats.get(project, chat_id)
    assert stored.turns[-1].text == turn["text"]


def test_r4_f5_no_note_for_an_edit_only_proposed_or_rejected(client: TestClient) -> None:
    for decision in (None, "reject"):
        chat, chat_id = edited(client, decision)
        turn = ask(client, chat, chat_id, AREA)
        assert "plan edit you accepted" not in turn["text"], decision


def test_r4_f5_the_number_of_rooms_on_the_edited_drawing_says_as_drawn(
    client: TestClient,
) -> None:
    chat, chat_id = edited(client, "accept")
    turn = ask(client, chat, chat_id, "How many rooms are there?")
    assert turn["kind"] == "answer", turn["text"]
    assert turn["text"].endswith(
        "As drawn; the plan edit you accepted (Bagno 1.01 + Stanza 1.02) isn't applied to answers."
    )


def test_r4_f5_a_total_gives_the_total_with_the_edit_once(client: TestClient) -> None:
    """qa-c on #629: a total listed the merged room once per room it merged, which reads as
    addable. The total with the edit, once."""
    chat, chat_id = edited(client, "accept")
    turn = ask(client, chat, chat_id, "What is the total floor area?")
    assert turn["kind"] == "answer", turn["text"]
    assert turn["text"].endswith(
        "As drawn; the plan edit you accepted (Bagno 1.01 + Stanza 1.02) isn't applied to answers; "
        "with it, the total is 21.02 m² (Bagno 1.01 + Stanza 1.02: 21.02 m²)."
    )


def test_r4_f5_the_area_of_a_room_the_edit_does_not_change_gets_no_note(
    client: TestClient,
) -> None:
    chat, chat_id = edited(client, "accept")
    turn = ask(client, chat, chat_id, "What is the area of Balcone 1.03?")
    assert turn["kind"] == "answer", turn["text"]
    assert "plan edit you accepted" not in turn["text"]


def test_r4_f5_a_door_count_on_the_edited_drawing_gets_no_note(client: TestClient) -> None:
    """Orchestrator 05:19: only a quantity the edit can change (rooms, walls) carries it, so a
    later answer about doors, windows or fixtures reads as before."""
    chat, chat_id = edited(client, "accept")
    turn = ask(client, chat, chat_id, "How many doors are there?")
    assert turn["kind"] == "answer", turn["text"]
    assert "plan edit you accepted" not in turn["text"]


def test_r4_f5_a_wall_quantity_on_the_edited_drawing_says_as_drawn() -> None:
    """The walls the edit removes change any wall count or length on its drawing. This sheet's
    reader gives none, so the turn is made by hand; a door count beside it gets nothing."""
    proposal = Proposal(
        proposal_id="p1",
        drawing_id="d1",
        page=1,
        state="accepted",
        removed=(Item(id="W1", polygon=((0, 0), (1, 0), (1, 1)), label="Wall W1"),),
    )

    def part(subject: str, measure: str) -> dict[str, Any]:
        quantity = {"measure": measure, "subject": subject, "value": 4, "marks": []}
        return {"drawing_id": "d1", "answer": {"quantity": quantity}}

    def turn(*parts: dict[str, Any]) -> ChatTurn:
        return ChatTurn(chat_id="c", turn=2, kind="answer", text="Drawn plan 1: 4.",
                        model="rules", cost_usd=0.0, latency_s=0.0,
                        answers=({"parts": list(parts)},))  # fmt: skip

    for measure in ("count", "length"):
        noted = with_accepted_edits(turn(part("wall", measure)), {"p1": proposal})
        assert noted.text == (
            "Drawn plan 1: 4. As drawn; the plan edit you accepted (Wall W1) isn't applied to "
            "answers."
        ), measure
    doors = turn(part("door", "count"))
    assert with_accepted_edits(doors, {"p1": proposal}) == doors

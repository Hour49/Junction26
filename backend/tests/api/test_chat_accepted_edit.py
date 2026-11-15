"""R4-F5 (Tudor, #14 c6888351556): answers read the drawing as drawn, so after an accepted plan
edit a room's area is still its drawn one. The turn says so, and gives the room's area with the
edit, instead of reading as if the edit was lost. CHAT_MODEL=rules, no keys."""

from typing import Any

from conftest import upload
from fastapi.testclient import TestClient
from swiss_walls import walled_flat

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
        "As drawn. Your accepted edit p1 is not applied to answers; with it, Bagno 1.01 is part of "
        "Bagno 1.01 + Stanza 1.02: 21.02 m²."
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
        assert "accepted edit" not in turn["text"], decision


def test_r4_f5_another_answer_on_the_edited_drawing_says_it_reads_it_as_drawn(
    client: TestClient,
) -> None:
    chat, chat_id = edited(client, "accept")
    turn = ask(client, chat, chat_id, "How many doors are there?")
    assert "As drawn. Your accepted edit p1 is not applied to answers." in turn["text"]

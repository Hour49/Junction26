"""Big QA R1 edits S1 (2026-11-15): "What is the area of Bagno 1.01?" was asked as room 1.01 on
every drawing (the name word dropped), so the sample's flat-a Küche 1.01 (22.40 m²) and flat-b's
room 1.01 answered too, and the card led with Küche. A room named with its name and its number is
only the room that carries both; a drawing whose room of that number has another name refuses."""

from typing import Any

from fastapi.testclient import TestClient


def asked(client: TestClient, question: str) -> dict[str, dict[str, Any]]:
    project = client.get(client.post("/api/projects/sample").json()["url"]).json()
    reply = client.post(f"/api/projects/{project['id']}/ask", json={"question": question})
    assert reply.status_code == 200, reply.text
    return {part["name"]: part["answer"] for part in reply.json()["parts"]}


def test_a_room_asked_by_name_and_number_is_only_the_room_with_both(client: TestClient) -> None:
    parts = asked(client, "What is the area of Bagno 1.01?")
    assert parts["plans/flat-c.pdf"]["answer"] == 9.0
    for other in ("plans/flat-a.pdf", "plans/flat-b.pdf"):  # their room 1.01 is not Bagno
        assert parts[other]["answer"] is None, (other, parts[other])
        refusal = parts[other]["refusal"]
        assert refusal["code"] == "not-in-drawing", refusal
        assert "Bagno" in refusal["text"] and "1.01" in refusal["text"], refusal


def test_a_room_asked_by_its_number_alone_is_every_drawing_s_room_of_that_number(
    client: TestClient,
) -> None:
    parts = asked(client, "What is the area of room 1.01?")
    answered = {name for name, answer in parts.items() if answer["answer"] is not None}
    assert {"plans/flat-a.pdf", "plans/flat-b.pdf", "plans/flat-c.pdf"} <= answered


def test_a_type_word_and_a_number_is_the_room_of_that_type_with_that_number(
    client: TestClient,
) -> None:
    """ "bathroom 1.01" names the room by its type: flat-c's Bagno (a bathroom) answers, flat-a's
    Küche 1.01 (a kitchen) does not; a count in the room is checked the same way."""
    parts = asked(client, "What is the area of bathroom 1.01?")
    assert parts["plans/flat-c.pdf"]["answer"] == 9.0, parts["plans/flat-c.pdf"]
    assert parts["plans/flat-a.pdf"]["answer"] is None
    doors = asked(client, "How many doors does Bagno 1.01 have?")
    assert doors["plans/flat-a.pdf"]["refusal"]["code"] == "not-in-drawing"
    assert doors["plans/flat-c.pdf"]["answer"] is not None, doors["plans/flat-c.pdf"]


def test_a_room_word_in_any_language_before_the_number_is_not_a_name(client: TestClient) -> None:
    """Golden v2: "Nettofläche von Raum 5.04 («Wohnen»)", "la pièce 4.23": "Raum" and "pièce" are
    the word room, not the room's name, so the number alone names the room, as before."""
    for question in (
        "Wie gross ist die Nettofläche von Raum 1.01 in m²?",
        "Quelle est la surface nette de la pièce 1.01 en m² ?",
    ):
        parts = asked(client, question)
        assert parts["plans/flat-a.pdf"]["answer"] is not None, (
            question,
            parts["plans/flat-a.pdf"],
        )

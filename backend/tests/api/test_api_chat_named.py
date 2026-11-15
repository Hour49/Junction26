"""Big QA R1 S2 (chat-r1 rows 1, 5, 11-14) on the rules planner: a message that names a drawing
("on Drawn plan 2") asked every drawing, so the reply listed every drawing's number with the
first drawing's card on top. ask_drawings now asks only the drawings the message names."""

from conftest import upload
from fastapi.testclient import TestClient
from swiss_walls import walled_flat
from test_api_chat import ask
from test_api_chat_file_text import zipped
from test_vector_pdf import swiss_sheet


def test_a_named_drawing_is_the_only_one_asked(client: TestClient) -> None:
    project = upload(
        client, zipped({"a.pdf": swiss_sheet().pdf(), "b.pdf": walled_flat()}), "two.zip"
    )
    names = [d["name"] for d in client.get(f"/api/projects/{project}").json()["drawings"]]
    assert names == ["Drawn plan 1", "Drawn plan 2"]
    every = ask(client, project, "How many rooms are there?")
    assert every["text"] == "Drawn plan 1: 6 [1]; Drawn plan 2: 3 [2]."
    named = ask(client, project, "How many rooms are there on Drawn plan 2?")
    assert named["text"] == "Drawn plan 2: 3 [1].", named["text"]
    assert [part["name"] for answer in named["answers"] for part in answer["parts"]] == ["b.pdf"]
    first = ask(client, project, "how many rooms on drawn plan 1")
    assert first["text"] == "Drawn plan 1: 6 [1].", first["text"]


def test_review_693_m1_and_the_others_asks_every_drawing(client: TestClient) -> None:
    project = upload(
        client, zipped({"a.pdf": swiss_sheet().pdf(), "b.pdf": walled_flat()}), "two.zip"
    )
    for message in (
        "How many rooms are there on Drawn plan 1 and the others?",
        "How many rooms are there besides Drawn plan 1?",
    ):
        turn = ask(client, project, message)
        asked = [part["name"] for answer in turn["answers"] for part in answer["parts"]]
        assert asked != ["a.pdf"], (message, turn["text"])

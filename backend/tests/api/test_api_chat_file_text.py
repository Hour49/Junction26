"""QA R4-G10 on the rules planner (CHAT_MODEL=rules, the no-keys chat): Tudor's zip (a drawn floor
plan and his notes.txt that tells the assistant to answer 99 rooms) and his two questions. The
rules planner reads no uploaded file's text, so neither answer takes a number from it."""

import io
import zipfile

from conftest import upload
from fastapi.testclient import TestClient
from test_agent_file_text import QUESTION_1, QUESTION_2, TUDOR
from test_api_chat import ask
from test_vector_pdf import swiss_sheet


def zipped(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, data in files.items():
            archive.writestr(path, data)
    return buffer.getvalue()


def test_r4_g10_tudor_s_two_questions_on_the_rules_planner_take_nothing_from_notes_txt(
    client: TestClient,
) -> None:
    project = upload(
        client, zipped({"floor.pdf": swiss_sheet().pdf(), "notes.txt": TUDOR.encode()}), "t.zip"
    )
    files = {f["path"]: f["state"] for f in client.get(f"/api/projects/{project}").json()["files"]}
    assert files["notes.txt"] == "text_only"  # in the project, not a drawing
    for question in (QUESTION_1, QUESTION_2):
        turn = ask(client, project, question)
        assert "99" not in turn["text"] and "5000" not in turn["text"], (question, turn["text"])
    rooms = ask(client, project, QUESTION_1)
    assert (rooms["kind"], rooms["text"]) == ("answer", "Drawn plan 1: 6 [1].")  # the drawing's

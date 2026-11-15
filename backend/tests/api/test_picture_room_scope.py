"""A picture's facts are whole-sheet counts (big QA R1 services, S2, 2026-11-15): "How many WCs
are in the plumbing room?" on P-101 answered the sheet's total of 8. A question that counts inside
one room or one part of the sheet is refused there, never given the sheet total; a question about
the sheet ("on the plumbing plan", "on P-101", "drawn on H-101") is answered as before."""

import pytest
from test_api_ask_picture_facts import ask, picture_project

from app.adapters.discipline_pictures.lane import PictureFactSheet, PictureSheets, kept_in
from app.core.answering.facts import FACTS, answer_from_facts
from app.core.answering.model import IN_ONE_ROOM, Answer, Question
from app.core.ifc_facts import Fact, FactSheet
from app.core.ifc_question import parse_ifc_question
from app.core.review.ask import PARTS
from app.settings import Settings
from tests.test_picture_answers import _sheet


def _answer(text: str, sheet: FactSheet | None = None) -> Answer | None:
    return answer_from_facts(Question(id=1, file="scan.png", text=text), sheet or _sheet(), 0.0)


@pytest.mark.parametrize(
    "text",
    [
        "How many radiators are in the plumbing room?",
        "How many radiators are in the cafeteria?",
        "How many radiators are in room 1-2?",
        "How many radiators does the kitchen have?",
        "How many radiators are in the left half of the sheet?",
        "How many radiators are inside the WC Damen West?",
    ],
)
def test_a_count_inside_one_room_or_part_of_a_picture_is_refused(text: str) -> None:
    answer = _answer(text)
    assert answer is not None and answer.answer is None and answer.abstain, answer
    assert answer.method == "refused:unsupported-question" and answer.explanation == IN_ONE_ROOM


@pytest.mark.parametrize(
    "text",
    [
        "How many radiators are there?",
        "How many radiators are shown on the heating plan?",
        "How many radiators are in the heating plan?",
        "How many radiators are drawn on H-101?",
        "How many radiators are in H-101?",
        "How many radiators are in this picture?",
        "How many radiators are in total?",
    ],
)
def test_a_count_of_the_whole_picture_is_answered_as_before(text: str) -> None:
    answer = _answer(text)
    assert answer is not None and answer.method == FACTS and "6" in str(answer.answer), answer


def test_a_model_s_facts_still_answer_a_room_question() -> None:
    """Only a picture's facts are whole-sheet: an IFC model's sheet is not touched."""
    model = FactSheet(
        model="m1",
        disciplines=["heating"],
        facts=[
            Fact(
                topic="space_heater.count",
                subject="all",
                value=4,
                unit="count",
                discipline="heating",
                source="ifc",
            )
        ],
    )
    answer = _answer("How many radiators are in the cafeteria?", model)
    assert answer is None or not answer.method.startswith("refused:unsupported"), answer


def test_the_ask_and_the_chat_refuse_one_room_on_a_picture(settings: Settings) -> None:
    client, project, drawing = picture_project(settings, kept=True)
    found = ask(client, project, drawing, "How many radiators are in the cafeteria?")
    assert found["answer"] is None and found["refusal"] is not None, found
    # the existing one-room words, not "I don't count radiators" (the picture does count them)
    assert found["refusal"]["text"].startswith(PARTS[IN_ONE_ROOM].split(" Try")[0]), found
    assert "don't count" not in found["refusal"]["text"], found
    assert found["method"] != FACTS and "29" not in (found["explanation"] or ""), found
    asked = client.post(
        f"/api/projects/{project['id']}/ask",
        json={"question": "How many radiators are in the cafeteria?"},
    )
    parts = {p["drawing_id"]: p["answer"] for p in asked.json()["parts"]}
    assert parts[drawing]["answer"] is None and parts[drawing]["method"] != FACTS
    sheet = ask(client, project, drawing, "How many radiators are drawn on this plan?")
    assert sheet["method"] == FACTS and "29" in sheet["answer"], sheet


@pytest.mark.parametrize(
    "text",
    [
        "What is the net floor area of the room 'ESIK (67-2)', in m²?",
        "How long is the heating pipe on H-101, in metres?",
        "How many doors in the door schedule have a wood solid core door?",
        "Which room in the finish room schedule has the largest area?",
    ],
)
def test_a_unit_or_a_table_is_no_place_inside_the_sheet(text: str) -> None:
    """The golden set's "in m²" and "in the door schedule" (2026-11-15): not a room."""
    found = parse_ifc_question(text)
    assert found is None or found.place is None, found


def test_on_the_plumbing_plan_is_the_sheet_and_in_the_plumbing_room_is_refused(
    settings: Settings,
) -> None:
    """P-101 (8 WCs, 8 washbasins): "on the plumbing plan" is the sheet since #711, so 8; "in the
    plumbing room" is one room, so refused instead of the sheet's 8."""
    client, project, drawing = picture_project(settings, kept=False)
    file = next(f for f in project["files"] if f["drawing_id"] == drawing)
    fixtures = [
        Fact(topic="sanitary_terminal.count", subject=subject, value=8, unit="count",
             discipline="plumbing", source="picture:vlm:held")
        for subject in ("WC UP-Spülkasten Betätigung vorne:35 x 60cm", "Waschtisch:60 x 60cm")
    ]  # fmt: skip
    PictureSheets(None, kept_in(settings.projects_dir.parent / "pictures", "template")).put(
        file["sha256"],
        PictureFactSheet(model=file["sha256"][:16], disciplines=["plumbing"], facts=fixtures),
    )
    sheet = ask(client, project, drawing, "How many WCs are shown on the plumbing plan?")
    assert sheet["method"] == FACTS and "8" in sheet["answer"], sheet
    room = ask(client, project, drawing, "How many WCs are in the plumbing room?")
    assert room["answer"] is None and room["method"] != FACTS, room


@pytest.mark.parametrize(
    ("text", "said"),
    [
        ("How many radiators are in the heating system?", "6"),  # review-721 M1: a system
        ("How long are the pipes in the heating system?", "5.5"),
        ("How many radiators are in Plan image 1?", "6"),  # S1: the drawing's own name
        ("How many radiators are in H-101 E00 heating.png?", "6"),  # S1: its file
    ],
)
def test_a_system_or_the_drawing_s_own_name_is_no_room(text: str, said: str) -> None:
    answer = _answer(text)
    assert answer is not None and answer.method == FACTS and said in str(answer.answer), answer


@pytest.mark.parametrize(
    "text",
    [
        "How long are the pipes in the waste water system?",  # review-721 M1 (main 31.41 m)
        "How many fire dampers are in the ventilation system?",  # M1 (main 5)
        "How many toilets are in Plan image 1?",  # S1 (main 8)
        "How many toilets are in P-101 E00 plumbing.png?",  # S1 (main 8)
    ],
)
def test_review_721_questions_name_no_place(text: str) -> None:
    found = parse_ifc_question(text)
    assert found is not None and found.place is None, found

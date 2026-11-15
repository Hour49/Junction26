"""Big QA R1 S2 (chat-r1 rows 1, 5, 11-14): a message that names a drawing ("on Drawn plan 1", "on
Plan image 2", "in the building model") still asked every drawing, so the reply's first card and
numbers came from drawings the user did not ask about. The drawings a message names, by their
plain names (list_drawings) or, for the IFC, by "building model"."""

import pytest
from test_agent_loop import Model, Tools, call, final, step, turn

from app.core.agent.named import named_drawings, unnamed

NAMES = {
    "d1": "Drawn plan 1",
    "d2": "Drawn plan 2",
    "d10": "Drawn plan 10",
    "m1": "Building model 1",
    "i2": "Plan image 2",
    "i12": "Plan image 12",
}


@pytest.mark.parametrize(
    ("message", "named"),
    [
        ("How many doors are there in the building model?", {"m1"}),  # row 1
        ("What is the area of the kitchen on Drawn plan 1?", {"d1"}),  # row 5
        ("how mnay windwos are in the bulding model", {"m1"}),  # row 11, misspelt
        ("Montako ovea rakennusmallissa on?", {"m1"}),  # row 12, Finnish
        ("How many toilets are there on Plan image 2?", {"i2"}),  # row 14
        ("how many toilets on plan image 2", {"i2"}),  # any case
        ("What's the area of room 0.02 on Drawn plan 1?", {"d1"}),  # row 4
        ("Doors on Drawn plan 10?", {"d10"}),  # not Drawn plan 1
        ("Doors on Plan image 12?", {"i12"}),  # not Plan image 2... nor 1
        ("Compare Drawn plan 1 and Drawn plan 2", set()),  # compare: every drawing (review-693)
        ("How many doors in Building model 1?", {"m1"}),
        ("How many doors does the IFC model have?", {"m1"}),
        ("Which drawing has the largest floor area?", set()),  # row 13: names none
        ("How many doors are there?", set()),
        ("What is the area of the kitchen?", set()),
    ],
)
def test_the_drawings_a_message_names(message: str, named: set[str]) -> None:
    assert named_drawings(message, NAMES) == named


def test_no_building_model_in_the_project_names_nothing() -> None:
    assert named_drawings("doors in the building model", {"d1": "Drawn plan 1"}) == set()


def test_a_page_s_name_wins_over_its_drawing_s() -> None:
    names = {"p1": "Drawn plan 1, page 1", "p2": "Drawn plan 1, page 2"}
    assert named_drawings("rooms on Drawn plan 1, page 2", names) == {"p2"}


@pytest.mark.parametrize(
    ("question", "names", "asked"),
    [
        (
            "How many toilets are there on Plan image 2?",
            ["Plan image 2"],
            "How many toilets are there?",
        ),
        (
            "What is the area of the kitchen on Drawn plan 1?",
            ["Drawn plan 1"],
            "What is the area of the kitchen?",
        ),
        (
            "How many doors are there in the building model?",
            ["Building model 1"],
            "How many doors are there?",
        ),
        ("how mnay windwos are in the bulding model", ["Building model 1"], "how mnay windwos are"),
        (
            "Montako ovea rakennusmallissa on?",
            ["Building model 1"],
            "Montako ovea rakennusmallissa on?",
        ),
        ("Rooms on Drawn plan 10?", ["Drawn plan 1"], "Rooms on Drawn plan 10?"),
    ],
)
def test_the_asked_question_leaves_the_named_drawing_out(
    question: str, names: list[str], asked: str
) -> None:
    assert unnamed(question, names) == asked


def test_r1_row_13_the_card_of_the_drawing_the_text_cites_comes_first() -> None:
    """Row 13: "Drawn plan 2 has the largest floor area at 312.23 m2 [1]" over a card that opened
    on "Drawn plan 1: 295.99 m²". The cards of the drawings the text cites come first, in the
    order it cites them; the rest keep their order."""

    def part(drawing_id: str, value: float, mark: str) -> dict[str, object]:
        return {
            "drawing_id": drawing_id,
            "name": f"{drawing_id}.pdf",
            "answer": {
                "answer": value,
                "unit": "m2",
                "marks": [{"id": mark, "page": 1, "box": [0.1, 0.1, 0.2, 0.2], "label": "Plan"}],
            },
        }

    found = {
        "question": "What is the total floor area?",
        "parts": [
            part("1" * 16, 295.99, "m1"),
            part("2" * 16, 312.23, "m2"),
            part("3" * 16, 100.0, "m3"),
        ],
    }
    model = Model(
        step(call("ask_drawings", question=found["question"])),
        final(text="Drawn plan 2 has the largest floor area at 312.23 m2 [ev_2]."),
    )
    got = turn(model, Tools(ask_drawings=found))
    order = [p["drawing_id"] for p in got.answers[0]["parts"]]
    assert order == ["2" * 16, "1" * 16, "3" * 16]


@pytest.mark.parametrize(
    "message",
    [
        "How many rooms are there on Drawn plan 1 and the others?",
        "How many rooms are there besides Drawn plan 1?",
        "How many rooms are there on drawings other than Drawn plan 1?",
        "How many rooms, not counting Drawn plan 1?",
        "Does Drawn plan 1 have more rooms than the other drawings?",
        "Rooms on every drawing, Drawn plan 1 included?",
        "How many rooms except on Drawn plan 1?",
        "Which drawing has the most rooms, Drawn plan 1 or Plan image 2?",
        "Compare Drawn plan 1 with the rest",
        "Rooms in all drawings, apart from Drawn plan 1",
        "Rooms excluding Drawn plan 1",
        "How many doors are there without the building model?",
    ],
)
def test_review_693_m1_a_message_about_other_drawings_too_narrows_to_none(message: str) -> None:
    """review-693 M1: the named drawing alone would answer for the others (or the opposite)."""
    assert named_drawings(message, NAMES) == set()


def test_review_693_s3_the_model_of_a_thing_is_no_building_model() -> None:
    assert named_drawings("What does the model of the kitchen show?", NAMES) == set()


@pytest.mark.parametrize(
    ("question", "names", "asked"),
    [
        (
            "How many doors are on Drawn plan 1 and Drawn plan 2?",
            ["Drawn plan 1", "Drawn plan 2"],
            "How many doors are?",
        ),
        (
            "How many rooms are on Drawn plan 1 page 2?",
            ["Drawn plan 1, page 2"],
            "How many rooms are?",
        ),
    ],
)
def test_review_693_s1_no_fragment_is_left(question: str, names: list[str], asked: str) -> None:
    assert unnamed(question, names) == asked


def test_review_693_s1_a_page_named_without_its_comma() -> None:
    names = {"p1": "Drawn plan 1, page 1", "p2": "Drawn plan 1, page 2"}
    assert named_drawings("rooms on Drawn plan 1 page 2", names) == {"p2"}


@pytest.mark.parametrize(
    "message",
    [
        "How many rooms on Drawn plan 1 and the remaining drawings?",
        "How many rooms in the whole project, and on Drawn plan 1?",
        "How many rooms in total, including Drawn plan 1?",
        "How many rooms on Drawn plan 1 and elsewhere?",
        "Rooms across Drawn plan 1 and any other plan",
        "Rooms on Drawn plan 1 and the entire set, altogether",
        "Rooms overall, Drawn plan 1 too",
    ],
)
def test_review_693_m1b_a_message_about_the_whole_project_narrows_to_none(message: str) -> None:
    """review-693 M1 (second pass): "the remaining drawings", "the whole project", "in total,
    including", "elsewhere" still narrowed to Drawn plan 1."""
    assert named_drawings(message, NAMES) == set()


@pytest.mark.parametrize(
    "message",
    ["How many rooms on Drawn plan 1 and everywhere else?", "Doors everywhere, Drawn plan 1 too"],
)
def test_review_693_s_everywhere_narrows_to_none(message: str) -> None:
    """qa-a's should on #693: "on Drawn plan 1 and everywhere else" narrowed to Drawn plan 1."""
    assert named_drawings(message, NAMES) == set()

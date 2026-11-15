"""Big QA R1 chat rows 7, 9, 10: an "I don't know" about Drawn plan 1 still carried an unrelated
card ("Building model 1: Total doors: 68 Doors by type ...", for the swimming pool the model's
73-space list), which reads as an answer to the question. A refusal carries the drawings that
refused (named with what each lacks) and the card of a drawing only when its text cites it."""

from typing import Any

import pytest
from test_agent_loop import HALL, Model, Tools, call, final, step, turn

PLAN, MODEL = "1" * 16, "2" * 16
REFUSED = {
    "drawing_id": PLAN,
    "name": "plan.pdf",
    "answer": {
        "answer": None,
        "refusal": {"code": "unsupported-question", "text": "Doors are not read by opening side."},
    },
}
DOORS = {
    "drawing_id": MODEL,
    "name": "house.ifc",
    "answer": {
        "answer": "Total doors: 68",
        "unit": None,
        "level": {"level": "low"},
        "marks": [{"id": "m1", "page": 1, "box": [0.1, 0.1, 0.2, 0.2], "label": "Doors"}],
    },
}
ASKED = {"question": "How many doors open outward?", "parts": [DOORS, REFUSED]}


def refusal(text: str, **more: Any) -> Any:
    model = Model(
        step(call("ask_drawings", question=ASKED["question"])),
        final(kind="dont_know", text=text, **more),
    )
    return turn(model, Tools(ask_drawings=ASKED))


def test_r1_row_7_a_refusal_carries_no_other_drawing_s_card() -> None:
    got = refusal("I don't know. The drawing reader cannot filter doors by opening direction.")
    assert got.kind == "dont_know"
    parts = [part for answer in got.answers for part in answer["parts"]]
    assert [part["drawing_id"] for part in parts] == [PLAN]  # named with what it lacks
    assert all(part["answer"]["refusal"] for part in parts)


def test_a_refusal_that_cites_a_drawing_keeps_that_drawing_s_card() -> None:
    got = refusal("I don't know which doors open outward; the model lists 68 doors [ev_1].")
    parts = [part["drawing_id"] for answer in got.answers for part in answer["parts"]]
    assert parts == [MODEL, PLAN]


def test_an_answer_keeps_every_card() -> None:
    model = Model(
        step(call("ask_drawings", question=ASKED["question"])),
        final(text="The model has 68 doors [ev_1]."),
    )
    got = turn(model, Tools(ask_drawings=ASKED))
    assert [p["drawing_id"] for a in got.answers for p in a["parts"]] == [MODEL, PLAN]


@pytest.mark.parametrize(
    ("label", "text"),
    [
        ("Dormitorio", "The area of room 1DER-COC is shown below [ev_1]."),  # ifc-r1 row 4
        ("Flat", "The area of flat 2B is shown below [ev_1]."),
    ],
)
def test_ifc_r1_row_4_a_room_code_is_no_number_of_the_text_s_own(label: str, text: str) -> None:
    """ifc-r1 row 4 (main 031d74db, after #656/#679): "The area of room 1DER-COC is shown below
    [1]." still said no value: the 1 of the room's code read as the text's own number, and the
    cited mark's label is not the code, so #679's label strip does not take it out."""
    found = {
        **HALL,
        "parts": [
            {
                **HALL["parts"][0],
                "answer": {
                    **HALL["parts"][0]["answer"],
                    "answer": 12.43,
                    "marks": [{"id": "m1", "page": 1, "box": [0.1, 0.1, 0.2, 0.2], "label": label}],
                },
            }
        ],
    }
    model = Model(step(call("ask_drawings", question="q")), final(text=text))
    got = turn(model, Tools(ask_drawings=found))
    assert got.text.endswith(": 12.43 m²."), got.text


@pytest.mark.parametrize(
    "text",
    [
        "The hall is 156sqm, shown below [ev_1].",
        "The hall is 156m2, shown below [ev_1].",
        "The hall is 156 m², shown below [ev_1].",
    ],
)
def test_a_number_with_its_unit_is_still_the_text_s_own(text: str) -> None:
    model = Model(step(call("ask_drawings", question="q")), final(text=text))
    got = turn(model, Tools(ask_drawings=HALL))
    assert got.text == text.replace("[ev_1]", "[1]")

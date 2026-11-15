"""Big QA R2 chat (qa-a, New S3): at 390 the model wrote the prompt's "The answer is below." and
the server's value sentence (#656) said "Building model 1: 68." with no unit: a count's value has
no unit, its noun ("doors", the card's "68 doors") is on the drawing's quantity. The width only
picked another run of the model; the request is the same at 1440."""

import pytest
from test_agent_loop import DRAWING, Model, Tools, call, final, step, turn


def counted(value: int, noun: str | None) -> dict[str, object]:
    quantity = {"measure": "count", "subject": "door", "noun": noun}
    return {"question": "How many doors?", "parts": [{"drawing_id": DRAWING, "name": "house.ifc",
            "answer": {"answer": value, "unit": "count", "quantity": quantity,
                       "marks": [{"id": "m1", "page": 1, "box": [0.1, 0.1, 0.2, 0.2],
                                  "label": "Doors"}]}}]}  # fmt: skip


@pytest.mark.parametrize(
    ("value", "noun", "said"),
    [(68, "doors", ": 68 doors."), (1, "door", ": 1 door."), (3, None, ": 3.")],
)
def test_r2_a_count_left_to_the_card_is_said_with_its_noun(
    value: int, noun: str | None, said: str
) -> None:
    model = Model(step(call("ask_drawings", question="How many doors?")),
                  final(text="The answer is below [ev_1]."))  # fmt: skip
    got = turn(model, Tools(ask_drawings=counted(value, noun)), names={DRAWING: "Building model 1"})
    assert got.text == f"The answer is below [1]. Building model 1{said}", got.text

"""Big QA R1 edits row 5 (S3): "Drawn plan 3 (Drawn plan 3) has 3 rooms [1].". The model wrote the
drawing's plain name with its file in brackets, as the tool results give both, and the server
then put the plain name in place of the file. The name is said once."""

import pytest
from test_agent_loop import ASKED, DRAWING, Model, Tools, call, final, step, turn


@pytest.mark.parametrize(
    ("said", "shown"),
    [
        ("Drawn plan 1 (plan.pdf) has 1 room [ev_1].", "Drawn plan 1 has 1 room [1]."),
        ("plan.pdf (Drawn plan 1) has 1 room [ev_1].", "Drawn plan 1 has 1 room [1]."),
        ("plan.pdf has 1 room [ev_1].", "Drawn plan 1 has 1 room [1]."),
        ("Drawn plan 1 has 1 room [ev_1].", "Drawn plan 1 has 1 room [1]."),
    ],
)
def test_edits_r1_row_5_a_drawing_s_name_is_said_once(said: str, shown: str) -> None:
    model = Model(step(call("ask_drawings", question="How many rooms?")), final(text=said))
    got = turn(model, Tools(ask_drawings=ASKED), names={DRAWING: "Drawn plan 1"})
    assert got.text == shown

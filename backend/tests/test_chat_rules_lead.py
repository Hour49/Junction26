"""R4-C5 (Tudor's QA round 4): the rules chat's answer lead (#560) listed at most 12 drawings with
nothing saying more answered, and never led with the project total."""

from test_chat_rules import plan


def answered(n: int) -> list[dict[str, object]]:
    return [{"drawing": f"{at}.pdf", "answer": at, "unit": "count", "ev": f"ev_{at}"}
            for at in range(1, n + 1)]  # fmt: skip


def asked(given: list[dict[str, object]], **total: object) -> dict[str, object]:
    """An ask_drawings result: the loop's `answered` list, each drawing's part and the total."""
    parts = [{"drawing_id": f"d{at}", "name": a["drawing"],
              "answer": {"answer": a["answer"], "unit": a["unit"]}}
             for at, a in enumerate(given)]  # fmt: skip
    return {"answered": given, "parts": parts, **total}


def test_a_lead_cut_at_12_drawings_says_how_many_more_answered() -> None:
    found = asked(answered(15))
    _, args = plan("How many doors?", ("ask_drawings", {}, found))
    assert args["text"].endswith("; 12.pdf: 12 [ev_12]; and 3 more drawings.")
    assert args["evidence_ids"] == [f"ev_{at}" for at in range(1, 13)]
    one = asked(answered(13))
    _, args = plan("How many doors?", ("ask_drawings", {}, one))
    assert args["text"].endswith("; 12.pdf: 12 [ev_12]; and 1 more drawing.")
    whole = asked(answered(12))
    _, args = plan("How many doors?", ("ask_drawings", {}, whole))
    assert args["text"].endswith("; 12.pdf: 12 [ev_12].")


def test_a_project_total_leads_the_answer() -> None:
    """The total of drawings known to show different parts of one building comes first, in its
    unit; each drawing's value follows."""
    floors = [{"drawing": "eg.pdf", "answer": 40.5, "unit": "m2", "ev": "ev_1"},
              {"drawing": "og.pdf", "answer": 30.25, "unit": "m2", "ev": "ev_2"}]  # fmt: skip
    found = asked(floors, total=70.75, total_unit="m2")
    _, args = plan("What is the floor area?", ("ask_drawings", {}, found))
    assert args["text"] == "In total 70.75 m². eg.pdf: 40.5 m² [ev_1]; og.pdf: 30.25 m² [ev_2]."
    assert args["evidence_ids"] == ["ev_1", "ev_2"]


def test_one_answering_drawing_is_not_said_twice_as_the_total() -> None:
    found = asked(answered(1), total=1, total_unit="count")
    _, args = plan("How many doors?", ("ask_drawings", {}, found))
    assert args["text"] == "1.pdf: 1 [ev_1]."


def test_without_a_total_the_drawings_are_listed_as_before() -> None:
    found = asked(answered(2), total=None, total_unit=None)
    _, args = plan("How many doors?", ("ask_drawings", {}, found))
    assert args["text"] == "1.pdf: 1 [ev_1]; 2.pdf: 2 [ev_2]."


def test_a_counted_total_names_what_it_counts() -> None:
    doors = {"unit": "count", "quantity": {"noun": "doors"}}
    parts = [{"drawing_id": f"d{at}", "name": f"{at}.pdf", "answer": {"answer": at, **doors}}
             for at in (1, 2)]  # fmt: skip
    found = {"answered": answered(2), "parts": parts, "total": 3, "total_unit": "count"}
    _, args = plan("How many doors?", ("ask_drawings", {}, found))
    assert args["text"] == "In total 3 doors. 1.pdf: 1 [ev_1]; 2.pdf: 2 [ev_2]."

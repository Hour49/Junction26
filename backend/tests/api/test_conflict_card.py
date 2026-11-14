"""The conflict card (board #14, Tudor's asks 8-10): a settle's note (a typed answer in words), and
each conflict's plain-words title, why and suggested answers (app/core/review/conflict_card.py)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_review_core import AT, BOX_A, BOX_B, DRAWING, disputed, quantity

from app.core.drawing.model import MeasuredValue
from app.core.errors import InvalidInputError
from app.core.pipeline.model import QuantityConflict
from app.core.review import conflict_card
from app.core.review.model import NOTE_MAX, Edit, ReviewState
from app.core.review.review import apply, row, sign
from scripts.make_sample_archive import sample_files

KEY = "area:room|name=1.01"  # flat-b's room 1.01: outline 22.40 m2, printed 30 m2, a rule decides


def doors(resolved: bool) -> Any:
    found = quantity("door", 2, "count", BOX_A, BOX_B, conflict=disputed(resolved=resolved))
    return row(found, DRAWING, ReviewState(), {})


# Ask 10: title and why


def test_a_count_no_rule_decides_reads_as_a_question_and_says_a_person_chooses() -> None:
    shown = doors(resolved=False)
    assert conflict_card.title(shown) == "Door count: 2 or 3?"
    assert conflict_card.why(shown) == (
        "The methods disagree: 2 by the sheet, 3 by the IFC model. "
        "No rule decides between them, so a person has to choose."
    )


def test_a_conflict_a_rule_decides_says_settled_by_a_rule_and_the_value_used() -> None:
    assert conflict_card.why(doors(resolved=True)).endswith(
        "Settled by a rule (the sheet's own count): 2 is used."
    )


def test_an_area_conflict_writes_square_metres_and_each_value_once() -> None:
    values = (
        MeasuredValue(value=22.401, method="polygon_x_scale"),
        MeasuredValue(value=30.0, method="printed_label"),
        MeasuredValue(value=30.0004, method="summed_rooms"),  # the same value, written once
    )
    conflict = QuantityConflict(values=values, resolution=None, note="Checked twice.")
    area = quantity("area:room", 22.401, "m2", BOX_A, conflict=conflict)
    shown = row(area, DRAWING, ReviewState(), {})
    assert conflict_card.title(shown) == "Area of room: 22.40 m² or 30.00 m²?"
    assert conflict_card.why(shown).startswith(
        "The methods disagree: 22.40 m² by the room outlines at the sheet's scale, 30.00 m² by "
        "the printed room areas, 30.00 m² by the summed rooms. Checked twice. No rule"
    )
    assert conflict_card.suggestions(shown) == ["22.40 m²", "30.00 m²"]


# Ask 9: suggestions


def test_a_count_s_suggestions_are_its_values_with_the_noun() -> None:
    assert conflict_card.suggestions(doors(resolved=False)) == ["2 doors", "3 doors"]
    one = quantity(
        "door",
        1,
        "count",
        conflict=QuantityConflict(
            values=(
                MeasuredValue(value=1, method="parser"),
                MeasuredValue(value=0, method="ifc_model"),
            ),
            resolution=None,
        ),
    )
    assert conflict_card.suggestions(row(one, DRAWING, ReviewState(), {})) == ["1 door", "0 doors"]


# Ask 8: a settle's note


def test_a_note_alone_keeps_the_value_in_use_settles_and_allows_sign_off() -> None:
    found = quantity("door", 2, "count", BOX_A, BOX_B, conflict=disputed(resolved=False))
    edit = Edit(quantity="door", action="settle", note="  2: the second door is a wardrobe  ")
    state = apply(ReviewState(), edit, found, DRAWING, AT)
    settled = state.settled["door"]
    assert (settled.value, settled.note) == (2, "2: the second door is a wardrobe")
    shown = row(found, DRAWING, state, {})
    assert (shown.needs_person, shown.settled) == (False, settled)
    assert sign(state, found, DRAWING, "Ana", AT).signed["door"].value == 2


def test_a_note_goes_with_the_value_it_explains() -> None:
    found = quantity("door", 2, "count", BOX_A, BOX_B, conflict=disputed(resolved=False))
    edit = Edit(quantity="door", action="settle", value=3, note="the IFC model is right")
    assert apply(ReviewState(), edit, found, DRAWING, AT).settled["door"].note == (
        "the IFC model is right"
    )
    plain = Edit(quantity="door", action="settle", value=3)
    assert apply(ReviewState(), plain, found, DRAWING, AT).settled["door"].note is None


def test_settle_without_a_value_or_a_note_is_still_invalid() -> None:
    found = quantity("door", 2, "count", BOX_A, BOX_B, conflict=disputed(resolved=False))
    with pytest.raises(InvalidInputError, match="value to keep, or a note"):
        apply(ReviewState(), Edit(quantity="door", action="settle"), found, DRAWING, AT)


@pytest.mark.parametrize(
    "edit",
    [
        {"quantity": "door", "action": "reject", "mark": "m1", "note": "why"},
        {"quantity": "door", "action": "settle", "note": "   "},
        {"quantity": "door", "action": "settle", "note": ""},
        {"quantity": "door", "action": "settle", "note": "x" * (NOTE_MAX + 1)},
    ],
)
def test_a_note_on_another_action_empty_or_too_long_is_refused(edit: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        Edit.model_validate(edit)


# Through the API


@pytest.fixture
def flat_b(client: TestClient) -> tuple[str, str]:
    """The sample's flat-b alone: (project id, drawing id)."""
    data = sample_files()["plans/flat-b.pdf"]
    response = client.post("/api/projects", params={"name": "flat-b.pdf"}, content=data)
    assert response.status_code == 202, response.text
    project_id = response.json()["id"]
    project = client.get(f"/api/projects/{project_id}").json()
    return project_id, project["drawings"][0]["drawing_id"]


def conflict(client: TestClient, project_id: str) -> dict[str, Any]:
    review = client.get(f"/api/projects/{project_id}/review").json()
    return next(found for found in review["conflicts"] if found["quantity"] == KEY)


def test_the_project_review_gives_each_conflict_a_title_why_and_suggestions(
    client: TestClient, flat_b: tuple[str, str]
) -> None:
    found = conflict(client, flat_b[0])
    assert found["title"] == "Area of room (name Küche · 1.01): 22.40 m² or 30.00 m²?"
    assert found["why"] == (
        "The methods disagree: 22.40 m² by the room outlines at the sheet's scale, 30.00 m² by "
        "the printed room areas. Settled by a rule (the printed label over the outline at the "
        "sheet's scale): 30.00 m² is used."
    )
    assert found["suggestions"] == ["22.40 m²", "30.00 m²"]


def test_a_typed_answer_is_kept_with_the_settle_and_shown_on_the_conflict(
    client: TestClient, flat_b: tuple[str, str]
) -> None:
    project_id, drawing_id = flat_b
    url = f"/api/drawings/{drawing_id}/review"
    edit = {"quantity": KEY, "action": "settle", "note": "the printed 30 m² includes the closet"}
    takeoff = client.post(url, params={"project": project_id}, json=edit)
    assert takeoff.status_code == 200, takeoff.text
    shown = next(found for found in takeoff.json()["quantities"] if found["key"] == KEY)
    assert shown["settled"]["value"] == 30.0  # words only: the value in use is kept
    assert shown["settled"]["note"] == "the printed 30 m² includes the closet"
    assert conflict(client, project_id)["settled"]["note"] == edit["note"]
    unsettled = {"quantity": KEY, "action": "unsettle"}
    assert client.post(url, params={"project": project_id}, json=unsettled).status_code == 200
    assert conflict(client, project_id)["settled"] is None


def test_a_note_on_another_edit_is_422(client: TestClient, flat_b: tuple[str, str]) -> None:
    project_id, drawing_id = flat_b
    edit = {"quantity": KEY, "action": "reject", "mark": "m1", "note": "no"}
    response = client.post(
        f"/api/drawings/{drawing_id}/review", params={"project": project_id}, json=edit
    )
    assert response.status_code == 422
    assert response.json()["code"] == "validation"
    assert "a note goes with settle, not reject" in response.json()["detail"]

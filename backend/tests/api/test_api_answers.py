"""Asking, the takeoff, review edits, reset, sign-off and the CSV (docs/API.md)."""

import csv
import io
from dataclasses import replace
from functools import partial
from typing import Any, cast

import pytest
from conftest import plan_png, upload
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.adapters.decisions.uses import Confidence
from app.api.takeoff import _cell
from app.composition import DECISIONS_SIGNAL, build_ingest
from app.core import cost
from app.core.pipeline.ports import DrawingFiles
from app.main import create_app
from app.settings import Settings
from scripts.make_sample_archive import sample_files

DOORS = "How many doors are there?"


def ask(client: TestClient, drawing_id: str, question: str) -> dict[str, Any]:
    response = client.post("/api/ask", json={"drawing_id": drawing_id, "question": question})
    assert response.status_code == 200, response.text
    return response.json()


def review(client: TestClient, drawing_id: str, **edit: object) -> dict[str, Any]:
    response = client.post(f"/api/drawings/{drawing_id}/review", json=edit)
    assert response.status_code == 200, response.text
    return response.json()


def row(takeoff: dict[str, Any], key: str) -> dict[str, Any]:
    return next(found for found in takeoff["quantities"] if found["key"] == key)


def test_a_count_comes_with_its_row_named_marks_and_answer_line(
    client: TestClient, drawing_id: str
) -> None:
    answer = ask(client, drawing_id, DOORS)
    assert (answer["answer"], answer["unit"], answer["method"], answer["refusal"]) == (
        2, "count", "takeoff", None,
    )  # fmt: skip
    quantity = answer["quantity"]
    assert (quantity["key"], quantity["status"], quantity["rule"]["id"]) == (
        "door", "single", "each-once",
    )  # fmt: skip
    marks = answer["marks"]
    assert marks == quantity["marks"]
    assert [(mark["id"], mark["n"], mark["state"], mark["label"]) for mark in marks] == [
        ("m1", 1, "counted", "door"), ("m2", 2, "counted", "door"),
    ]  # fmt: skip
    assert all(mark["ref"] for mark in marks)
    assert answer["pages"][0]["url"].endswith("/pages/1.png")
    assert answer["cost_usd"] == 0.0
    assert answer["line"]["answer"] == 2
    assert [item["box"] for item in answer["line"]["evidence"]] == [mark["box"] for mark in marks]


def test_an_area_names_its_rooms_with_their_outlines_and_areas(
    client: TestClient, drawing_id: str
) -> None:
    total = row(client.get(f"/api/drawings/{drawing_id}/takeoff").json(), "area:room|indoor")
    labels = [mark["label"] for mark in total["marks"]]
    assert "Küche" in labels
    assert all(mark["polygon"] for mark in total["marks"])
    counted = [mark for mark in total["marks"] if mark["state"] == "counted"]
    assert sum(mark["value"] for mark in counted) == pytest.approx(total["value"], abs=0.01)


def test_an_item_the_rule_left_out_is_greyed_with_its_reason_and_can_be_counted_in(
    client: TestClient, drawing_id: str
) -> None:
    total = row(client.get(f"/api/drawings/{drawing_id}/takeoff").json(), "area:room|indoor")
    (out,) = [mark for mark in total["marks"] if mark["state"] == "excluded"]
    assert (out["id"], out["n"], out["label"]) == ("x1", None, "Balkon")
    assert out["reason"] and out["value"] > 0

    edit = {"quantity": "area:room|indoor", "action": "restore", "mark": "x1"}
    restored = row(review(client, drawing_id, **edit), "area:room|indoor")
    back = next(mark for mark in restored["marks"] if mark["id"] == "x1")
    assert (back["state"], back["reason"], restored["status"]) == (
        "counted",
        out["reason"],
        "edited",
    )
    assert restored["value"] == pytest.approx(total["value"] + out["value"], abs=0.01)

    edit["action"] = "reject"
    assert row(review(client, drawing_id, **edit), "area:room|indoor")["value"] == total["value"]


def test_a_question_it_cannot_parse_is_refused_with_questions_it_can_answer(
    client: TestClient, drawing_id: str
) -> None:
    answer = ask(client, drawing_id, "What colour is the roof?")
    assert (answer["answer"], answer["quantity"], answer["marks"]) == (None, None, [])
    refusal = answer["refusal"]
    assert refusal["code"] == "unsupported-question"
    assert refusal["text"].startswith("This question isn't one")
    assert {"quantity": "door", "label": "door count", "question": DOORS} in refusal["can_answer"]
    assert answer["line"]["abstain"] is True


def test_the_area_of_the_kitchen_is_the_one_kitchen_s_area(
    client: TestClient, drawing_id: str
) -> None:
    """R1-3-4: refused as "isn't one I can turn into a count, area, length or volume"."""
    by_number = ask(client, drawing_id, "What is the net floor area of room 2.01?")
    kitchen = ask(client, drawing_id, "What is the area of the kitchen?")
    assert kitchen["refusal"] is None
    assert (kitchen["answer"], kitchen["unit"]) == (by_number["answer"], "m2")
    assert kitchen["quantity"]["key"] == by_number["quantity"]["key"]
    assert kitchen["marks"] == by_number["marks"]


@pytest.mark.parametrize(
    ("question", "words"),
    [
        ("How many doors and windows are there?", "more than one kind of thing"),
        ("How many doors does the kitchen have?", "inside one room"),
    ],
)
def test_a_count_with_a_part_it_cannot_apply_says_which_part(
    client: TestClient, drawing_id: str, question: str, words: str
) -> None:
    """R1-5-2: these were answered with the whole-drawing door count; now refused, saying why."""
    answer = ask(client, drawing_id, question)
    assert (answer["answer"], answer["quantity"]) == (None, None)
    assert answer["refusal"]["code"] == "unsupported-question"
    assert words in answer["refusal"]["text"]
    assert {"quantity": "door", "label": "door count", "question": DOORS} in answer["refusal"][
        "can_answer"
    ]


def test_a_class_the_reader_did_not_look_for_is_refused_as_not_read(
    client: TestClient, drawing_id: str
) -> None:
    refusal = ask(client, drawing_id, "How many columns are there?")["refusal"]
    assert refusal["code"] == "not-read"
    assert "column" in refusal["text"]


@pytest.mark.parametrize(
    "raster",
    [{}, {"extractor_raster": "composite", "raster_components": "elements=dir:arm,plans=dir:arm"}],
)
def test_a_sheet_nothing_was_read_from_is_refused_without_blaming_the_build(
    settings: Settings, raster: dict[str, str]
) -> None:
    """The stand-in reader, or a configured raster reader that has nothing for this image: the
    refusal says nothing was found, not that the build lacks a reader."""
    (settings.projects_dir.parent / "arm").mkdir()  # an arm folder with no file for the image
    settings = settings.model_copy(update=raster)
    client = TestClient(
        create_app(settings, build_ingest(settings, settings.projects_dir, background=False))
    )
    project = client.get(f"/api/projects/{upload(client, plan_png(), 'plan.png')}").json()
    refusal = ask(client, project["drawings"][0]["drawing_id"], DOORS)["refusal"]
    assert refusal["code"] == "no-reader"
    assert refusal["text"] == (
        "Nothing was read from this sheet: its reader found no elements or rooms on it."
    )


def test_ask_names_a_drawing(client: TestClient) -> None:
    response = client.post("/api/ask", json={"question": DOORS})
    assert response.status_code == 422
    response = client.post("/api/ask", json={"question": DOORS, "drawing_id": "nope"})
    assert response.status_code == 404


def test_the_takeoff_leaves_out_zero_rows_unless_asked(client: TestClient, drawing_id: str) -> None:
    url = f"/api/drawings/{drawing_id}/takeoff"
    short = {found["key"] for found in client.get(url).json()["quantities"]}
    full = {found["key"] for found in client.get(url, params={"zeros": True}).json()["quantities"]}
    assert "door" in short and "room:sauna" not in short
    assert "room:sauna" in full


def test_a_row_carries_its_parsed_scope(client: TestClient, drawing_id: str) -> None:
    takeoff = client.get(f"/api/drawings/{drawing_id}/takeoff").json()
    found = row(takeoff, "area:room|name=küche")
    assert (found["measure"], found["subject"], found["label"]) == (
        "area", "room", "area of room (name küche)",
    )  # fmt: skip
    assert found["scope"]["name"] == "küche"


def test_rejecting_and_adding_marks_recounts_and_the_engineer_sees_it(
    client: TestClient, drawing_id: str
) -> None:
    door = row(review(client, drawing_id, quantity="door", action="reject", mark="m1"), "door")
    assert (door["value"], door["status"]) == (1, "edited")
    takeoff = review(
        client, drawing_id, quantity="door", action="add", page=1, box=[0.1, 0.1, 0.2, 0.2]
    )
    door = row(takeoff, "door")
    assert door["value"] == 2
    assert [(mark["id"], mark["n"], mark["state"]) for mark in door["marks"]] == [
        ("m1", None, "rejected"), ("m2", 1, "counted"), ("a1", 2, "added"),
    ]  # fmt: skip
    review(client, drawing_id, quantity="door", action="add", page=1, box=[0.3, 0.3, 0.4, 0.4])
    answer = ask(client, drawing_id, DOORS)
    assert answer["answer"] == 3
    assert answer["quantity"]["original_value"] == 2
    assert answer["line"]["answer"] == 2  # the scorer's line stays what the pipeline read
    door = row(review(client, drawing_id, quantity="door", action="reject", mark="a1"), "door")
    assert door["value"] == 2  # an added mark that is rejected is removed
    door = row(review(client, drawing_id, quantity="door", action="restore", mark="m1"), "door")
    assert door["value"] == 3


def test_an_edit_changes_its_own_quantity_only(client: TestClient, drawing_id: str) -> None:
    takeoff = review(client, drawing_id, quantity="shower", action="reject", mark="m1")
    assert row(takeoff, "shower")["value"] == 0
    assert row(takeoff, "shower+bathtub")["value"] == 2


def test_leaving_a_room_out_of_an_area_subtracts_its_area(
    client: TestClient, drawing_id: str
) -> None:
    total = row(client.get(f"/api/drawings/{drawing_id}/takeoff").json(), "area:room|indoor")
    first = total["marks"][0]
    takeoff = review(client, drawing_id, quantity="area:room|indoor", action="reject", mark="m1")
    after = row(takeoff, "area:room|indoor")["value"]
    assert after == pytest.approx(total["value"] - first["value"], abs=1e-3)


def test_a_settled_value_holds_until_the_next_mark_edit(
    client: TestClient, drawing_id: str
) -> None:
    door = row(review(client, drawing_id, quantity="door", action="settle", value=5), "door")
    assert (door["value"], door["status"], door["settled"]["value"]) == (5, "edited", 5)
    door = row(review(client, drawing_id, quantity="door", action="reject", mark="m2"), "door")
    assert (door["value"], door["settled"]) == (1, None)


def test_reset_undoes_one_quantity_or_all(client: TestClient, drawing_id: str) -> None:
    review(client, drawing_id, quantity="door", action="reject", mark="m1")
    review(client, drawing_id, quantity="window", action="reject", mark="m1")
    client.post(f"/api/drawings/{drawing_id}/signoff", json={"quantity": "door", "by": "Ana"})
    takeoff = review(client, drawing_id, quantity="door", action="reset")
    assert (row(takeoff, "door")["value"], row(takeoff, "door")["status"]) == (2, "single")
    assert row(takeoff, "window")["value"] == 1
    takeoff = review(client, drawing_id, action="reset")
    assert row(takeoff, "window")["value"] == 2


def test_sign_off_shows_in_the_answer_and_locks_the_row(
    client: TestClient, drawing_id: str
) -> None:
    url = f"/api/drawings/{drawing_id}/signoff"
    door = row(client.post(url, json={"quantity": "door", "by": "Ana"}).json(), "door")
    assert door["status"] == "signed"
    assert (door["signed"]["by"], door["signed"]["value"]) == ("Ana", 2)
    assert door["signed"]["at"].endswith("Z")
    assert ask(client, drawing_id, DOORS)["quantity"]["signed"]["by"] == "Ana"
    response = client.post(
        f"/api/drawings/{drawing_id}/review",
        json={"quantity": "door", "action": "reject", "mark": "m1"},
    )
    assert response.status_code == 409
    assert response.json() == {
        "detail": "door is signed off by Ana; undo the sign-off first",
        "code": "not-allowed",
    }
    door = row(
        client.post(url, json={"quantity": "door", "by": "Ana", "undo": True}).json(), "door"
    )
    assert (door["status"], door["signed"]) == ("single", None)
    review(client, drawing_id, quantity="door", action="reject", mark="m1")


def test_edits_are_kept_on_disk_across_app_restarts(
    client: TestClient, drawing_id: str, settings: Settings
) -> None:
    review(client, drawing_id, quantity="door", action="reject", mark="m1")
    ingest = client.app.state.ingest  # type: ignore[attr-defined]
    again = TestClient(create_app(settings, ingest))  # a new app reads the edits from disk
    assert row(again.get(f"/api/drawings/{drawing_id}/takeoff").json(), "door")["value"] == 1


@pytest.mark.parametrize(
    ("edit", "status"),
    [
        ({"quantity": "nope", "action": "settle", "value": 1}, 404),
        ({"quantity": "door", "action": "reject", "mark": "m9"}, 404),
        ({"action": "settle", "value": 1}, 422),
        ({"quantity": "door", "action": "reject"}, 422),
        ({"quantity": "door", "action": "add", "page": 1}, 422),
        ({"quantity": "door", "action": "add", "page": 2, "box": [0, 0, 1, 1]}, 422),
        ({"quantity": "area:room|indoor", "action": "add", "page": 1, "box": [0, 0, 1, 1]}, 422),
        ({"quantity": "door", "action": "settle"}, 422),
        ({"quantity": "door", "action": "explode"}, 422),
        ({"quantity": "door", "action": "add", "page": 1, "box": [0.5, 0.5, 0.1, 0.1]}, 422),
    ],
)
def test_a_bad_edit_is_refused(
    client: TestClient, drawing_id: str, edit: dict[str, object], status: int
) -> None:
    response = client.post(f"/api/drawings/{drawing_id}/review", json=edit)
    assert response.status_code == status, response.text
    assert set(response.json()) >= {"detail", "code"}


def test_the_takeoff_exports_as_csv(client: TestClient, drawing_id: str) -> None:
    client.post(f"/api/drawings/{drawing_id}/signoff", json={"quantity": "door", "by": "Ana"})
    response = client.get(f"/api/drawings/{drawing_id}/takeoff.csv")
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert response.headers["content-disposition"] == 'attachment; filename="plan-takeoff.csv"'
    rows = {line["key"]: line for line in csv.DictReader(io.StringIO(response.text))}
    door = rows["door"]
    assert (door["drawing"], door["value"], door["status"], door["signed_by"]) == (
        "plan.pdf", "2", "signed", "Ana",
    )  # fmt: skip


@pytest.mark.parametrize(
    ("cell", "written"),
    [("=HYPERLINK(1)", "'=HYPERLINK(1)"), ("+1", "'+1"), ("@x", "'@x"), ("door", "door"), (2, 2)],
)
def test_a_csv_cell_never_runs_as_a_formula(cell: object, written: object) -> None:
    assert _cell(cell) == written


class Rated:
    """A stand-in for the pipeline's confidence: it reads the sheet as Decisions does and says
    0.87 for every answer it is asked about."""

    def __init__(self, seen: list[tuple[str, str, object, bytes]], files: DrawingFiles) -> None:
        self._seen = seen
        self._files = files

    def probability(self, path: str, family: str, value: object) -> Confidence:
        self._seen.append((path, family, value, self._files.read(path)))
        return Confidence(0.87, "decisions: test")


def test_an_answer_carries_the_pipeline_s_score_named_and_uncalibrated_never_in_its_proof(
    client: TestClient, plan_pdf: bytes, raster: tuple[TestClient, str]
) -> None:
    images, drawing_id = raster
    assert ask(images, drawing_id, DOORS)["confidence"] is None  # DECISIONS_CONFIDENCE off
    seen: list[tuple[str, str, object, bytes]] = []
    for app in (images, client):
        state = cast(FastAPI, app.app).state
        state.answering = replace(
            state.answering, confidence=partial(Rated, seen), signal=DECISIONS_SIGNAL
        )
    answer = ask(images, drawing_id, DOORS)
    assert answer["answer"] == 2
    assert answer["confidence"] == {"signal": "g1main", "score": 0.87, "calibrated": False}
    assert answer["line"]["confidence"] == 0.87  # the scorer's answer_v1.1 line, unchanged
    assert "confidence" not in answer["proof"]  # the proof never presents it as a probability
    assert seen == [("plan.png", "door", 2, plan_png())]  # the sheet as the pipeline read it
    refused = ask(images, drawing_id, "What colour is the roof?")
    assert refused["confidence"] is None
    vector = client.get(f"/api/projects/{upload(client, plan_pdf)}").json()["drawings"][0]
    answer = ask(client, vector["drawing_id"], DOORS)  # read on the vector route: not rated
    assert (answer["answer"], answer["confidence"], len(seen)) == (2, None, 1)
    assert "decisions" not in (answer["explanation"] or "")


def test_a_count_of_rooms_has_one_key_whatever_each_room_is_called(
    raster: tuple[TestClient, str],
) -> None:
    client, drawing_id = raster
    proof = ask(client, drawing_id, "How many bedrooms are there?")["proof"]
    assert [(key["label"], key["count"]) for key in proof["legend"]] == [("bedroom", 2)]
    assert proof["arithmetic"] is None  # not "1 Makuuhuone 1 + 1 Makuuhuone 2 = 2"


def test_a_settled_room_area_shows_the_settled_value_on_its_mark_and_in_its_sum(
    client: TestClient,
) -> None:
    """K1: after flat-b's room 1.01 was settled at the outline's 22.40 m², the answer's mark kept
    the printed label's 30 m² and the sum read "30 = 30 m²; kept: 22.4 m²"."""
    project = client.get(f"/api/projects/{upload(client, sample_files()['plans/flat-b.pdf'])}")
    drawing_id = project.json()["drawings"][0]["drawing_id"]
    key = "area:room|name=1.01"
    before = ask(client, drawing_id, "What is the net floor area of room 1.01?")
    assert before["quantity"]["key"] == key
    assert [mark["value"] for mark in before["marks"]] == [30.0]
    assert before["proof"]["arithmetic"] is None  # one part: no "30 = 30 m²" (R3 qa-2)
    outline = before["quantity"]["first"]
    assert outline["method"] == "polygon_x_scale"

    review(client, drawing_id, quantity=key, action="settle", value=outline["value"])
    after = ask(client, drawing_id, "What is the net floor area of room 1.01?")
    assert after["answer"] == pytest.approx(22.40, abs=0.01)
    assert [mark["value"] for mark in after["marks"]] == [outline["value"]]
    assert after["proof"]["arithmetic"] == "settled by a person, was 30 m²"


class PaidRated(Rated):
    """Rated, whose Decisions call costs $0.0003 (R1b-4-2)."""

    def probability(self, path: str, family: str, value: object) -> Confidence:
        cost.charge(0.0003)
        return super().probability(path, family, value)


def test_an_answer_records_the_model_calls_it_paid_for(raster: tuple[TestClient, str]) -> None:
    images, drawing_id = raster
    state = cast(FastAPI, images.app).state
    seen: list[tuple[str, str, object, bytes]] = []
    state.answering = replace(
        state.answering, confidence=partial(PaidRated, seen), signal=DECISIONS_SIGNAL
    )
    answer = ask(images, drawing_id, DOORS)
    assert answer["cost_usd"] == pytest.approx(0.0003)
    assert answer["line"]["cost_usd"] == pytest.approx(0.0003)

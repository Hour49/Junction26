"""get_counting_rules (fable-rooms/chat item 8, app/adapters/counting_rules.py): the convention for
each quantity in any wording, every convention without one, an unknown quantity said so, a bad
call an error and never an exception, and the toolbox offers it."""

import json

import pytest
from fastapi.testclient import TestClient
from test_api_chat import sample

from app.adapters.agent_tools import project_toolbox
from app.adapters.counting_rules import CONVENTIONS, NAME, run_counting_tool
from app.core.pipeline.rules import SHOWERS_AND_BATHTUBS
from app.core.review.ask import CLOSET_RULE


def rule(quantity: object) -> dict:
    return json.loads(run_counting_tool(NAME, json.dumps({"quantity": quantity})))


@pytest.mark.parametrize(
    ("asked", "quantity", "says"),
    [
        ("Does that include closet doors?", "doors", CLOSET_RULE),
        ("double doors", "doors", "a double door, a sliding or folding door is one door"),
        ("window sashes", "windows", "not one per sash or pane"),
        ("water closets", "toilets", "a urinal is not a toilet"),
        ("separate WC rooms", "toilets", "the toilet in it counts as a toilet"),
        ("WC seats", "toilets", "toilet bowl"),
        ("double-bowl sinks", "sinks", "a double-bowl sink is one sink"),
        ("showers and bathtubs", "showers and bathtubs", SHOWERS_AND_BATHTUBS.text),
        ("sauna", "saunas", "sauna stoves instead"),
        (
            "Are shafts in the total floor area?",
            "floor area",
            "shafts, lifts and stairwells included",
        ),
        ("balconies in the floor area", "floor area", "outdoor rooms (balconies, terraces)"),
        ("the apartment's area", "apartment area", "stated net area"),
        ("area of the kitchen", "room area", "net floor area"),
        ("bedrooms", "rooms", "printed label"),
    ],
)
def test_the_convention_for_each_quantity(asked: str, quantity: str, says: str) -> None:
    got = rule(asked)
    assert got["quantity"] == quantity and says in got["convention"]
    assert not any(ch.isdigit() for ch in got["convention"])  # no number the validator can't trace


# qa-c's should-fixes on PR #353 (S4): the most specific cue wins, whole words only
@pytest.mark.parametrize(
    ("asked", "quantity"),
    [
        ("Does the area include the balcony?", "floor area"),
        ("Is the terrace in the area?", "floor area"),
        ("Are stairwells counted?", "floor area"),
        ("lifts", "floor area"),
        ("Is the elevator shaft in it?", "floor area"),
        ("Is a double-bowl sink one or two?", "sinks"),
        ("What is the area of the bathroom?", "room area"),
        ("How many bathrooms?", "rooms"),
        ("Küche", "rooms"),
        ("Türen", "doors"),
        ("Fenster", "windows"),
        ("ikkunat", "windows"),
        ("parveke pinta-ala", "floor area"),
        ("Does the toilet count include the water closet room?", "toilets"),
        ("closet doors", "doors"),
    ],
)
def test_the_most_specific_cue_wins(asked: str, quantity: str) -> None:
    assert rule(asked)["quantity"] == quantity


@pytest.mark.parametrize("asked", ["solar panels", "parking spaces", "glass panels"])
def test_a_cue_inside_another_word_does_not_match(asked: str) -> None:
    assert rule(asked)["convention"] is None


def test_the_floor_area_says_shafts_plainly_with_no_question_wording() -> None:
    assert "though the question" not in CONVENTIONS["floor area"][1]


def test_an_unknown_quantity_says_so_and_lists_the_known_ones() -> None:
    got = rule("parking spaces")
    assert got["convention"] is None and "parking spaces" in got["unknown"]
    assert got["known"] == list(CONVENTIONS)


def test_no_quantity_gives_every_convention() -> None:
    assert list(rule("")["conventions"]) == list(CONVENTIONS)
    assert list(json.loads(run_counting_tool(NAME, "{}"))["conventions"]) == list(CONVENTIONS)


@pytest.mark.parametrize("arguments", ["not json", "[1]", '{"quantity": 3}'])
def test_a_bad_call_is_an_error_never_an_exception(arguments: str) -> None:
    assert "error" in json.loads(run_counting_tool(NAME, arguments))
    assert "error" in json.loads(run_counting_tool("other", "{}"))


def test_the_toolbox_offers_it(client: TestClient) -> None:
    toolbox = project_toolbox(client.app, sample(client), [], {})
    assert NAME in {tool["function"]["name"] for tool in toolbox.tools}
    assert json.loads(toolbox.run(NAME, '{"quantity": "closet doors"}'))["quantity"] == "doors"

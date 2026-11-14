"""The rules that read a free-text question about an IFC model as a lookup over its facts."""

import pytest

from app.core.ifc_question import FactQuery, parse_ifc_question, storey_number


def parsed(text: str) -> FactQuery:
    query = parse_ifc_question(text)
    assert query is not None, text
    return query


def test_an_element_count_by_type() -> None:
    query = parsed("Which door kinds does the house have, and how many of each?")
    assert (query.entity, query.measures[0], query.by) == ("door", "count", "type")


def test_a_part_and_a_total() -> None:
    query = parsed("What is the total length of the external walls?")
    assert (query.entity, query.part, query.aggregate) == ("wall", "external", "total")
    assert "length" in query.measures


def test_a_storey_is_kept_as_the_question_words_it() -> None:
    query = parsed("List the rooms on level 2 with their areas, grouped by function.")
    assert (query.entity, query.storey, query.by) == ("space", "level 2", "function")
    assert "area" in query.measures


def test_a_room_named_by_its_use_asks_about_rooms_and_keeps_the_name() -> None:
    query = parsed("How many toilet rooms are on the second floor?")
    assert (query.entity, query.storey, query.words) == ("space", "second floor", ("toilet",))


def test_of_two_things_at_one_place_the_longer_wins() -> None:
    assert parsed("How many light switches are fitted?").entity == "switch"


def test_what_a_model_does_not_hold_is_unavailable() -> None:
    assert parsed("What did the roof cost?").family() == "unavailable"
    assert parsed("Which type of glazing do the windows have?").family() == "window.glazing"
    assert parsed("How many windows have double glazing?").family() == "window.count"
    assert parsed("What is the area of the glazed windows?").entity == "window"


def test_the_model_itself() -> None:
    assert parsed("Which software exported this file?").entity == "project"


def test_a_storey_question() -> None:
    assert parsed("What are the elevations of the storeys?").entity == "storey"


def test_yes_no_and_estimates_are_flagged() -> None:
    assert parsed("Are the internal walls load-bearing?").yes_no
    assert parsed("Roughly how much office area is there, as an estimate?").derived


def test_no_rule_no_lookup() -> None:
    assert parse_ifc_question("Tell me a joke.") is None


@pytest.mark.parametrize(
    ("phrase", "number"),
    [("level 3", 3), ("2.og", 2), ("ground floor", 0), ("third floor", 3), ("basement", -1)],
)
def test_storey_numbers(phrase: str, number: int) -> None:
    assert storey_number(phrase) == number


def test_the_components_of_a_system_are_the_components() -> None:
    assert parsed("Give the plumbing system components by category.").entity == "discipline"
    assert parsed("Which plumbing systems are there?").entity == "system"


def test_a_request_is_not_a_yes_no_question() -> None:
    assert not parsed("Can you provide an analysis of the structural system?").yes_no
    assert parsed("Are the internal walls load-bearing?").yes_no


def test_by_building_level_is_by_storey() -> None:
    assert parsed("How are the lights distributed across the building levels?").by == "storey"
    assert parsed("What is the count of electrical components by building level?").by == "storey"

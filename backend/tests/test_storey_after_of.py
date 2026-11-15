"""A storey named after "of" a drawing word scopes like "the P1 plan" (review-711 re-check, eu-big,
2026-11-15): "How many doors are on the plumbing plan of P1?" counted the whole sheet with no
storey. Only after a drawing word (plan, floor plan, sheet, drawing, layout), and by the same rules
as STOREY_AT: a code has a capital or follows a storey word, a name is one capitalised word that
is no sheet, floor or counted word. "The plan of the building" and "the plan of 12 m" stay as on
main."""

import pytest

from app.adapters.question_templates import TemplateParser
from app.core.answering.model import SEVERAL_STOREYS, Query, Unsupported

PARSE = TemplateParser().parse


@pytest.mark.parametrize(
    ("text", "storey"),
    [
        ("How many doors are on the plumbing plan of P1?", "P1"),
        ("How many doors are on the Plan of P1?", "P1"),
        ("How many doors are on the floor plan of the Erdgeschoss?", "Erdgeschoss"),
        ("How many doors are on the plan of level OG2?", "OG2"),
        ("How many rooms are on the drawing of E01?", "E01"),
        ("How many windows are on the layout of floor 1OG?", "1OG"),
    ],
)
def test_a_storey_after_of_a_drawing_word_scopes_the_count(text: str, storey: str) -> None:
    parsed = PARSE(text)
    assert isinstance(parsed, Query) and parsed.storey == storey, (text, parsed)


@pytest.mark.parametrize(
    "text",
    [
        "How many doors are on the plan of the building?",
        "How many doors are on the plan of 12 m?",
        "How many doors are on the plan of p1?",  # no capital, no storey word: maybe a typo
        "How many doors are on the plan of the Building?",  # a sheet word
    ],
)
def test_no_storey_is_read_from_a_non_storey_after_of(text: str) -> None:
    parsed = PARSE(text)
    assert isinstance(parsed, Query) and parsed.storey is None, (text, parsed)


def test_two_storeys_after_of_are_one_count_each() -> None:
    assert PARSE("How many doors are on the plan of P1 and P2?") == Unsupported(
        reason=SEVERAL_STOREYS
    )


def test_of_after_no_drawing_word_is_not_a_storey() -> None:
    """ "The doors of P1" is how main reads it: no drawing word before "of"."""
    before = PARSE("How many doors are on the P1 plan?")
    assert isinstance(before, Query) and before.storey == "P1"  # unchanged
    parsed = PARSE("How many doors are in the corridor of P1?")
    assert not (isinstance(parsed, Query) and parsed.storey == "P1"), parsed

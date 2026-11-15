"""Big QA R2 services-second N1 (2026-11-15): "How long is each pipe system on P-101?" answered
only the sheet total, because the by-system words allowed only "mep" between "each" and
"system"; "How long is each plumbing system?" said "This file holds no systems", though the
sheet lists four. A discipline or pipe word before "system" still asks by system, and a length
asked of a system is its pipes' (or ducts') length."""

import pytest

from app.core.ifc_question import parse_ifc_question
from tests.test_picture_answers import _ask_p101

PER_SYSTEM = [
    "- S_PWC: 18.86 m",
    "- S_PWH_: 1.80 m",
    "- S_Regenwasser: 16.40 m",
    "- S_Schmutzwasser: 31.41 m",
    "Total length: 68.47 m",
]


@pytest.mark.parametrize(
    "text",
    [
        "How long is each pipe system on P-101?",
        "How long is each plumbing system?",
        "What is the length of each piping system?",
        "How long is each drainage system?",
        "Give the pipe length by heating system",
    ],
)
def test_a_discipline_or_pipe_word_before_system_still_asks_by_system(text: str) -> None:
    found = parse_ifc_question(text)
    assert found is not None and found.by == "system", found


@pytest.mark.parametrize(
    "text", ["How long is each pipe system on P-101?", "How long is each plumbing system?"]
)
def test_each_pipe_system_lists_each_systems_length(text: str) -> None:
    said = str(_ask_p101(text).answer)
    assert said.splitlines()[:5] == PER_SYSTEM, said
    assert "holds no systems" not in said


def test_a_length_of_each_ventilation_system_is_a_duct_length() -> None:
    found = parse_ifc_question("How long is each ventilation system?")
    assert found is not None and (found.entity, found.by) == ("duct_segment", "system"), found


def test_a_count_of_systems_is_still_the_systems() -> None:
    found = parse_ifc_question("How many plumbing systems are there?")
    assert found is not None and found.entity == "system" and found.by is None, found

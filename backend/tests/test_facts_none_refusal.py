"""Big QA R2 services row 7 (2026-11-15): "How many fire dampers are on the ground floor?" on the
DigitalHub services project said 5 (the ventilation model), but the answer card opened on the
architecture model's "No dampers found in this file (not available in it).", a words answer
under the count. A count asked of a file that holds none of the thing is a refusal with those
same words, so the card skips it; a listing ("Which ... are present?") or a yes/no keeps its
text, since there the words are the answer."""

from test_ifc_fact_answer import FILE, SHEET
from test_review_ask_facts import asked

from app.core.answering.facts import FACTS, answer_from_facts
from app.core.answering.model import Answer, Question


def answer(text: str) -> Answer:
    found = answer_from_facts(Question(id=1, file=FILE, text=text), SHEET, 0.0)
    assert found is not None, text
    return found


def test_a_count_of_a_thing_the_file_holds_none_of_is_refused_in_its_own_words() -> None:
    for text, words in (
        ("How many beams are there?", "No beams found in this file (not available in it)."),
        ("What is the number of beams?", "No beams found in this file (not available in it)."),
        (
            "How many electrical components are there?",
            "This file holds no electrical elements: not available in it.",
        ),
    ):
        found = answer(text)
        assert found.method == "refused:not-in-drawing" and found.abstain, (text, found)
        assert found.answer is None and found.explanation == words, (text, found)


def test_a_listing_or_a_yes_no_keeps_its_words() -> None:
    for text in (
        "Which beams are in this building?",
        "Are there any beams?",
        "What electrical components are present in the building?",
    ):
        found = answer(text)
        assert found.method == FACTS and "not available" in str(found.answer), (text, found)


def test_the_drawing_ask_says_the_files_own_words() -> None:
    found = asked("How many electrical components are there?", facts=lambda: SHEET)
    assert found.refusal is not None
    assert found.refusal.code == "not-in-drawing"
    assert found.refusal.text == "This file holds no electrical elements: not available in it."

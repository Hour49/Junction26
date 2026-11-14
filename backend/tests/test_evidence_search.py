"""The pure parts of an evidence search (decision 0012): how a description is cut into passages,
passage ids, a passage ranking as a file ranking, the words of a query, and snippets."""

from typing import Any

import pytest

from app.core.evidence.chunks import PASSAGE_CHARS, pack, passages
from app.core.evidence.model import EvidenceSource, Passage, sources
from app.core.evidence.search import first_per_file, parsed, passage_id, snippet, terms, words
from app.core.ingest.model import FileStatus, ProjectStatus


def source(
    detail: str = "", visible_text: str = "", why: str | None = None, **register: Any
) -> EvidenceSource:
    triage: dict[str, Any] = {
        "class": "not_drawing",
        "p_plan": 0.1,
        "method": "test",
        "description": {
            "text": "A brick house seen from the south.",
            "subject": "south facade",
            "model": "test",
            "what_it_is": "photograph",
            "shows_building": True,
            "visible_text": visible_text,
            "detail": detail,
        },
    }
    if why is not None:
        triage["relevance"] = {"verdict": "related", "why": why, "judge": "test"}
    if register:
        triage["register"] = {
            "has_floor_plan": False,
            "photo_of_sheet": False,
            "scale_shown": "none",
            "quality": "good",
            "method": "test",
            **register,
        }
    file = FileStatus.model_validate(
        {"id": "f7", "path": "a.jpg", "size": 1, "state": "set_aside", "triage": triage}
    )
    status = ProjectStatus(
        id="p1", name="a.zip", state="done", created_at="2026-11-14T00:00:00+00:00", files=(file,)
    )
    (found,) = sources(status)
    return found


# ---------------------------------------------------------------- passages


def test_the_summary_is_the_kind_in_words_the_subject_and_the_text_not_the_judges_why() -> None:
    (summary,) = passages(source(why="Same address as the plans."))
    assert summary == Passage(
        part="summary", n=1, text="photograph. south facade. A brick house seen from the south."
    )
    (elevation,) = passages(source(kind="site_plan_or_map"))
    assert elevation.text.startswith("site plan or map. south facade.")  # the register's kind


def test_detail_is_cut_at_sentence_ends_and_printed_text_at_line_ends() -> None:
    sentence = "x" * 299 + "."
    found = passages(source(detail=f"{sentence} {sentence} Short one.", visible_text="A-12\n1:100"))
    assert [(p.part, p.n) for p in found] == [
        ("summary", 1),
        ("detail", 1),
        ("detail", 2),
        ("visible_text", 1),
    ]
    assert found[1].text == sentence  # two would be 601 characters
    assert found[2].text == f"{sentence} Short one."
    assert found[3].text == "A-12\n1:100"  # lines stay lines


def test_a_piece_longer_than_a_passage_is_cut_and_nothing_is_lost() -> None:
    long = "y" * (PASSAGE_CHARS * 2 + 10)
    found = pack(["ab", long, "cd"], " ")
    assert found == ["ab", "y" * PASSAGE_CHARS, "y" * PASSAGE_CHARS, "y" * 10 + " cd"]
    assert all(len(text) <= PASSAGE_CHARS for text in found)
    assert pack(["", "  "], " ") == []


# ---------------------------------------------------------------- ids


@pytest.mark.parametrize(
    ("found", "expected"),
    [
        ("f7-summary", ("f7", "summary", 1)),
        ("f7", ("f7", "summary", 1)),  # a file id is its summary
        (" f7-detail-2 ", ("f7", "detail", 2)),
        ("f12-visible_text-1", ("f12", "visible_text", 1)),
        ("f7-detail", None),
        ("f7-detail-0", None),
        ("f7-summary-1", None),
        ("7", None),
        ("f7-other-1", None),
        ("", None),
    ],
)
def test_a_passage_or_file_id_parses_and_anything_else_is_none(
    found: str, expected: tuple[str, str, int] | None
) -> None:
    assert parsed(found) == expected


def test_passage_ids_round_trip() -> None:
    for passage in passages(source(detail="One. Two.", visible_text="A")):
        made = passage_id("f7", passage)
        assert parsed(made) == ("f7", passage.part, passage.n)


def test_a_passage_ranking_becomes_the_first_files_with_their_best_passage() -> None:
    ranking = ["f2-detail-1", "f1-summary", "f2-summary", "f3-summary", "f4-summary"]
    assert first_per_file(ranking, 3) == [
        ("f2", "f2-detail-1"),
        ("f1", "f1-summary"),
        ("f3", "f3-summary"),
    ]
    assert first_per_file([], 3) == []


# ---------------------------------------------------------------- words and snippets


def test_a_word_is_two_letters_or_digits_or_more_and_underscores_split() -> None:
    assert words("Is a_b the  SOUTH facade? 1:100 é") == ["is", "the", "south", "facade", "100"]


def test_terms_are_the_query_words_the_passage_holds_without_common_ones() -> None:
    passage = "The south facade is red brick."
    assert terms("Is there a photo of the south facade?", passage) == ("south", "facade")
    assert terms("kissa", passage) == ()


def test_a_snippet_is_short_starts_near_the_match_and_cuts_at_words() -> None:
    text = " ".join(f"word{n}" for n in range(200)) + " brick wall " + "tail " * 50
    found = snippet(text, ["brick"])
    assert len(found) <= 300
    assert "brick" in found
    assert found.startswith("...") and found.endswith("...")
    assert snippet("Short text.", ["brick"]) == "Short text."
    assert snippet(text, []).startswith("word0 ")

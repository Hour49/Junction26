"""Scoring against the questions of the sealed split (`score --against all|dev|eval`): coverage,
and accuracy on the answered questions only."""

import pytest

from stoa_eval.coverage import CoverageScore, Labeller, load_answers, score_all
from stoa_eval.families import group_of
from stoa_eval.models import Answer, NumberedQuestion, Question
from stoa_eval.scoring import score
from stoa_eval.selection import SelectionParams, annotate, select
from tests.factories import make_questions, oracle_answer, sealed_groups

ROWS: list[tuple[int, Question]] = list(enumerate(make_questions(), 1))
SEALED = sealed_groups(ROWS)
SELECTION = select(ROWS, SelectionParams(), SEALED)
# what the split files hold: every question with its id, labelled dev or eval
LABELLED: list[tuple[NumberedQuestion, str]] = [
    (
        NumberedQuestion(**question.model_dump(), id=line),
        "eval" if group_of(question.path) in SEALED else "dev",
    )
    for line, question in ROWS
]


def run(answers: list[Answer]) -> CoverageScore:
    return score_all(LABELLED, load_answers(enumerate(answers, 1)))


def test_labels_and_split_match_the_golden_annotation() -> None:
    label = Labeller()
    pool = annotate(ROWS, SEALED)
    for (question, split), item in zip(LABELLED, pool, strict=True):
        assert tuple(label(question)) == (item.source, item.language, item.template)
        assert (split == "eval") == (item.split == "holdout")
    split_of = {question.id: split for question, split in LABELLED}
    assert all(
        split_of[item.id] == ("eval" if item.split == "holdout" else "dev")
        for item in SELECTION.items
    )
    result = run([])
    assert result.by_split["dev"].n == sum(item.split == "dev" for item in pool)
    assert result.by_split["eval"].n == sum(item.split == "holdout" for item in pool) > 0


def test_coverage_and_accuracy_on_the_answered() -> None:
    answers = [oracle_answer(line, question) for line, question in ROWS[:6]]
    answers += [oracle_answer(line, question, value=-1) for line, question in ROWS[6:8]]
    answers += [
        oracle_answer(line, question).model_copy(update={"answer": None})
        for line, question in ROWS[8:10]
    ]
    result = run(answers)
    total = result.questions
    assert (total.n, total.answered, total.correct) == (len(ROWS), 8, 6)
    assert total.coverage == pytest.approx(8 / len(ROWS))
    assert total.accuracy == pytest.approx(6 / 8)
    assert result.by_reason == {"ok": 6, "wrong_value": 2}
    assert result.cost_total_usd == pytest.approx(0.10)  # null answers still cost
    assert result.cost_mean_usd == pytest.approx(0.01)
    assert result.evidence_coverage == 0.0


def test_one_row_per_template_most_answered_first() -> None:
    doors = [(line, q) for line, q in ROWS if q.question.startswith("How many doors")]
    result = run([oracle_answer(line, question) for line, question in doors])
    first = result.by_template[0]
    assert (first.source, first.type, first.language) == ("cubicasa5k", "count", "en")
    assert first.template == "How many doors are shown on this floor plan?"
    assert (first.n, first.answered, first.correct, first.accuracy) == (6, 6, 6, 1.0)
    saunas = next(row for row in result.by_template if "saunas" in row.template)
    assert (saunas.n, saunas.answered, saunas.coverage, saunas.accuracy) == (6, 0, 0.0, None)
    room = "What is the net floor area of room"
    assert [row.n for row in result.by_template if row.template.startswith(room)] == [5]
    assert sum(row.n for row in result.by_template) == len(ROWS)
    assert result.by_source_type["cubicasa5k/count"].answered == 6


def test_missing_is_wrong_only_against_the_golden_set() -> None:
    golden = SELECTION.items
    by_id = dict(ROWS)
    answers = [oracle_answer(item.id, by_id[item.id]) for item in golden[1:]]  # first one skipped
    golden_mode = score(golden, answers)
    assert golden_mode.overall.correct == len(golden) - 1
    assert golden_mode.by_reason["missing"] == 1
    all_mode = run(answers)
    assert all_mode.questions.accuracy == 1.0
    assert all_mode.questions.answered == len(golden) - 1
    assert "missing" not in all_mode.by_reason


def test_text_answers_are_listed_for_review_and_extra_ids_reported() -> None:
    text = [(line, q) for line, q in ROWS if q.type == "text"][:2]
    answers = [oracle_answer(line, question) for line, question in text]
    answers.append(oracle_answer(9999, text[0][1]))
    result = run(answers)
    reviewed = [(review.id, review.exact_match) for review in result.needs_review]
    assert reviewed == [(text[0][0], True), (text[1][0], True)]
    assert result.extra_answer_ids == [9999]
    assert result.cost_total_usd == pytest.approx(0.02)  # the extra answer isn't counted


def test_repeated_answer_ids_fail() -> None:
    line, question = ROWS[0]
    with pytest.raises(ValueError, match="repeats id 1"):
        load_answers(enumerate([oracle_answer(line, question), oracle_answer(line, question)], 1))
    assert len(load_answers(enumerate([oracle_answer(line, question)], 1))) == 1

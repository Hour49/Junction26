"""Split text claims derived from gold answers (ifc-eval brief), on made-up data."""

import json
from pathlib import Path

import pytest

from stoa_eval.cli import main
from stoa_eval.jsonl import read_jsonl
from stoa_eval.models import Answer, NumberedQuestion, TextClaims
from stoa_eval.text_claims_dev import (
    derive,
    family_of,
    names_of,
    numbers_of,
    score_split_claims,
    write_text_answers,
)
from stoa_eval.text_scoring import mentions
from tests.factories import make_questions, read_json, write_questions


@pytest.mark.parametrize(
    ("text", "golden", "extended"),
    [
        ("10,957 pipes", [("count", 957)], [("count", 10957)]),
        ("31.5 cu m", [], [("volume", 31.5)]),  # golden reads no number here
        ("12 m³ of concrete", [("count", 12)], [("volume", 12)]),
        ("45.1% and 54 %", [("count", 54)], [("percent", 45.1), ("percent", 54)]),
        ("1,5 m", [("length", 1.5)], [("length", 1.5)]),  # a decimal comma either way
    ],
)
def test_extended_mentions_leave_the_golden_reading_alone(
    text: str, golden: list[tuple[str, float]], extended: list[tuple[str, float]]
) -> None:
    assert [(m.kind, m.value) for m in mentions(text)] == golden
    assert [(m.kind, m.value) for m in mentions(text, extended=True)] == extended


def test_numbers_claim_each_quantity_once_in_its_canonical_unit() -> None:
    claims = numbers_of("Walls: 1,111.8 cu ft (31.48 cu m) in 4 walls; rooms 97 sq m and 96 sq m")
    assert [(c.unit, c.value) for c in claims] == [
        ("m3", pytest.approx(31.48, rel=0.01)),  # the restatement in m3 is dropped
        ("m2", 97),
        ("m2", 96),  # same unit, close values: both kept
        ("count", 4),
    ]


def test_names_are_the_listed_labels_that_name_something() -> None:
    gold = (
        "No, not all of them.\n- Basiswand:STB 25.0 (ext): 370 mm\n- Total thickness: 370 mm\n"
        "- Kitchen: 12 sq m\n- Space 4: 3 sq m\n- Level 2: 3 rooms\n  Approximate gross area: 9\n"
        "Header line:\n"
    )
    assert [c.name for c in names_of(gold)] == ["no", "Basiswand:STB 25.0", "Kitchen", "Space 4"]
    unavailable = names_of("The information is not directly available in the BIM model.")
    assert [c.name for c in unavailable] == ["not available"]


def test_family_is_the_models_discipline() -> None:
    assert family_of("data/ifc_bench/house_two_plumbing.ifc") == "ifc_bench/plumbing"
    assert family_of("data/cubicasa5k/plan-1.png") == "cubicasa5k"


def row(id_: int, answer: str, path: str = "data/ifc_bench/a_arc.ifc") -> NumberedQuestion:
    return NumberedQuestion(id=id_, path=path, question="q", answer=answer, unit=None, type="text")


def test_split_claims_judge_answered_questions_only() -> None:
    rows = [
        row(1, "Kitchen: 12.5 sq m, 3 doors"),
        row(2, "Wand A: 200 mm", "data/ifc_bench/a_str.ifc"),
        row(3, "No."),
        row(4, "nothing here"),  # nothing to claim
    ]
    claims = derive(rows, "ifc_bench")
    assert [line.id for line in claims] == [1, 2, 3]
    answers: dict[int, str | float | None] = {1: "kitchen 12.4 m2 with three doors", 2: "0.2 m"}
    score = score_split_claims([(r, "dev") for r in rows], answers, claims, "sha")
    by_id = {item.id: item for item in score.items}
    assert by_id[1].passed  # unit converted, 0.8% off, the count as a word
    assert not by_id[2].passed and by_id[2].numbers_matched == 1  # the name is missing
    assert score.unanswered == 1 and 3 not in by_id
    assert score.by_family == {
        "ifc_bench/arc": score.passed.model_copy(update={"n": 1, "correct": 1, "accuracy": 1.0}),
        "ifc_bench/str": score.passed.model_copy(update={"n": 1, "correct": 0, "accuracy": 0.0}),
    }


def test_written_answers_are_answer_v1(tmp_path: Path) -> None:
    out = tmp_path / "answers.jsonl"
    write_text_answers({7: "b", 3: "a"}, out, method="ifc-facts", cost_usd=0.001)
    lines = [answer for _, answer in read_jsonl(out, Answer)]
    assert [(a.id, a.answer, a.method, a.cost_usd) for a in lines] == [
        (3, "a", "ifc-facts", 0.001),
        (7, "b", "ifc-facts", 0.001),
    ]


def test_text_claims_and_dev_score_end_to_end(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    questions = write_questions(tmp_path / "questions.jsonl", make_questions())
    split = tmp_path / "split"
    assert main(["split", "--questions", str(questions), "--out-dir", str(split)]) == 0
    assert main(["text-claims", "--split-dir", str(split)]) == 0
    claims = [line for _, line in read_jsonl(split / "dev_text_claims.jsonl", TextClaims)]
    dev = [json.loads(line) for line in (split / "dev.jsonl").read_text().splitlines()]
    assert {line.id for line in claims} == {
        r["id"] for r in dev if r["type"] == "text" and r["path"].startswith("data/ifc_bench/")
    }
    out = tmp_path / "oracle.json"
    oracle = split / "dev_text_oracle.jsonl"
    args = ["score", str(oracle), "--against", "dev", "--split-dir", str(split)]
    assert main([*args, "--no-record", "--out", str(out)]) == 0
    assert "text by claims" in capsys.readouterr().out
    result = read_json(out)["text_claims"]
    assert result["passed"]["correct"] == result["passed"]["n"] == len(claims) > 0

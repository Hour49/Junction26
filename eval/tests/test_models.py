"""The answer format (answer_v1): the committed JSON Schema matches the models, and the models
refuse malformed answers while accepting good ones."""

from typing import Any

import pytest
from pydantic import ValidationError

from stoa_eval.models import SCHEMA_DIR, Answer, Question, render_schemas


def test_committed_schemas_match_the_models() -> None:
    rendered = render_schemas()
    committed = {path.name for path in SCHEMA_DIR.glob("*.schema.json")}
    assert committed == set(rendered), "run `python -m stoa_eval schema` in eval/"
    for name, text in rendered.items():
        assert (SCHEMA_DIR / name).read_text(encoding="utf-8") == text, (
            f"{name} is stale: run `python -m stoa_eval schema` in eval/"
        )


GOOD: dict[str, Any] = {
    "id": 7,
    "answer": 12.5,
    "unit": "m2",
    "evidence": [{"file": "data/cubicasa5k/plan-1.png", "page": 1, "box": [0.1, 0.2, 0.3, 0.4]}],
    "method": "vision",
    "cost_usd": 0.002,
    "latency_s": 1.5,
}


def test_a_good_answer_parses() -> None:
    answer = Answer.model_validate(GOOD)
    assert answer.evidence[0].box == (0.1, 0.2, 0.3, 0.4)
    assert Answer.model_validate({**GOOD, "answer": None, "unit": None, "evidence": []})


@pytest.mark.parametrize(
    "change",
    [
        {"answer": True},  # a bool is not a count
        {"unit": "sqm"},
        {"evidance": []},
        {"method": ""},
        {"cost_usd": -0.1},
        {"id": 0},
        {"evidence": [{"file": "f", "page": 1, "box": [0.1, 0.2, 1.3, 0.4]}]},
        {"evidence": [{"file": "f", "page": 1, "box": [0.5, 0.2, 0.3, 0.4]}]},
        {"evidence": [{"file": "f", "page": 0, "box": [0.1, 0.2, 0.3, 0.4]}]},
    ],
)
def test_a_bad_answer_is_refused(change: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        Answer.model_validate({**GOOD, **change})


def test_a_question_answer_must_fit_its_type() -> None:
    base = {"path": "data/a/b.png", "question": "q", "unit": "count", "type": "count"}
    assert Question.model_validate({**base, "answer": 3}).answer == 3
    with pytest.raises(ValidationError, match="count question"):
        Question.model_validate({**base, "answer": "3"})
    with pytest.raises(ValidationError, match="count question"):
        Question.model_validate({**base, "answer": 3.5})

"""Each scoring rule as a pass/fail pair, then the report built from them."""

import pytest

from stoa_eval.models import Answer, AnswerValue, Evidence, QuestionType, Unit
from stoa_eval.scoring import format_table, judge, normalise_text, score
from tests.factories import golden_item


def answer(
    value: AnswerValue | None,
    unit: Unit | None,
    *,
    id_: int = 1,
    evidence: list[Evidence] | None = None,
    cost: float = 0.0,
    latency: float = 0.0,
) -> Answer:
    return Answer(
        id=id_,
        answer=value,
        unit=unit,
        evidence=evidence or [],
        method="test",
        cost_usd=cost,
        latency_s=latency,
    )


def test_count_must_be_exact() -> None:
    gold = golden_item(5, "count", "count")
    assert judge(gold, answer(5, "count")) == "ok"
    assert judge(gold, answer(5.0, "count")) == "ok"
    assert judge(gold, answer(6, "count")) == "wrong_value"
    assert judge(gold, answer(5.4, "count")) == "wrong_value"


MEASURES: list[tuple[QuestionType, Unit]] = [("area", "m2"), ("length", "m"), ("volume", "m3")]


@pytest.mark.parametrize(("type_", "unit"), MEASURES)
def test_measure_within_two_percent(type_: QuestionType, unit: Unit) -> None:
    gold = golden_item(100.0, unit, type_)
    assert judge(gold, answer(101.9, unit)) == "ok"
    assert judge(gold, answer(98.1, unit)) == "ok"
    assert judge(gold, answer(102.0, unit)) == "ok"  # the boundary counts
    assert judge(gold, answer(102.1, unit)) == "wrong_value"
    assert judge(gold, answer(97.9, unit)) == "wrong_value"


def test_unit_must_match() -> None:
    area = golden_item(10.0, "m2", "area")
    assert judge(area, answer(10.0, "m2")) == "ok"
    assert judge(area, answer(10.0, "m3")) == "unit_mismatch"
    assert judge(area, answer(10.0, None)) == "unit_mismatch"
    count = golden_item(3, "count", "count")
    assert judge(count, answer(3, None)) == "unit_mismatch"


def test_only_m_ft_and_m2_ft2_convert() -> None:
    assert judge(golden_item(1000, "ft2", "area"), answer(92.9, "m2")) == "ok"  # 999.97 ft2
    assert judge(golden_item(1000, "ft2", "area"), answer(90.0, "m2")) == "wrong_value"
    assert judge(golden_item(10.0, "m2", "area"), answer(107.6, "ft2")) == "ok"
    assert judge(golden_item(10.0, "m", "length"), answer(32.8, "ft")) == "ok"
    assert judge(golden_item(10.0, "ft", "length"), answer(3.048, "m")) == "ok"
    assert judge(golden_item(10.0, "m", "length"), answer(10.0, "ft")) == "wrong_value"
    assert judge(golden_item(10.0, "m3", "volume"), answer(10.0, "m2")) == "unit_mismatch"


def test_missing_answer_is_wrong() -> None:
    gold = golden_item(5, "count", "count")
    assert judge(gold, None) == "missing"
    assert judge(gold, answer(None, None)) == "missing"
    assert judge(gold, answer(5, "count")) == "ok"


def test_number_and_text_dont_mix() -> None:
    assert judge(golden_item(5, "count", "count"), answer("5", "count")) == "wrong_type"
    assert judge(golden_item("5", None, "text"), answer(5, None)) == "wrong_type"
    assert judge(golden_item("5", None, "text"), answer("5", None)) == "ok"


def test_text_matches_after_normalising() -> None:
    gold = golden_item("The Fieldhouse", None, "text")
    assert judge(gold, answer("  the   FIELDHOUSE.\n", None)) == "ok"
    assert judge(gold, answer("Fieldhouse", None)) == "wrong_value"
    assert normalise_text("A  b. ") == "a b"
    assert judge(golden_item("12 m2", None, "text"), answer("12 m²", None)) == "ok"  # NFKC


def test_score_report() -> None:
    golden = [
        golden_item(5, "count", "count", id_=1, split="dev"),
        golden_item(50.0, "m2", "area", id_=2, split="holdout"),
        golden_item("ArchiCAD", None, "text", id_=3, split="holdout", source="ifc_bench"),
        golden_item(7, "count", "count", id_=4, split="dev"),
    ]
    box = Evidence(file="data/swiss_dwellings/plan-1.pdf", page=1, box=(0.1, 0.1, 0.2, 0.2))
    answers = [
        answer(5, "count", id_=1, evidence=[box], cost=0.01, latency=2.0),
        answer(55.0, "m2", id_=2, cost=0.03, latency=4.0),
        answer("archicad", None, id_=3, cost=0.02, latency=3.0),
        answer(1, "count", id_=99),
    ]
    result = score(golden, answers)
    assert (result.overall.correct, result.overall.n) == (2, 4)
    assert (result.numeric.correct, result.numeric.n) == (1, 3)
    assert (result.text.correct, result.text.n) == (1, 1)
    assert result.by_split["dev"].correct == 1
    assert result.by_split["holdout"].correct == 1
    assert result.by_source_type["swiss_dwellings/area"].accuracy == 0.0
    assert result.by_reason == {"missing": 1, "ok": 2, "wrong_value": 1}
    assert result.answered == 3
    assert result.extra_answer_ids == [99]
    assert result.evidence_coverage == 0.25
    assert result.cost_total_usd == pytest.approx(0.06)
    assert result.cost_mean_usd == pytest.approx(0.02)
    assert result.latency_mean_s == pytest.approx(3.0)
    assert [(r.id, r.exact_match) for r in result.needs_review] == [(3, True)]
    assert "overall      2/4     50.0%" in format_table(result)


def test_repeated_answer_ids_fail() -> None:
    golden = [golden_item(5, "count", "count")]
    with pytest.raises(ValueError, match="repeat ids"):
        score(golden, [answer(5, "count"), answer(6, "count")])
    assert score(golden, [answer(5, "count")]).overall.correct == 1

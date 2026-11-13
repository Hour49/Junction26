"""Part 2 slices outside the headline: extras (paraphrase, unanswerable, conflict lines) and the
answer_v1.1 fields (abstain, confidence calibration), on made-up lines."""

from typing import Any

import pytest
from pydantic import ValidationError

from stoa_eval.baselines import oracle
from stoa_eval.extras_scoring import bucket_of, format_slices, score_golden
from stoa_eval.models import Answer, ExtraItem, GoldenItem
from stoa_eval.scoring import score
from tests.factories import golden_item

GOLDEN = [
    golden_item(7, "count", "count", id_=1, source="cubicasa5k"),
    golden_item(12.5, "m2", "area", id_=2),
    golden_item(3, "count", "count", id_=3, source="cubicasa5k"),
]


def extra(kind: str, id_: int, **change: Any) -> ExtraItem:
    base: dict[str, Any] = {
        "path": "data/cubicasa5k/plan-1.pdf", "question": "q", "answer": 7, "unit": "count",
        "type": "count", "id": id_, "source": "cubicasa5k", "language": "en", "template": "t",
        "group": "cubicasa5k/plan-1", "split": "dev", "kind": kind, "origin_id": None,
        "expect": {"answer": 7}, "why": None,
    }  # fmt: skip
    if kind == "paraphrase":
        base |= {"origin_id": 1, "style": "reworded"}
    if kind == "unanswerable":
        base |= {"answer": None, "unit": None, "type": "unanswerable", "expect": {"abstain": True},
                 "why": "no scale", "template": "unanswerable/scale", "style": "scale"}  # fmt: skip
    if kind == "conflict":
        expect = {"answer": 12.5, "conflict_values": [12.5, 13.4]}
        base |= {"answer": 12.5, "unit": "m2", "type": "area", "expect": expect,
                 "path": "data/swiss_dwellings/x.pdf", "source": "swiss_dwellings"}  # fmt: skip
    return ExtraItem.model_validate(base | change)


def answer(id_: int, value: Any, unit: str | None = "count", **extra_fields: Any) -> Answer:
    return Answer.model_validate(
        {
            "id": id_,
            "answer": value,
            "unit": unit,
            "evidence": [],
            "method": "t",
            "cost_usd": 0,
            "latency_s": 0,
            **extra_fields,
        }
    )


def values(*pairs: tuple[float, str]) -> list[dict[str, Any]]:
    return [{"value": v, "unit": u, "method": "m", "file": "f"} for v, u in pairs]


EXTRAS = [
    extra("paraphrase", 1_000_001),  # origin 1
    extra("paraphrase", 1_000_002, origin_id=3, answer=3, expect={"answer": 3}, style="typo"),
    extra("unanswerable", 1_000_003),
    extra("unanswerable", 1_000_004),
    extra("conflict", 1_001_001),
    extra("conflict", 1_001_002),
]


def scored(answers: list[Answer], extras: list[ExtraItem] = EXTRAS) -> Any:
    ids = {line.id for line in extras}
    base = score(GOLDEN, [a for a in answers if a.id not in ids])
    return score_golden(base, GOLDEN, answers, extras, "sha")


def test_extras_damaged_copy_scores_exactly() -> None:
    answers = [
        answer(1, 7),  # origin 1 right, paraphrase 1_000_001 right
        answer(1_000_001, 7),
        answer(3, 3),  # origin 3 right, paraphrase 1_000_002 wrong
        answer(1_000_002, 4),
        answer(1_000_003, 10.0, "m2", abstain=True),  # abstains, with its best estimate
        answer(1_000_004, 10.0, "m2"),  # answers anyway
        # both values shown (one in ft2, within 2% after conversion) but the answer is wrong
        answer(1_001_001, 13.4, "m2", conflicts=values((12.5, "m2"), (144.24, "ft2"))),
        # the answer is right but only one value is shown twice
        answer(1_001_002, 12.6, "m2", conflicts=values((12.5, "m2"), (12.5, "m2"))),
    ]
    result = scored(answers)
    extras = result.extras
    assert (extras.paraphrase.correct, extras.paraphrase.n) == (1, 2)
    assert (extras.paraphrase_origin.correct, extras.paraphrase_origin.n) == (2, 2)
    assert extras.paraphrase_gap == pytest.approx(-0.5)
    assert extras.paraphrase_pairs == {"both": 1, "origin_only": 1}
    assert (extras.unanswerable.correct, extras.unanswerable.n) == (1, 2)
    assert (extras.conflict.correct, extras.conflict.n) == (0, 2)
    assert (extras.conflict_values_shown.correct, extras.conflict_answer_right.correct) == (1, 1)
    assert extras.by_kind_source["paraphrase/cubicasa5k"].correct == 1
    assert [item.detail for item in extras.items][2:4] == ["abstained", "answered"]
    # the headline only sees the golden questions; extras answers are not "extra answers ignored"
    assert result.overall.n == 3 and result.extra_answer_ids == [] and result.answered == 2
    assert result.answer_v1_1 is None  # no golden answer carries confidence or abstain
    printed = format_slices(result)
    assert "gap -50.0 pts" in printed and "answer_v1.1" not in printed


def test_a_missing_line_fails_every_kind() -> None:
    extras = scored([]).extras
    assert extras.paraphrase.correct == extras.unanswerable.correct == extras.conflict.correct == 0
    assert extras.paraphrase_gap == 0.0  # both 0%
    assert [item.detail for item in extras.items][:3] == ["missing", "missing", "missing"]


def test_the_oracle_passes_every_slice() -> None:
    result = scored(oracle(GOLDEN, EXTRAS))
    extras = result.extras
    assert result.overall.accuracy == 1.0
    for tally in (extras.paraphrase, extras.paraphrase_origin, extras.unanswerable,
                  extras.conflict):  # fmt: skip
        assert tally.accuracy == 1.0
    v11 = result.answer_v1_1
    assert v11.abstained == 0 and v11.not_abstained.accuracy == 1.0
    assert v11.calibration[-1].n == 3 and v11.calibration[-1].accuracy == 1.0


def test_extras_refuse_clashes_repeats_and_orphans() -> None:
    with pytest.raises(ValueError, match="also golden question ids"):
        scored([], [extra("paraphrase", 1_000_001).model_copy(update={"id": 2})])
    with pytest.raises(ValueError, match="repeat ids"):
        scored([], [EXTRAS[0], EXTRAS[0]])
    with pytest.raises(ValueError, match="origin_id not in the golden set"):
        scored([], [extra("paraphrase", 1_000_001, origin_id=99)])


@pytest.mark.parametrize(
    ("confidence", "bucket"),
    [(0.0, 0), (0.19, 0), (0.2, 1), (0.4, 2), (0.6, 3), (0.7999, 3), (0.8, 4), (1.0, 4)],
)
def test_confidence_buckets_include_their_lower_edge(confidence: float, bucket: int) -> None:
    assert bucket_of(confidence) == bucket


def test_answer_v11_abstain_and_calibration() -> None:
    answers = [
        answer(1, 7, confidence=0.9),  # right, bucket 4
        answer(2, 20.0, "m2", confidence=0.3, abstain=True),  # wrong estimate, abstained
        answer(3, 3, abstain=False),  # right, no confidence
    ]
    v11 = scored(answers, []).answer_v1_1
    assert (v11.answers, v11.abstained, v11.abstain_rate) == (3, 1, pytest.approx(1 / 3))
    assert (v11.not_abstained.correct, v11.not_abstained.n) == (2, 2)
    assert (v11.abstained_tally.correct, v11.abstained_tally.n) == (0, 1)
    assert v11.with_confidence == 2
    buckets = {(b.low, b.high): (b.n, b.correct, b.mean_confidence) for b in v11.calibration}
    assert buckets[(0.2, 0.4)] == (1, 0, pytest.approx(0.3))
    assert buckets[(0.8, 1.0)] == (1, 1, pytest.approx(0.9))
    assert buckets[(0.0, 0.2)] == (0, 0, None)
    assert "[0.8, 1.0]" in format_slices(scored(answers, []))


def test_review7_and_review10_lines_parse() -> None:
    line = extra("unanswerable", 1_000_061, origin_id=None)
    assert line.type == "unanswerable" and line.style == "scale"
    conflict = extra("conflict", 1_001_001, origin_id=89373)  # a reworded dataset question
    assert conflict.expect.conflict_values == [12.5, 13.4]
    text = extra("paraphrase", 1_000_004, answer="ArchiCAD", unit=None, type="text",
                 expect={"answer": "ArchiCAD"})  # fmt: skip
    assert text.answer == "ArchiCAD"


@pytest.mark.parametrize(
    ("kind", "change", "message"),
    [
        ("paraphrase", {"origin_id": None}, "names its origin_id"),
        ("paraphrase", {"expect": {"answer": 8}}, "expects its own answer"),
        ("paraphrase", {"answer": 7.5, "expect": {"answer": 7.5}}, "count question"),
        ("paraphrase", {"style": "scale"}, "style 'scale'"),
        ("paraphrase", {"type": "unanswerable"}, "type is unanswerable exactly"),
        ("paraphrase", {"id": 127_044}, "greater than or equal"),
        ("paraphrase", {"split": "holdout"}, "dev"),
        ("unanswerable", {"answer": 3, "unit": "count"}, "answer and unit null"),
        ("unanswerable", {"expect": {"abstain": False}}, "only abstain: true"),
        ("unanswerable", {"why": None}, "says why"),
        ("unanswerable", {"type": "area"}, "type is unanswerable exactly"),
        ("conflict", {"expect": {"answer": 12.5}}, "need them"),
        ("conflict", {"expect": {"answer": 12.5, "conflict_values": [12.5]}}, "at least 2"),
        ("conflict", {"group": None}, "valid string"),
    ],
)  # fmt: skip
def test_a_bad_extras_line_is_refused(kind: str, change: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        extra(kind, 1_000_001 if kind != "conflict" else 1_001_001, **change)


V11: dict[str, Any] = {
    "id": 7, "answer": 12.5, "unit": "m2",
    "evidence": [{"file": "f", "page": 1, "box": [0.1, 0.2, 0.3, 0.4],
                  "polygon": [[0.1, 0.2], [0.3, 0.2], [0.3, 0.4]],
                  "global_id": "2O2Fr$t4X7Zf8NOew3FLOH"}],
    "method": "vision", "cost_usd": 0.002, "latency_s": 1.5,
    "confidence": 0.6, "abstain": False,
    "conflicts": [{"value": 12.5, "unit": "m2", "method": "printed_label", "file": "f", "page": 1,
                   "box": [0.1, 0.2, 0.3, 0.4]},
                  {"value": 13.4, "unit": "m2", "method": "ifc_model", "file": "f.ifc"}],
    "resolution": "the printed label wins", "explanation": "label 12.5 m2; outline 13.4 m2",
    "excluded": [{"file": "f", "page": 1, "box": [0.5, 0.5, 0.6, 0.6], "reason": "a shaft"}],
    "inputs": ["f", "f.ifc"],
}  # fmt: skip


def test_an_answer_v11_line_parses() -> None:
    parsed = Answer.model_validate(V11)
    assert parsed.conflicts is not None and parsed.conflicts[1].page is None
    assert parsed.evidence[0].global_id == "2O2Fr$t4X7Zf8NOew3FLOH"


@pytest.mark.parametrize(
    "change",
    [
        {"confidence": 1.2},
        {"abstain": "yes"},
        {"conflicts": V11["conflicts"][:1]},
        {"conflicts": None},  # a resolution without conflicts
        {"excluded": [{"file": "f", "page": 1, "box": [0.5, 0.5, 0.6, 0.6], "reason": ""}]},
        {"evidence": [{**V11["evidence"][0], "polygon": [[0.1, 0.2], [0.3, 0.2]]}]},
        {"conflicts": [{**V11["conflicts"][0], "box": [0.5, 0.2, 0.3, 0.4]}, V11["conflicts"][1]]},
    ],
)
def test_a_bad_answer_v11_line_is_refused(change: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        Answer.model_validate({**V11, **change})


def test_golden_items_stay_answerable_by_v1_lines() -> None:
    plain: GoldenItem = GOLDEN[0]
    v1 = answer(plain.id, plain.answer)
    assert v1.confidence is None and v1.abstain is None and v1.conflicts is None

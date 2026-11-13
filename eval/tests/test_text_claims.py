"""Free-text answers judged by curated claims (D52, golden-8 brief), on made-up data."""

import json
from typing import Any

import pytest
from pydantic import ValidationError

from stoa_eval.models import Answer, AnswerValue, GoldenItem, NumberClaim, TextClaims
from stoa_eval.text_scoring import (
    FT,
    INCH,
    Mention,
    has_name,
    matched_claims,
    mentions,
    score_text_claims,
)

FT2 = FT**2


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("6'-2 1/2\"", [("length", (6 * 12 + 2.5) * INCH)]),
        ("8 ft 3 1/4 in", [("length", (8 * 12 + 3.25) * INCH)]),
        ("9'-0\" wide x 11'-0\" high", [("length", 9 * FT), ("length", 11 * FT)]),
        ('41 1/2" wide', [("length", 41.5 * INCH)]),
        ('P7 - 5/8" gypsum board', [("length", 0.625 * INCH)]),  # P7 is a code
        ("4 rooms, 2,318 SF", [("area", 2318 * FT2), ("count", 4)]),
        ("about 215.4 m² over four rooms", [("area", 215.4), ("count", 4)]),
        ("2,35 m", [("length", 2.35)]),  # a decimal comma
        ("45 MIN.", [("time", 45)]),
        ("rated 1 hour", [("time", 60)]),
        ("D7 (folding), ST-4/GL-9, door 204.C, room 316's", []),  # codes, not quantities
        ("2 urinals, 1 basin", [("count", 2), ("count", 1)]),
        ("Hardware set 27", [("count", 27)]),
    ],
)
def test_mentions_read_numbers_with_their_units(
    text: str, expected: list[tuple[str, float]]
) -> None:
    found = [(mention.kind, mention.value) for mention in mentions(text)]
    assert [kind for kind, _ in found] == [kind for kind, _ in expected]
    assert [value for _, value in found] == pytest.approx([value for _, value in expected])


def claim(value: float, unit: str) -> NumberClaim:
    return NumberClaim.model_validate({"value": value, "unit": unit})


def test_claims_match_one_to_one_within_two_percent() -> None:
    area = [claim(2318, "ft2")]
    assert matched_claims(area, mentions(f"{2318 * FT2:.2f} m²")) == 1  # converted
    assert matched_claims(area, mentions(f"{2318 * 1.02} SF")) == 1  # 2% is in
    assert matched_claims(area, mentions(f"{2318 * 1.021} SF")) == 0  # 2.1% is out
    assert matched_claims(area, mentions("2318")) == 0  # a bare number is a count, not an area
    assert matched_claims([claim(3, "count")], mentions("3.0 rooms")) == 0  # counts are whole
    ones = [claim(1, "count")] * 3
    assert matched_claims(ones, mentions("1 WC, 1 basin, 1 shower")) == 3
    assert matched_claims(ones, mentions("1 WC and 2 showers")) == 1  # each mention serves once
    wide_high = [claim(9, "ft"), claim(11, "ft")]
    assert matched_claims(wide_high, mentions("11'-0\" high, 9'-0\" wide")) == 2  # any order
    assert matched_claims(wide_high, mentions("9 ft by 9 ft")) == 1
    # one mention fits both claims, the other only the first: the matching still finds both
    close = [claim(100, "m2"), claim(101.5, "m2")]
    found = [Mention("area", 100.5, "a"), Mention("area", 98.5, "b")]
    assert matched_claims(close, found) == 2


def test_names_are_whole_words_after_normalising() -> None:
    assert has_name("Material ST-4 / GL-9.", ["ST-4"]) and has_name("st 4/gl 9", ["GL-9"])
    assert has_name("It is the GYMNASIUM.", ["Gymnasium"])
    assert not has_name("F20 everywhere", ["F2"])  # not inside a longer code
    assert has_name("an aluminum sliding door", ["aluminium sliding door", "aluminum sliding door"])
    assert not has_name("anything", ["", "  "])


def golden(id_: int, answer: AnswerValue, type_: str = "text", split: str = "dev") -> GoldenItem:
    return GoldenItem.model_validate({
        "id": id_, "path": "data/opening_design/P/A-801.pdf", "question": "q", "answer": answer,
        "unit": None if type_ == "text" else "count", "type": type_, "source": "opening_design",
        "language": "en", "template": "q", "group": "opening_design/P", "split": split,
    })  # fmt: skip


def reply(id_: int, value: AnswerValue | None) -> Answer:
    return Answer(id=id_, answer=value, unit=None, evidence=[], method="t", cost_usd=0.0,
                  latency_s=0.0)  # fmt: skip


def claims(id_: int, **fields: Any) -> TextClaims:
    return TextClaims.model_validate({"id": id_, "by": "test", **fields})


GOLDEN = [
    golden(1, "4 rooms, 2318 SF"),
    golden(2, "P7 - painted gypsum"),
    golden(3, "27", split="holdout"),
    golden(4, "unclaimed"),
    golden(5, 7, "count"),
]
CLAIMS = [
    claims(1, numbers=[{"value": 4, "unit": "count"}, {"value": 2318, "unit": "ft2"}]),
    claims(2, names=[{"name": "P7"}, {"name": "painted gypsum"}]),
    claims(3, names=[{"name": "27"}]),
]


def test_text_answers_pass_when_every_claim_is_met() -> None:
    answers = {
        1: reply(1, "Four rooms: about 215.4 m² together, 2 doors"),  # converted, an extra 2
        2: reply(2, "P7 (painted)"),  # one name missing
        3: reply(3, 27),  # a bare number answering a text question reads as that number
        4: reply(4, "whatever"),
    }
    result = score_text_claims(GOLDEN, answers, CLAIMS, "sha")
    by_id = {item.id: item for item in result.items}
    assert by_id[1].passed and by_id[1].extra_numbers == 1
    assert not by_id[2].passed and (by_id[2].names_found, by_id[2].names) == (1, 2)
    assert by_id[3].passed
    assert (result.passed.correct, result.passed.n) == (2, 3)
    assert (result.numbers.correct, result.numbers.n) == (2, 2)
    assert (result.names.correct, result.names.n) == (2, 3)
    assert result.by_split["holdout"].correct == 1 and result.by_split["dev"].correct == 1
    assert result.without_claims == [4]  # golden text questions only: 5 is a count
    missing = score_text_claims(GOLDEN, {}, CLAIMS, "sha")
    assert missing.passed.correct == 0 and missing.numbers.correct == 0


def test_claims_lines_are_checked() -> None:
    with pytest.raises(ValueError, match="repeat id 1"):
        score_text_claims(GOLDEN, {}, [*CLAIMS, CLAIMS[0]], "sha")
    with pytest.raises(ValueError, match="5 is not a golden free-text question"):
        score_text_claims(GOLDEN, {}, [claims(5, names=[{"name": "7"}])], "sha")
    with pytest.raises(ValidationError, match="at least one number or name"):
        claims(1)
    with pytest.raises(ValidationError, match="whole number"):
        claims(1, numbers=[{"value": 2.5, "unit": "count"}])
    with pytest.raises(ValidationError):
        claims(1, names=[{"name": "x"}], answer="3 rooms")  # unknown key
    with pytest.raises(ValidationError):
        claims(1, numbers=[{"value": 3, "unit": "yd"}])


def test_the_claims_schema_is_generated() -> None:
    from stoa_eval.models import render_schemas

    schema = json.loads(render_schemas()["text_claims_v1.schema.json"])
    assert schema["title"] == "TextClaims_v1" and schema["additionalProperties"] is False

"""Score answers (answer_v1) against golden items with the dataset's rules.

- count: exact (5.0 equals 5).
- area, length, volume: within 2% of the golden value, relative.
- Numeric answers need the golden unit, or one converted by `CONVERSIONS` (m/ft and m2/ft2 only).
- text and other: exact after `normalise_text`; also listed under `needs_review`, because the
  dataset scores them free-form and a person has to judge near misses.
- No answer, or `answer: null`, is wrong.
"""

import unicodedata
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from typing import Literal

from pydantic import BaseModel

from .models import FREE_TEXT_TYPES, Answer, AnswerValue, GoldenItem, Question

REL_TOL = 0.02
# answer unit -> golden unit: multiply the answer by the factor. 1 ft = 0.3048 m exactly.
CONVERSIONS: dict[tuple[str, str], float] = {
    ("ft", "m"): 0.3048,
    ("m", "ft"): 1 / 0.3048,
    ("ft2", "m2"): 0.3048**2,
    ("m2", "ft2"): 1 / 0.3048**2,
}
Reason = Literal["ok", "missing", "wrong_type", "unit_mismatch", "wrong_value"]


def normalise_text(text: str) -> str:
    """NFKC, case-folded, whitespace collapsed, trailing full stops dropped."""
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split()).rstrip(" .")


def judge(gold: Question, answer: Answer | None) -> Reason:
    if answer is None or answer.answer is None:
        return "missing"
    value = answer.answer
    if gold.type in FREE_TEXT_TYPES:
        if not isinstance(value, str) or not isinstance(gold.answer, str):
            return "wrong_type"
        return "ok" if normalise_text(value) == normalise_text(gold.answer) else "wrong_value"
    if isinstance(value, str) or isinstance(gold.answer, str):
        return "wrong_type"
    if answer.unit != gold.unit:
        factor = CONVERSIONS.get((str(answer.unit), str(gold.unit)))
        if factor is None:
            return "unit_mismatch"
        value *= factor
    if gold.type == "count":
        return "ok" if value == gold.answer else "wrong_value"
    tolerance = REL_TOL * abs(gold.answer) * (1 + 1e-9)  # the 1e-9 absorbs float rounding at 2%
    return "ok" if abs(value - gold.answer) <= tolerance else "wrong_value"


class Tally(BaseModel):
    n: int
    correct: int
    accuracy: float | None


class ItemResult(BaseModel):
    id: int
    source: str
    type: str
    language: str
    split: str
    reason: Reason
    correct: bool
    has_evidence: bool
    cost_usd: float | None
    latency_s: float | None


class TextReview(BaseModel):
    id: int
    question: str
    gold: AnswerValue
    answer: AnswerValue | None
    exact_match: bool


class Score(BaseModel):
    overall: Tally
    numeric: Tally
    text: Tally
    by_split: dict[str, Tally]
    by_source_type: dict[str, Tally]
    by_reason: dict[str, int]
    answered: int
    extra_answer_ids: list[int]
    evidence_coverage: float | None
    cost_total_usd: float
    cost_mean_usd: float | None
    latency_mean_s: float | None
    needs_review: list[TextReview]
    items: list[ItemResult]


def _tally(results: Iterable[ItemResult]) -> Tally:
    marks = [result.correct for result in results]
    correct = sum(marks)
    return Tally(n=len(marks), correct=correct, accuracy=correct / len(marks) if marks else None)


def _unique_ids(ids: Iterable[int], what: str) -> None:
    repeated = sorted(id_ for id_, count in Counter(ids).items() if count > 1)
    if repeated:
        raise ValueError(f"{what} repeat ids {repeated[:10]}")


def score(golden: Sequence[GoldenItem], answers: Sequence[Answer]) -> Score:
    _unique_ids((item.id for item in golden), "golden items")
    _unique_ids((answer.id for answer in answers), "answers")
    by_id = {answer.id: answer for answer in answers}
    golden_ids = {item.id for item in golden}
    results: list[ItemResult] = []
    review: list[TextReview] = []
    for item in golden:
        answer = by_id.get(item.id)
        reason = judge(item, answer)
        results.append(
            ItemResult(
                id=item.id,
                source=item.source,
                type=item.type,
                language=item.language,
                split=item.split,
                reason=reason,
                correct=reason == "ok",
                has_evidence=bool(answer and answer.evidence),
                cost_usd=answer.cost_usd if answer else None,
                latency_s=answer.latency_s if answer else None,
            )
        )
        if item.type in FREE_TEXT_TYPES:
            review.append(
                TextReview(
                    id=item.id,
                    question=item.question,
                    gold=item.answer,
                    answer=answer.answer if answer else None,
                    exact_match=reason == "ok",
                )
            )
    groups: dict[str, list[ItemResult]] = defaultdict(list)
    for result in results:
        groups[f"{result.source}/{result.type}"].append(result)
    answered = [answer for answer in answers if answer.id in golden_ids]
    cost_total = sum(answer.cost_usd for answer in answered)
    return Score(
        overall=_tally(results),
        numeric=_tally(r for r in results if r.type not in FREE_TEXT_TYPES),
        text=_tally(r for r in results if r.type in FREE_TEXT_TYPES),
        by_split={
            split: _tally(r for r in results if r.split == split) for split in ("dev", "holdout")
        },
        by_source_type={key: _tally(group) for key, group in sorted(groups.items())},
        by_reason=dict(sorted(Counter(result.reason for result in results).items())),
        answered=len(answered),
        extra_answer_ids=sorted(by_id.keys() - golden_ids),
        evidence_coverage=(
            sum(result.has_evidence for result in results) / len(results) if results else None
        ),
        cost_total_usd=cost_total,
        cost_mean_usd=cost_total / len(answered) if answered else None,
        latency_mean_s=(
            sum(answer.latency_s for answer in answered) / len(answered) if answered else None
        ),
        needs_review=review,
        items=results,
    )


def _pct(tally: Tally) -> str:
    accuracy = "n/a" if tally.accuracy is None else f"{tally.accuracy:6.1%}"
    return f"{tally.correct:>4}/{tally.n:<4} {accuracy}"


def _optional(value: float | None, fmt: str) -> str:
    return "n/a" if value is None else format(value, fmt)


def format_table(result: Score) -> str:
    lines = [
        f"overall   {_pct(result.overall)}",
        f"numeric   {_pct(result.numeric)}",
        f"text      {_pct(result.text)}   exact match only; see needs_review in score.json",
        *(f"{split:<9} {_pct(tally)}" for split, tally in result.by_split.items()),
        "",
        f"{'source/type':<26} {'correct/n':>9}  accuracy",
        *(f"{key:<26} {_pct(tally)}" for key, tally in result.by_source_type.items()),
        "",
        "reasons   " + ", ".join(f"{reason} {n}" for reason, n in result.by_reason.items()),
        f"answered  {result.answered}, extra answers ignored {len(result.extra_answer_ids)}",
        f"evidence  {_optional(result.evidence_coverage, '.1%')} of questions have a box",
        f"cost      total ${result.cost_total_usd:.4f}, "
        f"mean ${_optional(result.cost_mean_usd, '.4f')} per answer",
        f"latency   mean {_optional(result.latency_mean_s, '.2f')} s",
    ]
    return "\n".join(lines)

"""Part 2 slices outside the headline: the extras (questions Stoa didn't write) and the answer_v1.1
fields (formats-v1-1 brief §3 and §4; Bogdan 2026-11-13 23:03).

Extras (part2_answering/extras.jsonl), per kind:
- paraphrase: right by the dataset rules (scoring.judge). Its origin question is judged on the same
  answers file, and the gap is paraphrase accuracy minus origin accuracy over the same pairs: a
  negative gap means the answering depends on the template's wording.
- unanswerable: passes when the answer line says `abstain: true`. A missing line fails.
- conflict: passes when every expected `conflict_values` entry is matched one-to-one by a value in
  the answer's `conflicts` (by the same rules as an answer, in the line's unit) and the answer
  itself is right.

answer_v1.1, on the golden questions (extras excluded): abstain rate over the answered questions,
accuracy of the best estimate on abstained and on the other answers, and a calibration table of
confidence buckets 0.2 wide (the last one includes 1.0).
"""

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import NamedTuple

from pydantic import BaseModel, ConfigDict, Field

from .models import Answer, AnswerValue, ExtraItem, GoldenItem, Question, Unit
from .scoring import Score, Tally, judge

BUCKETS = 5  # confidence buckets of 0.2


class _Reply(NamedTuple):
    answer: AnswerValue | None
    unit: Unit | None


class ExtraResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    kind: str
    source: str
    style: str | None
    passed: bool
    detail: str = Field(description="the judge's reason, or what the line missed")


class ExtrasScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    extras_sha256: str
    paraphrase: Tally
    paraphrase_origin: Tally
    paraphrase_gap: float | None
    paraphrase_pairs: dict[str, int] = Field(description="both, origin_only, paraphrase_only, ...")
    unanswerable: Tally = Field(description="correct = abstained")
    conflict: Tally = Field(description="correct = values shown and answer right")
    conflict_values_shown: Tally
    conflict_answer_right: Tally
    by_kind_source: dict[str, Tally]
    items: list[ExtraResult]


class Bucket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    low: float
    high: float
    n: int
    correct: int
    accuracy: float | None
    mean_confidence: float | None


class AnswerV11Score(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answers: int = Field(description="golden questions with an answer line")
    abstained: int
    abstain_rate: float | None
    not_abstained: Tally
    abstained_tally: Tally = Field(description="the best estimate of abstained answers, judged")
    with_confidence: int
    calibration: list[Bucket]


class GoldenScore(Score):
    """The Part 2 score with the slices outside the headline."""

    extras: ExtrasScore | None = None
    answer_v1_1: AnswerV11Score | None = None


def _tally(marks: Sequence[bool]) -> Tally:
    correct = sum(marks)
    return Tally(n=len(marks), correct=correct, accuracy=correct / len(marks) if marks else None)


def as_question(line: ExtraItem, answer: AnswerValue | None = None) -> Question:
    """The line as a dataset question with `answer` (default: its own) as the truth."""
    if line.type == "unanswerable":
        raise ValueError(f"extras line {line.id} has no answer to judge")
    return Question(
        path=line.path,
        question=line.question,
        answer=line.answer if answer is None else answer,  # pyright: ignore[reportArgumentType]
        unit=line.unit,
        type=line.type,
    )


def values_shown(line: ExtraItem, answer: Answer | None) -> bool:
    """Every expected conflict value is matched one-to-one by a value in the answer's conflicts."""
    offered = list(answer.conflicts or []) if answer else []
    for want in line.expect.conflict_values or []:
        truth = as_question(line, want)
        hit = next(
            (
                n
                for n, item in enumerate(offered)
                if judge(truth, _Reply(item.value, item.unit)) == "ok"
            ),
            None,
        )
        if hit is None:
            return False
        offered.pop(hit)
    return True


def score_extras(
    extras: Sequence[ExtraItem],
    golden: Sequence[GoldenItem],
    answers: Mapping[int, Answer],
    extras_sha256: str,
) -> ExtrasScore:
    by_id = {item.id: item for item in golden}
    clash = sorted(line.id for line in extras if line.id in by_id)
    if clash:
        raise ValueError(f"extras ids {clash[:5]} are also golden question ids")
    repeated = sorted(i for i, n in Counter(line.id for line in extras).items() if n > 1)
    if repeated:
        raise ValueError(f"extras repeat ids {repeated[:5]}")
    orphans = sorted(
        line.id for line in extras if line.kind == "paraphrase" and line.origin_id not in by_id
    )
    if orphans:
        raise ValueError(f"paraphrases {orphans[:5]} name an origin_id not in the golden set")
    items: list[ExtraResult] = []
    paraphrase: list[bool] = []
    origin: list[bool] = []
    pairs: Counter[str] = Counter()
    abstained: list[bool] = []
    conflict: list[bool] = []
    shown: list[bool] = []
    right: list[bool] = []
    by_kind_source: dict[str, list[bool]] = {}
    for line in sorted(extras, key=lambda line: line.id):
        answer = answers.get(line.id)
        if line.kind == "unanswerable":
            passed = answer is not None and answer.abstain is True
            detail = "abstained" if passed else ("missing" if answer is None else "answered")
            abstained.append(passed)
        else:
            reason = judge(as_question(line), answer)
            if line.kind == "paraphrase":
                passed, detail = reason == "ok", reason
                assert line.origin_id is not None  # the model requires it on paraphrases
                origin_ok = judge(by_id[line.origin_id], answers.get(line.origin_id)) == "ok"
                paraphrase.append(passed)
                origin.append(origin_ok)
                pairs[_pair(origin_ok, passed)] += 1
            else:
                values = values_shown(line, answer)
                passed = values and reason == "ok"
                detail = f"{reason}, values {'shown' if values else 'not shown'}"
                conflict.append(passed)
                shown.append(values)
                right.append(reason == "ok")
        by_kind_source.setdefault(f"{line.kind}/{line.source}", []).append(passed)
        items.append(
            ExtraResult(
                id=line.id,
                kind=line.kind,
                source=line.source,
                style=line.style,
                passed=passed,
                detail=detail,
            )
        )
    para, orig = _tally(paraphrase), _tally(origin)
    gap = None if para.accuracy is None or orig.accuracy is None else para.accuracy - orig.accuracy
    return ExtrasScore(
        extras_sha256=extras_sha256,
        paraphrase=para,
        paraphrase_origin=orig,
        paraphrase_gap=gap,
        paraphrase_pairs=dict(sorted(pairs.items())),
        unanswerable=_tally(abstained),
        conflict=_tally(conflict),
        conflict_values_shown=_tally(shown),
        conflict_answer_right=_tally(right),
        by_kind_source={key: _tally(marks) for key, marks in sorted(by_kind_source.items())},
        items=items,
    )


def _pair(origin_ok: bool, paraphrase_ok: bool) -> str:
    if origin_ok and paraphrase_ok:
        return "both"
    if origin_ok:
        return "origin_only"
    return "paraphrase_only" if paraphrase_ok else "neither"


def bucket_of(confidence: float) -> int:
    """0..4 for [0, 0.2), [0.2, 0.4), ..., [0.8, 1.0]; a value on a boundary goes up."""
    return min(int(confidence * BUCKETS + 1e-9), BUCKETS - 1)


def score_answer_v11(
    golden: Sequence[GoldenItem], answers: Mapping[int, Answer]
) -> AnswerV11Score | None:
    """None when no answer to a golden question carries `confidence` or `abstain`."""
    judged = [
        (answer, judge(item, answer) == "ok")
        for item in golden
        if (answer := answers.get(item.id)) is not None
    ]
    if not any(a.confidence is not None or a.abstain is not None for a, _ in judged):
        return None
    marks: list[list[bool]] = [[] for _ in range(BUCKETS)]
    sums = [0.0] * BUCKETS
    for answer, ok in judged:
        if answer.confidence is not None:
            index = bucket_of(answer.confidence)
            marks[index].append(ok)
            sums[index] += answer.confidence
    abstained = [ok for answer, ok in judged if answer.abstain is True]
    calibration = [
        Bucket(
            low=index / BUCKETS,
            high=(index + 1) / BUCKETS,
            n=len(marks[index]),
            correct=sum(marks[index]),
            accuracy=sum(marks[index]) / len(marks[index]) if marks[index] else None,
            mean_confidence=sums[index] / len(marks[index]) if marks[index] else None,
        )
        for index in range(BUCKETS)
    ]
    return AnswerV11Score(
        answers=len(judged),
        abstained=len(abstained),
        abstain_rate=len(abstained) / len(judged) if judged else None,
        not_abstained=_tally([ok for answer, ok in judged if answer.abstain is not True]),
        abstained_tally=_tally(abstained),
        with_confidence=sum(len(bucket) for bucket in marks),
        calibration=calibration,
    )


def score_golden(
    base: Score,
    golden: Sequence[GoldenItem],
    answers: Sequence[Answer],
    extras: Sequence[ExtraItem] = (),
    extras_sha256: str | None = None,
) -> GoldenScore:
    """`base` (scoring.score on the golden questions) plus the slices outside the headline."""
    by_id = {answer.id: answer for answer in answers}
    return GoldenScore(
        **dict(base),
        extras=(
            score_extras(extras, golden, by_id, extras_sha256 or "")
            if extras_sha256 is not None
            else None
        ),
        answer_v1_1=score_answer_v11(golden, by_id),
    )


def _cell(tally: Tally) -> str:
    accuracy = "n/a" if tally.accuracy is None else f"{tally.accuracy:.1%}"
    return f"{tally.correct}/{tally.n} {accuracy}"


def format_slices(result: GoldenScore) -> str:
    """The extras and answer_v1.1 sections, or an empty string when neither applies."""
    lines: list[str] = []
    extras = result.extras
    if extras is not None:
        gap = "n/a" if extras.paraphrase_gap is None else f"{extras.paraphrase_gap * 100:+.1f} pts"
        lines += [
            "extras (questions Stoa didn't write; not in the headline)",
            f"  paraphrase       {_cell(extras.paraphrase)}, origins "
            f"{_cell(extras.paraphrase_origin)}, gap {gap}",
            "  pairs            "
            + ", ".join(f"{key} {n}" for key, n in extras.paraphrase_pairs.items()),
            f"  unanswerable     {_cell(extras.unanswerable)} abstained",
            f"  conflict         {_cell(extras.conflict)} pass (values shown "
            f"{_cell(extras.conflict_values_shown)}, answer right "
            f"{_cell(extras.conflict_answer_right)})",
            "  by kind/source   "
            + ", ".join(f"{key} {_cell(tally)}" for key, tally in extras.by_kind_source.items()),
        ]
    v11 = result.answer_v1_1
    if v11 is not None:
        rate = "n/a" if v11.abstain_rate is None else f"{v11.abstain_rate:.1%}"
        lines += [
            *([""] if lines else []),
            "answer_v1.1 on the golden questions (not in the headline)",
            f"  abstained        {v11.abstained}/{v11.answers} {rate}",
            f"  accuracy         not abstained {_cell(v11.not_abstained)}, abstained "
            f"{_cell(v11.abstained_tally)} (best estimate)",
            f"  calibration      {v11.with_confidence} answers with a confidence",
            f"  {'confidence':<16} {'n':>6} {'mean':>6} {'accuracy':>9}",
        ]
        for bucket in v11.calibration:
            mean = "n/a" if bucket.mean_confidence is None else f"{bucket.mean_confidence:.2f}"
            accuracy = "n/a" if bucket.accuracy is None else f"{bucket.accuracy:.1%}"
            upper = "]" if bucket.high >= 1 else ")"
            name = f"[{bucket.low:.1f}, {bucket.high:.1f}{upper}"
            lines.append(f"  {name:<16} {bucket.n:>6} {mean:>6} {accuracy:>9}")
    return "\n".join(lines)

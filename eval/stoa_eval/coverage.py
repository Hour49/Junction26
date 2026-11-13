"""Score an answers file against every question in questions.jsonl, not only the golden set.

This is for methods that cost nothing per question (PDF, DXF and IFC parsers): they answer some
questions and skip the rest. Here a skipped question, or `answer: null`, is unanswered, not wrong.
The report gives coverage (answered / questions) and accuracy on the answered questions, overall,
per split (the sealed split's dev and eval, `split.py`), per source x type and per question
template. Questions are streamed and the answers are kept in a compact form, so memory stays small.
The rules for one answer are the golden mode's (`scoring.judge`).
"""

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import NamedTuple

from pydantic import BaseModel

from .families import language_of, source_of, template_of
from .models import FREE_TEXT_TYPES, Answer, AnswerValue, NumberedQuestion, Unit
from .scoring import TextReview, judge, p95


class CompactAnswer(NamedTuple):
    """The part of an `Answer` the scorer needs, about a fifth of its memory."""

    answer: AnswerValue | None
    unit: Unit | None
    has_evidence: bool
    cost_usd: float
    latency_s: float


def load_answers(rows: Iterable[tuple[int, Answer]]) -> dict[int, CompactAnswer]:
    """Question id -> compact answer. A repeated id fails."""
    answers: dict[int, CompactAnswer] = {}
    for line, answer in rows:
        if answer.id in answers:
            raise ValueError(f"answers line {line} repeats id {answer.id}")
        answers[answer.id] = CompactAnswer(
            answer.answer, answer.unit, bool(answer.evidence), answer.cost_usd, answer.latency_s
        )
    return answers


class Labels(NamedTuple):
    source: str
    language: str
    template: str


class Labeller:
    """A question's source, language and template, as `selection.annotate` gives them; templates
    are cached by question text (about 6,800 distinct texts in 127,044 questions)."""

    def __init__(self) -> None:
        self._templates: dict[str, tuple[str, str]] = {}

    def __call__(self, question: NumberedQuestion) -> Labels:
        cached = self._templates.get(question.question)
        if cached is None:
            template = template_of(question.question)
            cached = self._templates[question.question] = (template, language_of(template))
        return Labels(source_of(question.path), cached[1], cached[0])


class Row(BaseModel):
    n: int
    answered: int
    correct: int
    coverage: float | None
    accuracy: float | None  # on the answered questions


class TemplateRow(Row):
    source: str
    type: str
    language: str
    template: str


class CoverageScore(BaseModel):
    questions: Row
    numeric: Row
    text: Row
    by_split: dict[str, Row]
    by_source_type: dict[str, Row]
    by_template: list[TemplateRow]  # every template, most answered first
    by_reason: dict[str, int]  # answered questions only
    extra_answer_ids: list[int]
    evidence_coverage: float | None  # share of answered questions with at least one box
    cost_total_usd: float
    cost_mean_usd: float | None  # per answer line that matches a question
    latency_mean_s: float | None
    latency_p95_s: float | None
    needs_review: list[TextReview]  # answered text questions


@dataclass
class _Count:
    n: int = 0
    answered: int = 0
    correct: int = 0

    def row(self) -> Row:
        return Row(
            n=self.n,
            answered=self.answered,
            correct=self.correct,
            coverage=self.answered / self.n if self.n else None,
            accuracy=self.correct / self.answered if self.answered else None,
        )


def score_all(
    questions: Iterable[tuple[NumberedQuestion, str]], answers: Mapping[int, CompactAnswer]
) -> CoverageScore:
    """`questions` are (question, split name) pairs, e.g. streamed from the split files."""
    label = Labeller()
    counts: dict[tuple[str, ...], _Count] = defaultdict(_Count)
    reasons: Counter[str] = Counter()
    matched: set[int] = set()
    review: list[TextReview] = []
    with_evidence = 0
    splits: list[str] = []
    for question, split in questions:
        line = question.id
        if split not in splits:
            splits.append(split)
        labels = label(question)
        reply = answers.get(line)
        reason = judge(question, reply)
        answered = reason != "missing"
        free_text = question.type in FREE_TEXT_TYPES
        for key in (
            ("all",),
            ("text",) if free_text else ("numeric",),
            ("split", split),
            ("source_type", f"{labels.source}/{question.type}"),
            ("template", labels.source, question.type, labels.language, labels.template),
        ):
            count = counts[key]
            count.n += 1
            count.answered += answered
            count.correct += reason == "ok"
        if reply is not None:
            matched.add(line)
        if reply is not None and answered:
            reasons[reason] += 1
            with_evidence += reply.has_evidence
            if free_text:
                review.append(
                    TextReview(
                        id=line,
                        question=question.question,
                        gold=question.answer,
                        answer=reply.answer,
                        exact_match=reason == "ok",
                    )
                )
    used = [answers[line] for line in matched]
    templates = [
        TemplateRow(
            source=key[1], type=key[2], language=key[3], template=key[4], **count.row().model_dump()
        )
        for key, count in counts.items()
        if key[0] == "template"
    ]
    answered_total = counts["all",].answered
    return CoverageScore(
        questions=counts["all",].row(),
        numeric=counts["numeric",].row(),
        text=counts["text",].row(),
        by_split={split: counts["split", split].row() for split in splits},
        by_source_type={
            key[1]: count.row() for key, count in sorted(counts.items()) if key[0] == "source_type"
        },
        by_template=sorted(templates, key=lambda row: (-row.answered, -row.n, row.template)),
        by_reason=dict(sorted(reasons.items())),
        extra_answer_ids=sorted(answers.keys() - matched),
        evidence_coverage=with_evidence / answered_total if answered_total else None,
        cost_total_usd=sum(reply.cost_usd for reply in used),
        cost_mean_usd=sum(reply.cost_usd for reply in used) / len(used) if used else None,
        latency_mean_s=sum(reply.latency_s for reply in used) / len(used) if used else None,
        latency_p95_s=p95([reply.latency_s for reply in used]),
        needs_review=review,
    )


def _pct(value: float | None) -> str:
    return "   n/a" if value is None else f"{value:6.1%}"


def _row(row: Row) -> str:
    return (
        f"{row.answered:>7}/{row.n:<7} {_pct(row.coverage)}   "
        f"{row.correct:>7}/{row.answered:<7} {_pct(row.accuracy)}"
    )


def format_coverage_table(result: CoverageScore, top: int = 20) -> str:
    header = f"{'':<28} {'answered/questions':>18} cover   {'correct/answered':>16} accuracy"
    rows = [
        ("all questions", result.questions),
        ("numeric", result.numeric),
        ("text (exact match)", result.text),
        *result.by_split.items(),
        ("", None),
        *result.by_source_type.items(),
    ]
    lines = [header]
    lines += [f"{name:<28} {_row(row)}" if row else "" for name, row in rows]
    lines += ["", f"top {top} templates by answered", header]
    for row in result.by_template[:top]:
        lines.append(f"{row.source + '/' + row.type + ' ' + row.language:<28} {_row(row)}")
        lines.append(f"    {row.template[:96]}")
    evidence = _pct(result.evidence_coverage).strip()
    mean_cost = "n/a" if result.cost_mean_usd is None else f"${result.cost_mean_usd:.4f}"
    latency = (
        "n/a"
        if result.latency_mean_s is None or result.latency_p95_s is None
        else f"{result.latency_mean_s:.2f} s, p95 {result.latency_p95_s:.2f} s"
    )
    lines += [
        "",
        "reasons   " + ", ".join(f"{reason} {n}" for reason, n in result.by_reason.items()),
        f"answers   {len(result.extra_answer_ids)} ids not among the scored questions (ignored)",
        f"evidence  {evidence} of answered questions have a box",
        f"cost      total ${result.cost_total_usd:.4f}, mean {mean_cost} per answer line",
        f"latency   mean {latency}",
    ]
    return "\n".join(lines)

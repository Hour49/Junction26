"""Two baselines that call no API.

- oracle: the golden answers themselves. It must score 100%; anything less is a scorer bug.
- constant: per question template, the typical answer among dev questions that are not in the golden
  set (median for area/length/volume, most common value otherwise). A template with no such question
  falls back to its source and type. This is the floor any real method has to beat.
"""

from collections import Counter, defaultdict
from collections.abc import Sequence

from .models import Answer, AnswerValue, GoldenItem, Unit

CONTINUOUS_TYPES = frozenset({"area", "length", "volume"})


def oracle(golden: Sequence[GoldenItem]) -> list[Answer]:
    return [
        Answer(
            id=item.id,
            answer=item.answer,
            unit=item.unit,
            evidence=[],
            method="oracle",
            cost_usd=0.0,
            latency_s=0.0,
        )
        for item in golden
    ]


def _most_common[T](values: Sequence[T]) -> T:
    """Ties go to the value with the smallest repr, so the result never depends on input order."""
    return min(Counter(values).items(), key=lambda pair: (-pair[1], repr(pair[0])))[0]


def _typical(rows: Sequence[GoldenItem]) -> tuple[AnswerValue, Unit | None]:
    units: list[Unit | None] = [row.unit for row in rows]
    unit = _most_common(units)
    if rows[0].type in CONTINUOUS_TYPES:
        numbers = sorted(row.answer for row in rows if not isinstance(row.answer, str))
        return numbers[(len(numbers) - 1) // 2], unit  # the lower median: a value that occurred
    return _most_common([row.answer for row in rows]), unit


def constant(golden: Sequence[GoldenItem], pool: Sequence[GoldenItem]) -> list[Answer]:
    """`pool` is every annotated question (`selection.annotate`); only its dev part outside the
    golden set is used."""
    golden_ids = {item.id for item in golden}
    by_template: dict[tuple[str, str, str], list[GoldenItem]] = defaultdict(list)
    by_source_type: dict[tuple[str, str], list[GoldenItem]] = defaultdict(list)
    for row in pool:
        if row.split == "dev" and row.id not in golden_ids:
            by_template[(row.source, row.type, row.template)].append(row)
            by_source_type[(row.source, row.type)].append(row)
    answers: list[Answer] = []
    for item in golden:
        value: AnswerValue | None = None
        unit: Unit | None = None
        method = "constant:none"
        for name, rows in (
            ("template", by_template.get((item.source, item.type, item.template))),
            ("source-type", by_source_type.get((item.source, item.type))),
        ):
            if rows:
                value, unit = _typical(rows)
                method = f"constant:{name}"
                break
        answers.append(
            Answer(
                id=item.id,
                answer=value,
                unit=unit,
                evidence=[],
                method=method,
                cost_usd=0.0,
                latency_s=0.0,
            )
        )
    return answers

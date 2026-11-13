"""Two baselines that call no API.

- oracle: the golden answers themselves, with confidence 1, one evidence box per gold item each
  answer is about (when Part 1 gold is given), and the expected behaviour on every extras line
  (abstain on unanswerable ones, both values on conflict ones, `estimate: true` on estimate ones).
  It must score 100% on the headline and on every slice; anything less is a scorer bug.
- constant: per question template, the typical answer among dev questions that are not in the golden
  set (median for area/length/volume, most common value otherwise). A template with no such question
  falls back to its source and type. This is the floor any real method has to beat.
"""

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence

from .evidence_scoring import oracle_evidence
from .extraction import Extraction
from .models import Answer, AnswerValue, ConflictValue, ExtraItem, GoldenItem, Unit

CONTINUOUS_TYPES = frozenset({"area", "length", "volume"})


def oracle(
    golden: Sequence[GoldenItem],
    extras: Sequence[ExtraItem] = (),
    part1_gold: Mapping[str, Extraction] | None = None,
) -> list[Answer]:
    """With `part1_gold` (file -> extraction gold), each golden answer cites one box per gold item
    it is about (evidence_scoring.oracle_evidence)."""
    answers = [
        Answer(
            id=item.id,
            answer=item.answer,
            unit=item.unit,
            evidence=oracle_evidence(item, part1_gold) if part1_gold is not None else [],
            method="oracle",
            cost_usd=0.0,
            latency_s=0.0,
            confidence=1.0,
            abstain=False,
        )
        for item in golden
    ]
    for line in extras:
        values = line.expect.conflict_values
        answers.append(
            Answer(
                id=line.id,
                answer=line.expect.answer,
                unit=line.unit,
                evidence=[],
                method="oracle",
                cost_usd=0.0,
                latency_s=0.0,
                abstain=line.kind == "unanswerable",
                estimate=True if line.kind == "estimate" else None,
                conflicts=(
                    None
                    if values is None
                    else [
                        ConflictValue(value=v, unit=line.unit, method="oracle", file=line.path)
                        for v in values
                    ]
                ),
                resolution=None if values is None else "the expected answer",
            )
        )
    return answers


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


def empty_extraction(gold: Extraction) -> Extraction:
    """The Part 1 floor: the gold file's pages with nothing found on them and no scale."""
    return Extraction.model_validate(
        {
            "schema": "extraction_v1",
            "file": gold.file,
            "split": gold.split,
            "truth": "elements",
            "pages": [page.model_dump() for page in gold.pages],
            "scale": {"status": "no_scale"},
            "plans": [],
            "elements": [],
            "rooms": [],
        }
    )

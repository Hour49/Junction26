"""Results history: one aggregate row per recorded score run, appended to eval/results/runs.jsonl.

Owner, 2026-11-13: "also I am thining overall we should save all the results of the golden datasset
so we can share that at the end of how we improved". The file is tracked and the repo is public, so
a row (`models.RunRecord`) holds aggregates only. The full score JSON stays in the gitignored runs
folder, and the row keeps its sha256 so the two can be matched.
"""

import csv
import json
from collections.abc import Iterable, Sequence
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ValidationError

from .coverage import CoverageScore, Row
from .extraction_scoring import ExtractionScore
from .models import Against, ExtractionRecord, Ratio, RunRecord, Stats
from .scale_scoring import Rate
from .scoring import Score, Tally


def _stats(numbers: Tally | Row) -> Stats:
    if isinstance(numbers, Row):
        return Stats(
            n=numbers.n,
            correct=numbers.correct,
            accuracy=numbers.accuracy,
            answered=numbers.answered,
            coverage=numbers.coverage,
        )
    return Stats(
        n=numbers.n,
        correct=numbers.correct,
        accuracy=numbers.accuracy,
        answered=None,
        coverage=None,
    )


def make_record(
    result: Score | CoverageScore,
    *,
    against: Against,
    name: str,
    note: str | None,
    milestone: bool,
    golden_version: str | None,
    questions_sha256: str,
    score_sha256: str,
    commit: str,
    dirty: bool,
    now: datetime,
    reads: Literal["gold-extraction", "pipeline-extraction"] | None = None,
) -> RunRecord:
    overall = result.overall if isinstance(result, Score) else result.questions
    return RunRecord(
        recorded_at=now,
        commit=commit,
        dirty=dirty,
        name=name,
        note=note,
        against=against,
        golden_version=golden_version,
        milestone=milestone,
        reads=reads,
        questions_sha256=questions_sha256,
        score_sha256=score_sha256,
        overall=_stats(overall),
        numeric=_stats(result.numeric),
        by_source_type={key: _stats(numbers) for key, numbers in result.by_source_type.items()},
        evidence_coverage=result.evidence_coverage,
        cost_total_usd=result.cost_total_usd,
        cost_mean_usd=result.cost_mean_usd,
        latency_mean_s=result.latency_mean_s,
        latency_p95_s=result.latency_p95_s,
    )


def _ratio(rate: Rate) -> Ratio:
    return Ratio(n=rate.n, correct=rate.correct, rate=rate.rate)


def make_extraction_record(
    result: ExtractionScore,
    *,
    against: Literal["golden", "dev", "eval"],
    name: str,
    note: str | None,
    milestone: bool,
    golden_version: str | None,
    gold_sha256: str,
    score_sha256: str,
    commit: str,
    dirty: bool,
    now: datetime,
) -> ExtractionRecord:
    rooms = Rate(), Rate(), Rate()  # boxes matched, type right, area right: summed over sources
    room_tp = room_fp = room_fn = 0
    for stats in result.rooms.values():
        room_tp, room_fp, room_fn = (
            room_tp + stats.boxes.tp,
            room_fp + stats.boxes.fp,
            room_fn + stats.boxes.fn,
        )
        for total, part in zip(rooms[1:], (stats.type, stats.area), strict=True):
            total.n, total.correct = total.n + part.n, total.correct + part.correct
    room_denominator = 2 * room_tp + room_fp + room_fn
    plans = Rate(
        n=sum(rate.n for rate in result.plans.values()),
        correct=sum(rate.correct for rate in result.plans.values()),
    )
    scale = result.scale_overall
    status, passed = Rate(), Rate()
    for stats in scale.by_case.values():
        status.n, status.correct = status.n + stats.status.n, status.correct + stats.status.correct
        passed.n += stats.m_per_unit.n
        passed.correct += stats.m_per_unit.correct
    return ExtractionRecord(
        recorded_at=now,
        commit=commit,
        dirty=dirty,
        name=name,
        note=note,
        part="extraction",
        against=against,
        golden_version=golden_version,
        milestone=milestone,
        gold_sha256=gold_sha256,
        score_sha256=score_sha256,
        files=result.files,
        predicted=result.predicted,
        multiplicity=result.multiplicity,
        elements_f1=result.elements_overall.f1,
        elements_f1_by_source={key: prf.f1 for key, prf in result.elements_by_source.items()},
        room_f1=2 * room_tp / room_denominator if room_denominator else None,
        room_type_accuracy=rooms[1].rate,
        room_area_accuracy=rooms[2].rate,
        plans_exact=_ratio(plans),
        counts_exact=_ratio(result.counts_overall),
        counts_exact_by_source={key: _ratio(rate) for key, rate in result.counts_by_source.items()},
        scale_status=_ratio(status),
        scale_m_per_unit=_ratio(passed),
        scale_m_per_unit_by_case={
            case: _ratio(stats.m_per_unit) for case, stats in scale.by_case.items()
        },
        scale_estimate_median_error=scale.estimates.median_error,
        scale_estimate_within_20=scale.estimates.within_20,
    )


def append_record(path: Path, record: BaseModel) -> None:
    """Add one line at the end; earlier lines are never rewritten."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as results:
        results.write(record.model_dump_json() + "\n")


def _records(path: Path) -> list[RunRecord | ExtractionRecord]:
    """Every row: answer rows (Part 2, and all rows from before v2) and extraction rows (Part 1)."""
    if not path.exists():
        return []
    rows: list[RunRecord | ExtractionRecord] = []
    with path.open(encoding="utf-8") as lines:
        for lineno, line in enumerate(lines, 1):
            if not line.strip():
                continue
            model = ExtractionRecord if json.loads(line).get("part") == "extraction" else RunRecord
            try:
                rows.append(model.model_validate_json(line))
            except ValidationError as error:
                raise ValueError(f"{path}:{lineno}: {error}") from error
    return rows


def read_history(path: Path, against: Against | None = None) -> list[RunRecord]:
    """Recorded answer runs (Part 2), oldest first, optionally only those against one target."""
    chosen = [
        record
        for record in _records(path)
        if isinstance(record, RunRecord) and (against is None or record.against == against)
    ]
    return sorted(chosen, key=lambda record: record.recorded_at)


def read_extraction_history(path: Path, against: Against | None = None) -> list[ExtractionRecord]:
    """Recorded extraction runs (Part 1), oldest first."""
    chosen = [
        record
        for record in _records(path)
        if isinstance(record, ExtractionRecord) and (against is None or record.against == against)
    ]
    return sorted(chosen, key=lambda record: record.recorded_at)


def _target(record: RunRecord | ExtractionRecord) -> str:
    if record.against == "golden":
        return f"golden {record.golden_version}"
    return record.against + (" (milestone)" if record.milestone else "")


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1%}"


def format_history(records: Sequence[RunRecord]) -> str:
    header = (
        f"{'recorded':<16}  {'commit':<9}  {'name':<26}  {'against':<12}  {'n':>7}  {'cover':>6}  "
        f"{'acc':>6}  {'numeric':>7}  {'evid':>6}  {'cost/ans':>9}  {'p95 s':>6}  note"
    )
    lines = [header]
    for record in records:
        cost = "n/a" if record.cost_mean_usd is None else f"${record.cost_mean_usd:.4f}"
        p95 = "n/a" if record.latency_p95_s is None else f"{record.latency_p95_s:.2f}"
        commit = record.commit + ("*" if record.dirty else "")
        lines.append(
            f"{record.recorded_at:%Y-%m-%d %H:%M}  {commit:<9}  "
            f"{record.name[:26]:<26}  {_target(record):<12}  {record.overall.n:>7}  "
            f"{_pct(record.overall.coverage):>6}  {_pct(record.overall.accuracy):>6}  "
            f"{_pct(record.numeric.accuracy):>7}  {_pct(record.evidence_coverage):>6}  "
            f"{cost:>9}  {p95:>6}  {record.note or ''}"
        )
    lines.append("* = recorded with uncommitted changes")
    return "\n".join(lines)


def format_extraction_history(records: Sequence[ExtractionRecord]) -> str:
    header = (
        f"{'recorded':<16}  {'commit':<9}  {'name':<26}  {'against':<12}  {'files':>5}  "
        f"{'pred':>5}  {'elem f1':>7}  {'room f1':>7}  {'counts':>6}  {'plans':>6}  "
        f"{'scale':>6}  note"
    )
    lines = ["Part 1, extraction", header]
    for record in records:
        commit = record.commit + ("*" if record.dirty else "")
        lines.append(
            f"{record.recorded_at:%Y-%m-%d %H:%M}  {commit:<9}  {record.name[:26]:<26}  "
            f"{_target(record):<12}  {record.files:>5}  {record.predicted:>5}  "
            f"{_pct(record.elements_f1):>7}  {_pct(record.room_f1):>7}  "
            f"{_pct(record.counts_exact.rate):>6}  {_pct(record.plans_exact.rate):>6}  "
            f"{_pct(record.scale_m_per_unit.rate):>6}  {record.note or ''}"
        )
    lines.append("* = recorded with uncommitted changes")
    return "\n".join(lines)


def write_history_csv(path: Path, records: Iterable[RunRecord]) -> None:
    """One row per run with the overall numbers and an accuracy and a coverage column per
    source/type, for a chart."""
    rows = list(records)
    groups = sorted({key for record in rows for key in record.by_source_type})
    fields = [
        "recorded_at", "commit", "dirty", "name", "note", "against", "golden_version", "milestone",
        "n", "correct", "accuracy", "answered", "coverage", "numeric_accuracy",
        "evidence_coverage", "cost_total_usd", "cost_mean_usd", "latency_mean_s", "latency_p95_s",
        *(f"accuracy {group}" for group in groups),
        *(f"coverage {group}" for group in groups),
    ]  # fmt: skip
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=fields)
        writer.writeheader()
        for record in rows:
            row: dict[str, object] = {
                "recorded_at": record.recorded_at.isoformat(),
                "commit": record.commit,
                "dirty": record.dirty,
                "name": record.name,
                "note": record.note or "",
                "against": record.against,
                "golden_version": record.golden_version or "",
                "milestone": record.milestone,
                "n": record.overall.n,
                "correct": record.overall.correct,
                "accuracy": record.overall.accuracy,
                "answered": record.overall.answered,
                "coverage": record.overall.coverage,
                "numeric_accuracy": record.numeric.accuracy,
                "evidence_coverage": record.evidence_coverage,
                "cost_total_usd": record.cost_total_usd,
                "cost_mean_usd": record.cost_mean_usd,
                "latency_mean_s": record.latency_mean_s,
                "latency_p95_s": record.latency_p95_s,
            }
            for group in groups:
                stats = record.by_source_type.get(group)
                row[f"accuracy {group}"] = stats.accuracy if stats else None
                row[f"coverage {group}"] = stats.coverage if stats else None
            writer.writerow(row)

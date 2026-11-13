"""Results history: one aggregate row per recorded score run, appended to eval/results/runs.jsonl.

Owner, 2026-11-13: "also I am thining overall we should save all the results of the golden datasset
so we can share that at the end of how we improved". The file is tracked and the repo is public, so
a row (`models.RunRecord`) holds aggregates only. The full score JSON stays in the gitignored runs
folder, and the row keeps its sha256 so the two can be matched.
"""

import csv
from collections.abc import Iterable, Sequence
from datetime import datetime
from pathlib import Path

from .coverage import CoverageScore, Row
from .jsonl import read_jsonl
from .models import Against, RunRecord, Stats
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


def append_record(path: Path, record: RunRecord) -> None:
    """Add one line at the end; earlier lines are never rewritten."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as results:
        results.write(record.model_dump_json() + "\n")


def read_history(path: Path, against: Against | None = None) -> list[RunRecord]:
    """Recorded runs, oldest first, optionally only those against one target."""
    if not path.exists():
        return []
    records = [record for _, record in read_jsonl(path, RunRecord)]
    chosen = [record for record in records if against is None or record.against == against]
    return sorted(chosen, key=lambda record: record.recorded_at)


def _target(record: RunRecord) -> str:
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

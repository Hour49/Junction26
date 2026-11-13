"""Results history: one aggregate record per scored run, one file each in eval/results/runs/
(run_store.py), and the tables that show how the methods improved.

Owner, 2026-11-13: "also I am thining overall we should save all the results of the golden datasset
so we can share that at the end of how we improved", and ~22:48: "also make sure all the runs of the
golden dataset, will be saved somewhere so at the end we will be able to show the improvement".
The files are tracked and the repo is public, so a record (`models.RunRecord`,
`models.ExtractionRecord`) holds aggregates only. The full score JSON stays in the gitignored runs
folder under the same stem, and the record keeps its sha256 so the two can be matched.
"""

import csv
from collections.abc import Callable, Iterable, Sequence
from datetime import datetime
from pathlib import Path
from typing import Literal

from .coverage import CoverageScore, Row
from .extraction_scoring import ExtractionScore
from .models import Against, ExtractionRecord, Ratio, RunRecord, Stats
from .run_store import read_records
from .scale_scoring import Rate, ScaleScore
from .scoring import Score, Tally

SHORT = {"cubicasa5k": "cubi", "swiss_dwellings": "swiss", "ifc_models": "ifc",
         "ifc_bench": "bench", "opening_design": "open"}  # fmt: skip


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

    def statuses(score: ScaleScore) -> Rate:
        total = Rate()
        for stats in score.by_case.values():
            total.n, total.correct = total.n + stats.status.n, total.correct + stats.status.correct
        return total

    passed = Rate()
    for stats in scale.by_case.values():
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
        scale_status=_ratio(statuses(scale)),
        scale_status_by_source={
            source: _ratio(statuses(score)) for source, score in result.scale.items()
        },
        scale_m_per_unit=_ratio(passed),
        scale_m_per_unit_by_case={
            case: _ratio(stats.m_per_unit) for case, stats in scale.by_case.items()
        },
        scale_estimate_median_error=scale.estimates.median_error,
        scale_estimate_within_20=scale.estimates.within_20,
    )


def read_history(folder: Path, against: Against | None = None) -> list[RunRecord]:
    """Recorded answer runs (Part 2), oldest first, optionally only those against one target."""
    return [
        record
        for record in read_records(folder)
        if isinstance(record, RunRecord) and (against is None or record.against == against)
    ]


def read_extraction_history(folder: Path, against: Against | None = None) -> list[ExtractionRecord]:
    """Recorded extraction runs (Part 1), oldest first."""
    return [
        record
        for record in read_records(folder)
        if isinstance(record, ExtractionRecord) and (against is None or record.against == against)
    ]


def source_accuracy(record: RunRecord) -> dict[str, float | None]:
    """Accuracy per source, from the per source/type numbers: correct over questions (golden)
    or over answered questions (all, dev, eval)."""
    totals: dict[str, list[int]] = {}
    for key, stats in record.by_source_type.items():
        total = totals.setdefault(key.split("/", 1)[0], [0, 0])
        total[0] += stats.correct
        total[1] += stats.n if stats.answered is None else stats.answered
    return {source: (c / n if n else None) for source, (c, n) in sorted(totals.items())}


def _target(record: RunRecord | ExtractionRecord) -> str:
    if record.against == "golden":
        return f"golden {record.golden_version}"
    return record.against + (" (milestone)" if record.milestone else "")


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1%}"


def _short(source: str) -> str:
    return SHORT.get(source, source[:6])


def _sources(groups: Iterable[Iterable[str]]) -> list[str]:
    return sorted({source for group in groups for source in group})


def format_history(records: Sequence[RunRecord]) -> str:
    """Part 2 runs, oldest first, with accuracy per source."""
    sources = _sources(source_accuracy(record) for record in records)
    header = (
        f"{'recorded':<16}  {'commit':<9}  {'name':<26}  {'against':<12}  {'n':>6}  {'cover':>6}  "
        f"{'acc':>6}  " + "".join(f"{_short(s):>7}  " for s in sources) + f"{'cost/ans':>9}  note"
    )
    lines = ["Part 2, answering (accuracy overall and per source)", header]
    for record in records:
        cost = "n/a" if record.cost_mean_usd is None else f"${record.cost_mean_usd:.4f}"
        commit = record.commit + ("*" if record.dirty else "")
        per_source = source_accuracy(record)
        lines.append(
            f"{record.recorded_at:%Y-%m-%d %H:%M}  {commit:<9}  "
            f"{record.name[:26]:<26}  {_target(record):<12}  {record.overall.n:>6}  "
            f"{_pct(record.overall.coverage):>6}  {_pct(record.overall.accuracy):>6}  "
            + "".join(f"{_pct(per_source.get(s)):>7}  " for s in sources)
            + f"{cost:>9}  {record.note or ''}"
        )
    lines.append("* = recorded with uncommitted changes")
    return "\n".join(lines)


def format_extraction_history(records: Sequence[ExtractionRecord]) -> str:
    """Part 1 runs, oldest first: element F1, counts exact and scale status ok, overall and per
    source."""
    sources = _sources(
        [*record.elements_f1_by_source, *record.counts_exact_by_source,
         *record.scale_status_by_source]
        for record in records
    )  # fmt: skip
    per_source = "".join(
        f"{_short(s) + ' f1':>10}  {_short(s) + ' cnt':>10}  {_short(s) + ' scl':>10}  "
        for s in sources
    )
    header = (
        f"{'recorded':<16}  {'commit':<9}  {'name':<26}  {'against':<12}  {'files':>5}  "
        f"{'elem f1':>7}  {'counts':>6}  {'scale':>6}  " + per_source + "note"
    )
    lines = ["Part 1, extraction (element F1, counts exact, scale status ok)", header]
    for record in records:
        commit = record.commit + ("*" if record.dirty else "")
        cells = "".join(
            f"{_pct(record.elements_f1_by_source.get(s)):>10}  "
            f"{_pct(_rate(record.counts_exact_by_source.get(s))):>10}  "
            f"{_pct(_rate(record.scale_status_by_source.get(s))):>10}  "
            for s in sources
        )
        lines.append(
            f"{record.recorded_at:%Y-%m-%d %H:%M}  {commit:<9}  {record.name[:26]:<26}  "
            f"{_target(record):<12}  {record.files:>5}  {_pct(record.elements_f1):>7}  "
            f"{_pct(record.counts_exact.rate):>6}  {_pct(record.scale_status.rate):>6}  "
            + cells
            + (record.note or "")
        )
    lines.append("* = recorded with uncommitted changes")
    return "\n".join(lines)


def _rate(ratio: Ratio | None) -> float | None:
    return None if ratio is None else ratio.rate


Metric = tuple[str, Callable[[RunRecord], float | None]]
ExtractionMetric = tuple[str, Callable[[ExtractionRecord], float | None]]
ANSWERING_METRICS: list[Metric] = [("accuracy", lambda r: r.overall.accuracy)]
EXTRACTION_METRICS: list[ExtractionMetric] = [
    ("element F1", lambda r: r.elements_f1),
    ("counts exact", lambda r: r.counts_exact.rate),
    ("scale status", lambda r: r.scale_status.rate),
]


def _progress_rows[R: (RunRecord, ExtractionRecord)](
    part: str, records: Sequence[R], metrics: Sequence[tuple[str, Callable[[R], float | None]]]
) -> list[str]:
    groups: dict[tuple[str, str], list[R]] = {}
    for record in records:
        groups.setdefault((record.name, _target(record)), []).append(record)
    lines: list[str] = []
    for (name, target), runs in sorted(groups.items()):
        for metric, value_of in metrics:
            values = [(r.recorded_at, v) for r in runs if (v := value_of(r)) is not None]
            if not values:
                continue
            first, latest = values[0], values[-1]
            best = max(values, key=lambda pair: pair[1])  # the earliest of equal bests
            change = (latest[1] - first[1]) * 100
            lines.append(
                f"{part:<10}  {name[:26]:<26}  {target:<12}  {metric:<12}  {len(values):>4}  "
                f"{_pct(first[1]):>6} {first[0]:%d %H:%M}  {_pct(latest[1]):>6} "
                f"{latest[0]:%d %H:%M}  {_pct(best[1]):>6} {best[0]:%d %H:%M}  {change:>+7.1f}"
            )
    return lines


def format_progress(answering: Sequence[RunRecord], extraction: Sequence[ExtractionRecord]) -> str:
    """Per method and target: the first, latest and best value of each headline number."""
    header = (
        f"{'part':<10}  {'name':<26}  {'against':<12}  {'metric':<12}  {'runs':>4}  "
        f"{'first':>15}  {'latest':>15}  {'best':>15}  {'pts':>7}"
    )
    lines = [
        "How we improved: first vs latest vs best per method (day hh:mm; pts = latest - first)"
    ]
    lines.append(header)
    lines += _progress_rows("extraction", extraction, EXTRACTION_METRICS)
    lines += _progress_rows("answering", answering, ANSWERING_METRICS)
    return "\n".join(lines)


def write_history_csv(path: Path, records: Iterable[RunRecord]) -> None:
    """One row per run with the overall numbers and an accuracy and a coverage column per
    source/type, for a chart."""
    rows = list(records)
    groups = sorted({key for record in rows for key in record.by_source_type})
    sources = _sources(source_accuracy(record) for record in rows)
    fields = [
        "recorded_at", "commit", "dirty", "name", "note", "against", "golden_version", "milestone",
        "n", "correct", "accuracy", "answered", "coverage", "numeric_accuracy",
        "evidence_coverage", "cost_total_usd", "cost_mean_usd", "latency_mean_s", "latency_p95_s",
        "reads", *(f"accuracy {source}" for source in sources),
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
                "reads": record.reads or "",
            }
            for source, accuracy in source_accuracy(record).items():
                row[f"accuracy {source}"] = accuracy
            for group in groups:
                stats = record.by_source_type.get(group)
                row[f"accuracy {group}"] = stats.accuracy if stats else None
                row[f"coverage {group}"] = stats.coverage if stats else None
            writer.writerow(row)


def write_extraction_csv(path: Path, records: Iterable[ExtractionRecord]) -> None:
    """One row per Part 1 run with the headline numbers, overall and per source."""
    rows = list(records)
    sources = _sources(
        [*record.elements_f1_by_source, *record.counts_exact_by_source,
         *record.scale_status_by_source]
        for record in rows
    )  # fmt: skip
    fields = [
        "recorded_at", "commit", "dirty", "name", "note", "against", "golden_version", "milestone",
        "files", "predicted", "multiplicity", "elements_f1", "room_f1", "room_type_accuracy",
        "room_area_accuracy", "plans_exact", "counts_exact", "scale_status", "scale_m_per_unit",
        "scale_estimate_median_error", "scale_estimate_within_20",
        *(f"{kind} {source}" for source in sources
          for kind in ("elements_f1", "counts_exact", "scale_status")),
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
                "files": record.files,
                "predicted": record.predicted,
                "multiplicity": record.multiplicity,
                "elements_f1": record.elements_f1,
                "room_f1": record.room_f1,
                "room_type_accuracy": record.room_type_accuracy,
                "room_area_accuracy": record.room_area_accuracy,
                "plans_exact": record.plans_exact.rate,
                "counts_exact": record.counts_exact.rate,
                "scale_status": record.scale_status.rate,
                "scale_m_per_unit": record.scale_m_per_unit.rate,
                "scale_estimate_median_error": record.scale_estimate_median_error,
                "scale_estimate_within_20": record.scale_estimate_within_20,
            }
            for source in sources:
                row[f"elements_f1 {source}"] = record.elements_f1_by_source.get(source)
                row[f"counts_exact {source}"] = _rate(record.counts_exact_by_source.get(source))
                row[f"scale_status {source}"] = _rate(record.scale_status_by_source.get(source))
            writer.writerow(row)

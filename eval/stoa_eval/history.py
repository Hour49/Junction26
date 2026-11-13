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
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from .conflict_scoring import ConflictScore, QuantityCounts
from .coverage import CoverageScore, Row
from .evidence_scoring import EvidenceGroup, EvidenceScore
from .extraction_scoring import ExtractionScore
from .extras_scoring import AnswerV11Score, ExtrasScore, GoldenScore
from .models import (
    Against,
    AnswerV11Record,
    AreaEstimates,
    CalibrationBucket,
    ConflictCounts,
    ConflictsRecord,
    EvidenceHitsGroup,
    EvidenceHitsRecord,
    ExtractionRecord,
    ExtrasRecord,
    Ratio,
    RunRecord,
    Stats,
    TablesRecord,
    TextClaimsRecord,
)
from .run_store import read_records
from .scale_scoring import Rate, ScaleScore
from .scoring import Score, Tally
from .table_scoring import TableScore
from .text_scoring import TextClaimsScore

SHORT = {"cubicasa5k": "cubi", "swiss_dwellings": "swiss", "ifc_models": "ifc",
         "ifc_bench": "bench", "opening_design": "open"}  # fmt: skip


@dataclass(frozen=True)
class Provenance:
    """Which code made the predictions, and how it was set up. `commit` and `dirty` describe that
    code: HEAD of the scorer's tree, or a clean export (`git archive`) of an older commit, in
    which case `eval_commit` and `eval_dirty` say which scorer scored it."""

    commit: str
    dirty: bool
    committed_at: datetime | None = None
    eval_commit: str | None = None
    eval_dirty: bool | None = None
    settings: dict[str, str] | None = None


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
    provenance: Provenance,
    now: datetime,
    reads: Literal["gold-extraction", "pipeline-extraction"] | None = None,
) -> RunRecord:
    overall = result.overall if isinstance(result, Score) else result.questions
    return RunRecord(
        recorded_at=now,
        commit=provenance.commit,
        dirty=provenance.dirty,
        committed_at=provenance.committed_at,
        eval_commit=provenance.eval_commit,
        eval_dirty=provenance.eval_dirty,
        settings=provenance.settings,
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
        by_split={key: _stats(numbers) for key, numbers in result.by_split.items()},
        by_source_type={key: _stats(numbers) for key, numbers in result.by_source_type.items()},
        evidence_coverage=result.evidence_coverage,
        cost_total_usd=result.cost_total_usd,
        cost_mean_usd=result.cost_mean_usd,
        latency_mean_s=result.latency_mean_s,
        latency_p95_s=result.latency_p95_s,
        extras=_extras(result.extras) if isinstance(result, GoldenScore) else None,
        answer_v1_1=_answer_v11(result.answer_v1_1) if isinstance(result, GoldenScore) else None,
        evidence_hits=_evidence(result.evidence_hits) if isinstance(result, GoldenScore) else None,
        text_claims=_text_claims(result.text_claims) if isinstance(result, GoldenScore) else None,
    )


def _ratio(rate: Rate | Tally) -> Ratio:
    if isinstance(rate, Tally):
        return Ratio(n=rate.n, correct=rate.correct, rate=rate.accuracy)
    return Ratio(n=rate.n, correct=rate.correct, rate=rate.rate)


def _extras(score: ExtrasScore | None) -> ExtrasRecord | None:
    if score is None:
        return None
    return ExtrasRecord(
        extras_sha256=score.extras_sha256,
        paraphrase=_ratio(score.paraphrase),
        paraphrase_origin=_ratio(score.paraphrase_origin),
        paraphrase_gap=score.paraphrase_gap,
        unanswerable_abstained=_ratio(score.unanswerable),
        conflict_pass=_ratio(score.conflict),
        conflict_values_shown=_ratio(score.conflict_values_shown),
        conflict_answer_right=_ratio(score.conflict_answer_right),
        estimate_pass=_ratio(score.estimate),
        estimate_value_right=_ratio(score.estimate_value_right),
        estimate_labelled=_ratio(score.estimate_labelled),
    )


def _answer_v11(score: AnswerV11Score | None) -> AnswerV11Record | None:
    if score is None:
        return None
    return AnswerV11Record(
        answers=score.answers,
        abstained=score.abstained,
        abstain_rate=score.abstain_rate,
        not_abstained_accuracy=_ratio(score.not_abstained),
        abstained_accuracy=_ratio(score.abstained_tally),
        with_confidence=score.with_confidence,
        calibration=[CalibrationBucket(**bucket.model_dump()) for bucket in score.calibration],
    )


def _evidence_group(group: EvidenceGroup) -> EvidenceHitsGroup:
    return EvidenceHitsGroup(
        questions=group.questions,
        with_boxes=group.with_evidence,
        precision=_ratio(group.precision),
        recall=_ratio(group.recall),
    )


def _evidence(score: EvidenceScore | None) -> EvidenceHitsRecord | None:
    if score is None:
        return None
    return EvidenceHitsRecord(
        rule=score.rule,
        overall=_evidence_group(score.overall),
        by_source={key: _evidence_group(group) for key, group in score.by_source.items()},
        by_source_family={
            key: _evidence_group(group) for key, group in score.by_source_family.items()
        },
    )


def _text_claims(score: TextClaimsScore | None) -> TextClaimsRecord | None:
    if score is None:
        return None
    return TextClaimsRecord(
        claims_sha256=score.claims_sha256,
        passed=_ratio(score.passed),
        numbers=_ratio(score.numbers),
        names=_ratio(score.names),
        without_claims=len(score.without_claims),
    )


def _tables(score: TableScore | None) -> TablesRecord | None:
    if score is None:
        return None
    return TablesRecord(
        files=score.files,
        tables_found=_ratio(score.tables_found),
        tables_extra=score.tables_extra,
        row_recall=_ratio(score.row_recall),
        row_precision=_ratio(score.row_precision),
        cell_accuracy=_ratio(score.cell_accuracy),
    )


def _conflict_counts(counts: QuantityCounts) -> ConflictCounts:
    return ConflictCounts(
        found=Ratio(n=counts.conflicts, correct=counts.found, rate=counts.recall),
        agree=counts.agree,
        false_alarms=counts.false_alarms,
        unlisted=counts.unlisted,
    )


def _conflicts(score: ConflictScore | None) -> ConflictsRecord | None:
    if score is None:
        return None
    return ConflictsRecord(
        files=score.files,
        overall=_conflict_counts(score.overall),
        by_quantity={key: _conflict_counts(c) for key, c in sorted(score.by_quantity.items())},
    )


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
    provenance: Provenance,
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
        commit=provenance.commit,
        dirty=provenance.dirty,
        committed_at=provenance.committed_at,
        eval_commit=provenance.eval_commit,
        eval_dirty=provenance.eval_dirty,
        settings=provenance.settings,
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
        room_area_estimates={
            source: AreaEstimates(
                rooms=len(stats.area_estimated.errors) + stats.area_estimated_missing,
                missing=stats.area_estimated_missing,
                median_error=stats.area_estimated.median_error,
                within_10=stats.area_estimated.within_10,
                within_20=stats.area_estimated.within_20,
            )
            for source, stats in sorted(result.rooms.items())
            if stats.area_estimated.errors or stats.area_estimated_missing
        },
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
        tables=_tables(result.tables),
        conflicts=_conflicts(result.conflicts),
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


def _settings_text(record: RunRecord | ExtractionRecord) -> str:
    return " ".join(f"{key}={value}" for key, value in sorted((record.settings or {}).items()))


def code_time(record: RunRecord | ExtractionRecord) -> datetime:
    """When the code that made the predictions existed: its commit time for a clean run, else the
    time the run was recorded (uncommitted code is only known to exist then). Progress and the
    series go in this order, so a run backfilled from an old commit lands where its code was."""
    if record.committed_at is not None and not record.dirty:
        return record.committed_at
    return record.recorded_at


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
    for record in sorted(records, key=code_time):  # stable: recording order breaks ties
        groups.setdefault((record.name, _target(record)), []).append(record)
    lines: list[str] = []
    for (name, target), runs in sorted(groups.items()):
        for metric, value_of in metrics:
            values = [(code_time(r), v) for r in runs if (v := value_of(r)) is not None]
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
    """Per method and target: the first, latest and best value of each headline number, in code
    order (`code_time`)."""
    header = (
        f"{'part':<10}  {'name':<26}  {'against':<12}  {'metric':<12}  {'runs':>4}  "
        f"{'first':>15}  {'latest':>15}  {'best':>15}  {'pts':>7}"
    )
    lines = [
        "How we improved: first vs latest vs best per method (day hh:mm of the code: commit time"
        " of a clean run, else when recorded; pts = latest - first)"
    ]
    lines.append(header)
    lines += _progress_rows("extraction", extraction, EXTRACTION_METRICS)
    lines += _progress_rows("answering", answering, ANSWERING_METRICS)
    return "\n".join(lines)


# The backend setting whose answers are fit on dev.jsonl: with it, the golden dev part scores the
# abstained answers in-sample (Bogdan's series, golden-9 brief).
IN_SAMPLE_SETTING = ("answer_prior", "dev")


@dataclass(frozen=True)
class SeriesPoint:
    """One commit of a method on the golden set: its latest Part 1 and Part 2 records."""

    commit: str
    dirty: bool
    time: datetime
    extraction: ExtractionRecord | None
    answering: RunRecord | None

    @property
    def settings(self) -> dict[str, str]:
        for record in (self.answering, self.extraction):
            if record is not None and record.settings is not None:
                return record.settings
        return {}


def series(
    name: str,
    answering: Iterable[RunRecord],
    extraction: Iterable[ExtractionRecord],
    golden_version: str = "v2",
) -> list[SeriesPoint]:
    """The method's points on one golden version, one per (commit, dirty), in code order. Part 2
    counts only runs that read the pipeline's own extraction; of several runs of one part at a
    point, the latest recorded wins."""
    found: dict[tuple[str, bool], dict[str, RunRecord | ExtractionRecord]] = {}
    for record in [*extraction, *answering]:
        if record.name != name or record.against != "golden":
            continue
        if record.golden_version != golden_version:
            continue
        if isinstance(record, RunRecord) and record.reads != "pipeline-extraction":
            continue
        parts = found.setdefault((record.commit, record.dirty), {})
        part = record.part
        if part not in parts or parts[part].recorded_at <= record.recorded_at:
            parts[part] = record
    points: list[SeriesPoint] = []
    for (commit, dirty), parts in found.items():
        part1, part2 = parts.get("extraction"), parts.get("answering")
        points.append(
            SeriesPoint(
                commit=commit,
                dirty=dirty,
                time=max(code_time(record) for record in parts.values()),
                extraction=part1 if isinstance(part1, ExtractionRecord) else None,
                answering=part2 if isinstance(part2, RunRecord) else None,
            )
        )
    return sorted(points, key=lambda point: (point.time, point.commit))


def _split_pct(record: RunRecord | None, split: str) -> str:
    if record is None or record.by_split is None or split not in record.by_split:
        return "n/a"
    return _pct(record.by_split[split].accuracy)


def format_series_markdown(points: Sequence[SeriesPoint], name: str, golden_version: str) -> str:
    """A markdown table of the series to paste into docs/GOLDEN.md or a README: commit, code
    time, the settings that change between points, Part 1 element F1 per source, Part 2
    accuracy overall, dev and holdout, and the share of answers marked abstained."""
    sources = _sources(
        point.extraction.elements_f1_by_source for point in points if point.extraction
    )
    names = sorted({key for point in points for key in point.settings})
    changing = [key for key in names if len({point.settings.get(key) for point in points}) > 1]
    constant = [key for key in names if key not in changing]
    head = [
        "commit", "code time", "settings that change",
        *(f"P1 element F1 {_short(source)}" for source in sources),
        "P2 accuracy", "P2 dev", "P2 holdout", "abstained",
    ]  # fmt: skip
    lines = [
        f"`{name}` on golden {golden_version}: Part 1 read from the drawings, Part 2 answered "
        "from that extraction, all scored by today's eval on the frozen set.",
        "",
        "| " + " | ".join(head) + " |",
        "| " + " | ".join(["---"] * 3 + ["---:"] * (len(head) - 3)) + " |",
    ]
    in_sample = False
    for point in points:
        part1, part2 = point.extraction, point.answering
        shown = " ".join(
            f"{key}={point.settings[key]}" for key in changing if key in point.settings
        )
        f1 = [
            _pct(part1.elements_f1_by_source.get(source)) if part1 else "n/a" for source in sources
        ]
        overall = (
            f"{part2.overall.correct}/{part2.overall.n} ({_pct(part2.overall.accuracy)})"
            if part2
            else "n/a"
        )
        dev = _split_pct(part2, "dev")
        if point.settings.get(IN_SAMPLE_SETTING[0]) == IN_SAMPLE_SETTING[1] and dev != "n/a":
            dev, in_sample = dev + " †", True
        v11 = part2.answer_v1_1 if part2 else None
        abstained = _pct(v11.abstain_rate) if v11 else "n/a"
        cells = [
            point.commit + ("*" if point.dirty else ""),
            f"{point.time:%Y-%m-%d %H:%M}",
            shown or "-",
            *f1,
            overall,
            dev,
            _split_pct(part2, "holdout"),
            abstained,
        ]
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    lines.append(
        "Code time is the commit time (Europe/Helsinki); `*` marks a run recorded with uncommitted "
        "changes, timed when recorded. Abstained: share of golden answers marked `abstain` "
        "(n/a: no answer_v1.1 fields)."
    )
    if in_sample:
        setting = "=".join(IN_SAMPLE_SETTING)
        lines.append("")
        lines.append(
            f"† In-sample: with {setting} an abstained answer carries the dev prior's value, and "
            "the prior is fit on dev.jsonl, which holds the golden dev questions. The holdout "
            "column is the honest number for the prior."
        )
    if constant:
        same = ", ".join(f"{key}={points[0].settings[key]}" for key in constant)
        lines += ["", f"Settings the same at every point: {same}."]
    return "\n".join(lines)


def write_history_csv(path: Path, records: Iterable[RunRecord]) -> None:
    """One row per run with the overall numbers and an accuracy and a coverage column per
    source/type, for a chart."""
    rows = list(records)
    groups = sorted({key for record in rows for key in record.by_source_type})
    sources = _sources(source_accuracy(record) for record in rows)
    splits = sorted({key for record in rows for key in record.by_split or {}})
    fields = [
        "recorded_at", "code_time", "commit", "dirty", "settings", "name", "note", "against",
        "golden_version", "milestone", "n", "correct", "accuracy", "answered", "coverage",
        "numeric_accuracy", "evidence_coverage", "cost_total_usd", "cost_mean_usd",
        "latency_mean_s", "latency_p95_s", "reads", "abstain_rate",
        *(f"accuracy {split}" for split in splits), *(f"accuracy {source}" for source in sources),
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
                "code_time": code_time(record).isoformat(),
                "commit": record.commit,
                "dirty": record.dirty,
                "settings": _settings_text(record),
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
                "abstain_rate": record.answer_v1_1.abstain_rate if record.answer_v1_1 else None,
            }
            for split, stats in (record.by_split or {}).items():
                row[f"accuracy {split}"] = stats.accuracy
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
        "recorded_at", "code_time", "commit", "dirty", "settings", "name", "note", "against",
        "golden_version", "milestone", "files", "predicted", "multiplicity", "elements_f1",
        "room_f1", "room_type_accuracy", "room_area_accuracy", "plans_exact", "counts_exact",
        "scale_status", "scale_m_per_unit", "scale_estimate_median_error",
        "scale_estimate_within_20",
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
                "code_time": code_time(record).isoformat(),
                "commit": record.commit,
                "dirty": record.dirty,
                "settings": _settings_text(record),
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

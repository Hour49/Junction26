"""The `pipeline` series: which code made a run (--commit, --setting), code-time order, and the
markdown table that shows the product getting better (golden-9)."""

import csv
import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from stoa_eval import cli
from stoa_eval.cli import REPO, main
from stoa_eval.extras_scoring import score_golden
from stoa_eval.history import (
    Provenance,
    code_time,
    format_progress,
    format_series_markdown,
    make_record,
    read_extraction_history,
    read_history,
    series,
    write_extraction_csv,
    write_history_csv,
)
from stoa_eval.models import Answer, ExtractionRecord, Ratio, RunRecord
from stoa_eval.run_store import run_stem, write_record
from stoa_eval.scoring import score
from tests.factories import golden_item

HELSINKI = ZoneInfo("Europe/Helsinki")
T0 = datetime(2026, 11, 13, 17, 0, tzinfo=HELSINKI)
Reads = Literal["gold-extraction", "pipeline-extraction"]


def part2(
    commit: str,
    *,
    committed: datetime = T0,
    recorded: datetime = T0 + timedelta(hours=8),
    dirty: bool = False,
    name: str = "pipeline",
    reads: Reads = "pipeline-extraction",
    version: str = "v2",
    settings: dict[str, str] | None = None,
    right: tuple[bool, bool] = (True, False),
    abstain: bool | None = None,
) -> RunRecord:
    """Two golden questions, one dev (swiss) and one holdout (ifc); `right` says which is right."""
    golden = [
        golden_item(5, "count", "count", id_=1, split="dev"),
        golden_item(7, "count", "count", id_=2, split="holdout", source="ifc_models"),
    ]
    answers = [
        Answer(id=item.id, answer=item.answer if ok else 0, unit="count", evidence=[],
               method="t", cost_usd=0.0, latency_s=0.0, abstain=abstain if i == 1 else None)
        for i, (item, ok) in enumerate(zip(golden, right, strict=True))
    ]  # fmt: skip
    return make_record(
        score_golden(score(golden, answers), golden, answers),
        against="golden",
        name=name,
        note=None,
        milestone=False,
        golden_version=version,
        questions_sha256="q" * 64,
        score_sha256="s" * 64,
        provenance=Provenance(commit, dirty, committed, settings=settings),
        now=recorded,
        reads=reads,
    )


def part1(
    commit: str,
    *,
    committed: datetime = T0,
    recorded: datetime = T0 + timedelta(hours=8),
    dirty: bool = False,
    f1: dict[str, float | None] | None = None,
    settings: dict[str, str] | None = None,
) -> ExtractionRecord:
    nothing = Ratio(n=0, correct=0, rate=None)
    return ExtractionRecord(
        recorded_at=recorded, commit=commit, dirty=dirty, committed_at=committed,
        settings=settings, name="pipeline", note=None, part="extraction", against="golden",
        golden_version="v2", milestone=False, gold_sha256="g" * 64, score_sha256="s" * 64,
        files=2, predicted=2, multiplicity=False, elements_f1=None,
        elements_f1_by_source=f1 or {}, room_f1=None, room_type_accuracy=None,
        room_area_accuracy=None, plans_exact=nothing, counts_exact=nothing,
        counts_exact_by_source={}, scale_status=nothing, scale_m_per_unit=nothing,
        scale_m_per_unit_by_case={}, scale_estimate_median_error=None,
        scale_estimate_within_20=None,
    )  # fmt: skip


def keep(folder: Path, record: RunRecord | ExtractionRecord) -> None:
    stem = run_stem(record.recorded_at, record.part, record.name, [folder])
    write_record(folder / f"{stem}.json", record)


def test_a_record_keeps_the_split_numbers_and_plain_settings_only() -> None:
    row = part2("abc1234", settings={"extractor_vector": "pdf"})
    assert row.by_split is not None
    assert {key: stats.accuracy for key, stats in row.by_split.items()} == {
        "dev": 1.0, "holdout": 0.0
    }  # fmt: skip
    assert row.settings == {"extractor_vector": "pdf"}
    data = json.loads(row.model_dump_json())
    for bad in ({"extractor_vector": "../data/stoa/x"}, {"Extractor": "pdf"}, {"a": ""}):
        with pytest.raises(ValidationError):
            RunRecord.model_validate({**data, "settings": bad})
    with pytest.raises(ValidationError):
        RunRecord.model_validate({**data, "eval_commit": "HEAD"})


def test_code_time_is_the_commit_time_of_clean_code_only() -> None:
    late = T0 + timedelta(hours=8)
    assert code_time(part2("abc1234", committed=T0, recorded=late)) == T0
    assert code_time(part2("abc1234", committed=T0, recorded=late, dirty=True)) == late
    assert code_time(part1("abc1234", committed=T0, recorded=late)) == T0


def test_progress_goes_in_code_order_so_a_backfill_counts_as_first(tmp_path: Path) -> None:
    # the newer commit was recorded first; the old commit was backfilled an hour later
    keep(tmp_path, part2("bbbbbbb", committed=T0 + timedelta(hours=6),
                         recorded=T0 + timedelta(hours=8), right=(True, True)))  # fmt: skip
    keep(tmp_path, part2("aaaaaaa", committed=T0, recorded=T0 + timedelta(hours=9),
                         right=(False, False)))  # fmt: skip
    [line] = [row for row in format_progress(read_history(tmp_path), []).splitlines()
              if "pipeline" in row]  # fmt: skip
    cells = line.split()
    assert cells[6:9] == ["0.0%", "13", "17:00"]  # first: the old commit, at its commit time
    assert cells[9:12] == ["100.0%", "13", "23:00"]  # latest: the newer commit
    assert cells[15] == "+100.0"


def test_series_pairs_both_parts_per_commit_in_code_order(tmp_path: Path) -> None:
    old, new = T0, T0 + timedelta(hours=7)
    keep(tmp_path, part1("bbbbbbb", committed=new, f1={"cubicasa5k": 0.5, "ifc_models": None}))
    keep(tmp_path, part2("bbbbbbb", committed=new, right=(False, True)))
    later = part2("bbbbbbb", committed=new, right=(True, True), recorded=T0 + timedelta(hours=9))
    keep(tmp_path, later)  # the latest recorded run of a part wins
    backfill = part2(
        "aaaaaaa", committed=old, recorded=T0 + timedelta(hours=10), right=(False, False)
    )
    keep(tmp_path, backfill)  # recorded last, older code, no Part 1
    keep(tmp_path, part2("ccccccc", reads="gold-extraction"))  # not the product end to end
    keep(tmp_path, part2("ddddddd", name="vision"))
    keep(tmp_path, part2("eeeeeee", version="v1"))
    points = series("pipeline", read_history(tmp_path), read_extraction_history(tmp_path))
    assert [(p.commit, p.time) for p in points] == [("aaaaaaa", old), ("bbbbbbb", new)]
    assert points[0].extraction is None and points[0].answering is not None
    assert points[1].extraction is not None and points[1].answering is not None
    assert points[1].answering.overall.correct == 2
    [v1] = series("pipeline", read_history(tmp_path), [], golden_version="v1")
    assert v1.commit == "eeeeeee"
    # a dirty run at the same commit is other code: its own point
    keep(tmp_path, part2("bbbbbbb", dirty=True, recorded=T0 + timedelta(hours=11)))
    points = series("pipeline", read_history(tmp_path), read_extraction_history(tmp_path))
    assert [(p.commit, p.dirty) for p in points][-1] == ("bbbbbbb", True)
    assert len(points) == 3


def test_series_table_has_the_columns_and_the_in_sample_mark() -> None:
    hello = {"extractor_vector": "hello", "log_level": "INFO"}
    prior = {"extractor_vector": "pdf", "answer_prior": "dev", "log_level": "INFO"}
    points = [
        *series("pipeline", [part2("aaaaaaa", settings=hello, right=(False, False))],
                [part1("aaaaaaa", settings=hello, f1={"cubicasa5k": 0.0})]),
        *series("pipeline",
                [part2("bbbbbbb", committed=T0 + timedelta(hours=7), settings=prior,
                       abstain=True)],
                [part1("bbbbbbb", committed=T0 + timedelta(hours=7), settings=prior,
                       f1={"cubicasa5k": 0.25, "swiss_dwellings": 0.875})]),
    ]  # fmt: skip
    table = format_series_markdown(points, "pipeline", "v2")
    lines = table.splitlines()
    head = [cell.strip() for cell in lines[2].strip("|").split("|")]
    assert head == ["commit", "code time", "settings that change", "P1 element F1 cubi",
                    "P1 element F1 swiss", "P2 accuracy", "P2 dev", "P2 holdout",
                    "abstained"]  # fmt: skip
    rows = [[cell.strip() for cell in line.strip("|").split("|")] for line in lines[4:6]]
    assert rows[0] == ["aaaaaaa", "2026-11-13 17:00", "extractor_vector=hello", "0.0%", "n/a",
                       "0/2 (0.0%)", "0.0%", "0.0%", "n/a"]  # fmt: skip
    assert rows[1] == ["bbbbbbb", "2026-11-14 00:00",
                       "answer_prior=dev extractor_vector=pdf", "25.0%", "87.5%",
                       "1/2 (50.0%)", "100.0% †", "0.0%", "50.0%"]  # fmt: skip
    assert "† In-sample" in table and "holdout column is the honest number" in table
    assert "Settings the same at every point: log_level=INFO." in table
    # no dev prior: no mark and no in-sample note; a dirty point is starred
    plain = format_series_markdown(
        series("pipeline", [part2("aaaaaaa", settings=hello, dirty=True)], []), "pipeline", "v2"
    )
    assert "†" not in plain and "| aaaaaaa* |" in plain


def test_csv_has_code_time_splits_abstain_rate_and_settings(tmp_path: Path) -> None:
    keep(tmp_path, part2("aaaaaaa", settings={"question_parser": "templates", "a": "b"},
                         abstain=True))  # fmt: skip
    keep(tmp_path, part1("aaaaaaa", settings={"question_parser": "templates"}))
    write_history_csv(tmp_path / "a.csv", read_history(tmp_path))
    [row] = list(csv.DictReader((tmp_path / "a.csv").open(encoding="utf-8")))
    assert row["code_time"] == T0.isoformat() and row["recorded_at"] != row["code_time"]
    assert (row["accuracy dev"], row["accuracy holdout"]) == ("1.0", "0.0")
    assert row["abstain_rate"] == "0.5" and row["settings"] == "a=b question_parser=templates"
    write_extraction_csv(tmp_path / "e.csv", read_extraction_history(tmp_path))
    [row] = list(csv.DictReader((tmp_path / "e.csv").open(encoding="utf-8")))
    assert row["code_time"] == T0.isoformat() and row["settings"] == "question_parser=templates"


def run(*argv: str | Path) -> int:
    return main([str(arg) for arg in argv])


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True,
                          check=True).stdout.strip()  # fmt: skip


def test_score_records_an_export_commit_and_its_settings(
    questions_file: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    split, out = tmp_path / "split", tmp_path / "golden"
    assert run("split", "--questions", questions_file, "--out-dir", split) == 0
    assert run("select", "--questions", questions_file, "--split-dir", split, "--out-dir", out) == 0
    golden, oracle = out / "golden_v1.jsonl", tmp_path / "oracle.jsonl"
    assert run("baseline", "oracle", "--golden", golden, "--out", oracle) == 0
    results, runs = tmp_path / "results", tmp_path / "runs"
    common = ("score", oracle, "--golden", golden, "--split-dir", split, "--results", results,
              "--runs-dir", runs, "--name", "pipeline")  # fmt: skip

    capsys.readouterr()
    for bad, message in (
        (("--commit", "0" * 40), "not a commit of this repo"),
        (("--setting", "EXTRACTOR_VECTOR"), "give NAME=VALUE"),
        (("--setting", "questions=../data/stoa/split/dev.jsonl"), "no paths"),
        (("--setting", "a=b", "--setting", "A=c"), "given twice"),
    ):
        assert run(*common, *bad) == 1
        assert message in capsys.readouterr().err
    assert not results.exists() and not runs.exists()  # refused before anything was written

    head = git("rev-parse", "HEAD")
    assert run(*common, "--commit", head, "--setting", "EXTRACTOR_VECTOR=pdf",
               "--setting", "question_parser=templates") == 0  # fmt: skip
    assert run(*common) == 0  # without --commit: HEAD of this tree, as before
    exported, plain = read_history(results)
    short = git("rev-parse", "--short", "HEAD")
    when = datetime.fromisoformat(git("show", "-s", "--format=%cI", "HEAD"))
    assert (exported.commit, exported.dirty, exported.committed_at) == (short, False, when)
    assert exported.eval_commit == short and exported.eval_dirty == plain.dirty
    assert exported.settings == {"extractor_vector": "pdf", "question_parser": "templates"}
    assert exported.committed_at is not None  # stored in Helsinki time, like recorded_at
    assert exported.committed_at.utcoffset() == when.astimezone(HELSINKI).utcoffset()
    assert (plain.commit, plain.committed_at, plain.eval_commit, plain.settings) == (
        short, when, None, None
    )  # fmt: skip


def test_series_command(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run("series", "--results", tmp_path) == 1
    assert "no recorded golden v2 runs named 'pipeline'" in capsys.readouterr().err
    keep(tmp_path, part2("aaaaaaa"))
    keep(tmp_path, part2("bbbbbbb", name="vision"))
    assert run("series", "--results", tmp_path) == 0
    printed = capsys.readouterr().out
    assert "| aaaaaaa |" in printed and "bbbbbbb" not in printed
    assert run("series", "--results", tmp_path, "--name", "vision") == 0
    assert "| bbbbbbb |" in capsys.readouterr().out


def test_commit_time_is_kept_in_helsinki_time(monkeypatch: pytest.MonkeyPatch) -> None:
    # GitHub writes merge commits in +01:00; the record keeps Helsinki time like recorded_at
    monkeypatch.setattr(cli, "_git", lambda *args: "2026-11-13T22:24:38+01:00")
    when = cli._committed_at("0f9120f")  # pyright: ignore[reportPrivateUsage]
    assert when.isoformat() == "2026-11-13T23:24:38+02:00"

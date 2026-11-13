"""The results history: aggregate rows only, append-only, oldest first, eval only at milestones."""

import csv
import hashlib
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from stoa_eval.cli import main
from stoa_eval.history import (
    format_history,
    format_progress,
    make_record,
    read_history,
    source_accuracy,
    write_history_csv,
)
from stoa_eval.models import SCHEMA_DIR, Against, Answer, RunRecord
from stoa_eval.run_store import migrate_jsonl, read_records, run_stem, slug, write_record
from stoa_eval.scoring import p95, score
from tests.factories import golden_item

HELSINKI = ZoneInfo("Europe/Helsinki")
T0 = datetime(2026, 11, 13, 21, 0, tzinfo=HELSINKI)
SECRET_QUESTION = "How many saunas are behind door 7 of site 1234?"
SECRET_ANSWER = "the secret drawing answer"
# Keys that would carry question text, answers or file names into the public repo.
FORBIDDEN = {"question", "answer", "gold", "path", "file", "template", "items", "needs_review",
             "evidence", "group", "id", "extra_answer_ids"}  # fmt: skip


def property_names(schema: Any) -> set[str]:
    names: set[str] = set()
    if isinstance(schema, dict):
        for key, value in schema.items():
            if key == "properties":
                names |= set(value)
            names |= property_names(value)
    elif isinstance(schema, list):
        for value in schema:
            names |= property_names(value)
    return names


def record(
    *,
    now: datetime = T0,
    against: Against = "golden",
    name: str = "m",
    milestone: bool = False,
    right: bool = True,
) -> RunRecord:
    gold = golden_item(SECRET_ANSWER, None, "text").model_copy(update={"question": SECRET_QUESTION})
    reply = Answer(id=1, answer=SECRET_ANSWER if right else "no", unit=None, evidence=[],
                   method="t", cost_usd=0.5, latency_s=2.0)  # fmt: skip
    return make_record(
        score([gold], [reply]),
        against=against,
        name=name,
        note=None,
        milestone=milestone,
        golden_version="v1" if against == "golden" else None,
        questions_sha256="q" * 64,
        score_sha256="s" * 64,
        commit="abc1234",
        dirty=False,
        now=now,
    )


def test_a_row_holds_aggregates_only() -> None:
    schema = json.loads((SCHEMA_DIR / "run_record_v1.schema.json").read_text(encoding="utf-8"))
    assert not property_names(schema) & FORBIDDEN
    assert schema["additionalProperties"] is False
    row = record().model_dump_json()
    assert SECRET_QUESTION not in row and SECRET_ANSWER not in row
    assert json.loads(row)["overall"] == {
        "n": 1, "correct": 1, "accuracy": 1.0, "answered": None, "coverage": None
    }  # fmt: skip
    with pytest.raises(ValidationError):
        RunRecord.model_validate({**json.loads(row), "question": SECRET_QUESTION})


def keep(folder: Path, row: RunRecord) -> Path:
    path = folder / f"{run_stem(row.recorded_at, 'answering', row.name, [folder])}.json"
    write_record(path, row)
    return path


def test_one_file_per_run_named_uniquely_and_never_overwritten(tmp_path: Path) -> None:
    assert slug("pdf-extract/Swiss counts v2!") == "pdf-extract-swiss-counts-v2"
    first = keep(tmp_path, record(name="Swiss counts"))
    second = keep(tmp_path, record(name="Swiss counts"))  # the same second
    assert first.name == "20261113-210000-answering-swiss-counts.json"
    assert second.name == "20261113-210000-answering-swiss-counts-2.json"
    with pytest.raises(FileExistsError):
        write_record(first, record(name="again"))
    assert [r.name for r in read_records(tmp_path)] == ["Swiss counts", "Swiss counts"]


def test_migration_keeps_every_row(tmp_path: Path) -> None:
    old = Path(__file__).parent / "data/runs_v1.jsonl"  # the 5 rows of the old shared file
    written = migrate_jsonl(old, tmp_path / "runs")
    rows = [json.loads(line) for line in old.read_text(encoding="utf-8").splitlines()]
    assert len(written) == len(rows) == 5
    migrated = read_records(tmp_path / "runs")
    defaults = {"part", "reads", "extras", "answer_v1_1"}  # fields added after these rows
    assert [r.model_dump(mode="json", exclude=defaults) for r in migrated] == rows
    assert {path.name for path in written} >= {"20261113-204152-answering-oracle.json"}


def test_history_is_oldest_first_and_filters(tmp_path: Path) -> None:
    keep(tmp_path, record(name="late", now=T0 + timedelta(hours=2)))
    keep(tmp_path, record(name="early", now=T0))
    keep(tmp_path, record(name="dev run", now=T0 + timedelta(hours=1), against="dev"))
    assert [r.name for r in read_history(tmp_path)] == ["early", "dev run", "late"]
    assert [r.name for r in read_history(tmp_path, "golden")] == ["early", "late"]
    assert read_history(tmp_path / "none") == []
    table = format_history(read_history(tmp_path))
    assert table.index("early") < table.index("dev run") < table.index("late")
    assert "swiss" in table.splitlines()[1]  # a per-source accuracy column
    assert source_accuracy(read_history(tmp_path)[0]) == {"swiss_dwellings": 1.0}
    out = tmp_path / "history.csv"
    write_history_csv(out, read_history(tmp_path))
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    assert [row["name"] for row in rows] == ["early", "dev run", "late"]
    assert rows[0]["accuracy swiss_dwellings/text"] == "1.0"
    assert rows[0]["accuracy swiss_dwellings"] == "1.0"


def test_progress_shows_first_latest_and_best(tmp_path: Path) -> None:
    keep(tmp_path, record(name="vision", now=T0, right=False))
    keep(tmp_path, record(name="vision", now=T0 + timedelta(hours=1)))
    keep(tmp_path, record(name="vision", now=T0 + timedelta(hours=2), right=False))
    [line] = [row for row in format_progress(read_history(tmp_path), []).splitlines()
              if "vision" in row]  # fmt: skip
    cells = line.split()
    assert cells[:5] == ["answering", "vision", "golden", "v1", "accuracy"]
    assert cells[5] == "3"  # runs
    assert cells[6:9] == ["0.0%", "13", "21:00"]  # first
    assert cells[9:12] == ["0.0%", "13", "23:00"]  # latest
    assert cells[12:15] == ["100.0%", "13", "22:00"]  # best
    assert cells[15] == "+0.0"


def test_eval_is_recorded_only_as_a_milestone() -> None:
    with pytest.raises(ValidationError, match="milestone"):
        record(against="eval")
    assert record(against="eval", milestone=True).milestone


def test_p95() -> None:
    assert p95([float(n) for n in range(1, 101)]) == 95.0
    assert p95([3.0]) == 3.0
    assert p95([]) is None


def run(*argv: str | Path) -> int:
    return main([str(arg) for arg in argv])


def test_score_records_by_default_and_history_commands(
    questions_file: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    split, out = tmp_path / "split", tmp_path / "golden"
    assert run("split", "--questions", questions_file, "--out-dir", split) == 0
    assert run("select", "--questions", questions_file, "--split-dir", split, "--out-dir", out) == 0
    golden = out / "golden_v1.jsonl"
    oracle = tmp_path / "oracle.jsonl"
    assert run("baseline", "oracle", "--golden", golden, "--out", oracle) == 0
    results, runs = tmp_path / "results/runs", tmp_path / "data-runs"
    common = ("--golden", golden, "--split-dir", split, "--results", results, "--runs-dir", runs)
    assert run("score", oracle, *common, "--name", "oracle", "--note", "plumbing") == 0
    [kept] = list(results.glob("*.json"))
    assert re.fullmatch(r"\d{8}-\d{6}-answering-oracle\.json", kept.name)
    row = json.loads(kept.read_text(encoding="utf-8"))
    assert re.fullmatch(r"[0-9a-f]{7,40}", row["commit"]) and isinstance(row["dirty"], bool)
    assert (row["against"], row["golden_version"], row["note"]) == ("golden", "v1", "plumbing")
    detail = runs / kept.name  # the full score, same stem, gitignored folder
    assert row["score_sha256"] == hashlib.sha256(detail.read_bytes()).hexdigest()
    assert datetime.fromisoformat(row["recorded_at"]).utcoffset() is not None

    capsys.readouterr()
    assert run("score", oracle, *common) == 1
    assert "give --name" in capsys.readouterr().err
    assert run("score", oracle, *common, "--against", "eval", "--name", "x") == 1
    assert "refused" in capsys.readouterr().err
    assert run("score", oracle, *common, "--name", "x", "--out", tmp_path / "o.json") == 1
    assert "--out is for --no-record" in capsys.readouterr().err
    scratch = tmp_path / "scratch.json"
    assert run("score", oracle, *common, "--no-record", "--out", scratch) == 0
    assert run("score", oracle, *common, "--against", "eval", "--no-record", "--out", scratch) == 0
    assert len(list(results.glob("*.json"))) == 1 and len(list(runs.glob("*.json"))) == 1
    assert run("score", oracle, *common, "--against", "dev", "--name", "dev") == 0
    assert run("score", oracle, *common, "--against", "eval", "--name", "m1", "--milestone") == 0
    assert len(list(results.glob("*.json"))) == 3

    capsys.readouterr()
    charts = tmp_path / "charts"
    assert run("history", "--results", results, "--csv", charts) == 0
    printed = capsys.readouterr().out
    assert "Part 1, extraction" in printed and "Part 2, answering" in printed
    assert printed.index("oracle") < printed.index("dev") < printed.index("eval (milestone)")
    assert len((charts / "answering.csv").read_text(encoding="utf-8").splitlines()) == 4
    assert (charts / "extraction.csv").read_text(encoding="utf-8").count("\n") == 1  # header
    assert run("history", "--results", results, "--progress") == 0
    assert "first vs latest vs best" in capsys.readouterr().out

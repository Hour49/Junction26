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
    append_record,
    format_history,
    make_record,
    read_history,
    write_history_csv,
)
from stoa_eval.models import SCHEMA_DIR, Against, Answer, RunRecord
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
    *, now: datetime = T0, against: Against = "golden", name: str = "m", milestone: bool = False
) -> RunRecord:
    gold = golden_item(SECRET_ANSWER, None, "text").model_copy(update={"question": SECRET_QUESTION})
    reply = Answer(id=1, answer=SECRET_ANSWER, unit=None, evidence=[], method="t", cost_usd=0.5,
                   latency_s=2.0)  # fmt: skip
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


def test_append_only(tmp_path: Path) -> None:
    results = tmp_path / "runs.jsonl"
    append_record(results, record(name="first"))
    first = results.read_text(encoding="utf-8")
    append_record(results, record(name="second"))
    text = results.read_text(encoding="utf-8")
    assert text.startswith(first) and len(text.splitlines()) == 2


def test_history_is_oldest_first_and_filters(tmp_path: Path) -> None:
    results = tmp_path / "runs.jsonl"
    append_record(results, record(name="late", now=T0 + timedelta(hours=2)))
    append_record(results, record(name="early", now=T0))
    append_record(results, record(name="dev run", now=T0 + timedelta(hours=1), against="dev"))
    assert [r.name for r in read_history(results)] == ["early", "dev run", "late"]
    assert [r.name for r in read_history(results, "golden")] == ["early", "late"]
    assert read_history(tmp_path / "none.jsonl") == []
    table = format_history(read_history(results))
    assert table.index("early") < table.index("dev run") < table.index("late")
    out = tmp_path / "history.csv"
    write_history_csv(out, read_history(results))
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    assert [row["name"] for row in rows] == ["early", "dev run", "late"]
    assert rows[0]["accuracy swiss_dwellings/text"] == "1.0"


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


def test_score_record_and_history_commands(
    questions_file: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    split, out = tmp_path / "split", tmp_path / "golden"
    assert run("split", "--questions", questions_file, "--out-dir", split) == 0
    assert run("select", "--questions", questions_file, "--split-dir", split, "--out-dir", out) == 0
    golden = out / "golden_v1.jsonl"
    oracle = tmp_path / "oracle.jsonl"
    assert run("baseline", "oracle", "--golden", golden, "--out", oracle) == 0
    results = tmp_path / "results/runs.jsonl"
    common = ("--golden", golden, "--split-dir", split, "--results", results)
    assert run("score", oracle, *common, "--record", "--name", "oracle", "--note", "plumbing") == 0
    [row] = [json.loads(line) for line in results.read_text(encoding="utf-8").splitlines()]
    assert re.fullmatch(r"[0-9a-f]{7,40}", row["commit"]) and isinstance(row["dirty"], bool)
    assert (row["against"], row["golden_version"], row["note"]) == ("golden", "v1", "plumbing")
    assert (
        row["score_sha256"]
        == hashlib.sha256((tmp_path / "oracle.score.json").read_bytes()).hexdigest()
    )
    assert datetime.fromisoformat(row["recorded_at"]).utcoffset() is not None

    capsys.readouterr()
    assert run("score", oracle, *common, "--against", "eval", "--record", "--name", "x") == 1
    assert "only with --milestone" in capsys.readouterr().err
    assert len(results.read_text(encoding="utf-8").splitlines()) == 1  # nothing appended
    assert run("score", oracle, *common, "--record") == 1
    assert "--record needs --name" in capsys.readouterr().err
    assert run("score", oracle, *common, "--against", "dev", "--record", "--name", "dev") == 0
    eval_run = ("--against", "eval", "--record", "--name", "m1", "--milestone")
    assert run("score", oracle, *common, *eval_run) == 0

    capsys.readouterr()
    chart = tmp_path / "history.csv"
    assert run("history", "--results", results, "--csv", chart) == 0
    printed = capsys.readouterr().out
    assert printed.index("oracle") < printed.index("dev") < printed.index("eval (milestone)")
    assert len(chart.read_text(encoding="utf-8").splitlines()) == 4

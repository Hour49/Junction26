"""The commands end to end on made-up data: split, select, both baselines, score, schema check."""

import hashlib
import json
from pathlib import Path

import pytest

from stoa_eval.cli import main
from stoa_eval.families import group_of
from tests.factories import make_questions, read_json, write_questions


def run(*argv: str | Path) -> int:
    return main([str(arg) for arg in argv])


def lines(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_split(questions: Path, out: Path) -> Path:
    assert run("split", "--questions", questions, "--out-dir", out) == 0
    return out


def test_split_files_are_deterministic_and_disjoint_by_group(
    questions_file: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first = make_split(questions_file, tmp_path / "a")
    assert "cubicasa5k/count" in capsys.readouterr().out
    second = make_split(questions_file, tmp_path / "b")
    for name in ("dev.jsonl", "eval.jsonl", "manifest.json"):
        assert sha(first / name) == sha(second / name), name
    dev, held = lines(first / "dev.jsonl"), lines(first / "eval.jsonl")
    total = len(make_questions())
    assert sorted(int(str(row["id"])) for row in dev + held) == list(range(1, total + 1))
    assert not {group_of(str(row["path"])) for row in dev} & {
        group_of(str(row["path"])) for row in held
    }
    manifest = read_json(first / "manifest.json")
    assert manifest["files_sha256"] == {
        "dev.jsonl": sha(first / "dev.jsonl"),
        "eval.jsonl": sha(first / "eval.jsonl"),
    }
    assert {group_of(str(row["path"])) for row in held} == set(manifest["eval_groups"])


def test_select_baselines_and_score(
    questions_file: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    split = make_split(questions_file, tmp_path / "split")
    out = tmp_path / "golden"
    argv = ("--questions", questions_file, "--split-dir", split, "--out-dir", out)
    assert run("select", *argv) == 0
    assert "in 8 cells" in capsys.readouterr().out
    golden = out / "golden_v1.jsonl"
    eval_ids = {row["id"] for row in lines(split / "eval.jsonl")}
    for item in lines(golden):
        assert (item["id"] in eval_ids) == (item["split"] == "holdout")

    oracle = tmp_path / "runs/oracle.jsonl"
    assert run("baseline", "oracle", "--golden", golden, "--out", oracle) == 0
    assert run("score", oracle, "--golden", golden) == 0
    n = len(lines(golden))
    assert read_json(tmp_path / "runs/oracle.score.json")["overall"] == {
        "n": n,
        "correct": n,
        "accuracy": 1.0,
    }
    floor = tmp_path / "runs/constant.jsonl"
    baseline = ("baseline", "constant", "--golden", golden, "--split-dir", split)
    assert run(*baseline, "--out", floor) == 0
    assert run("score", floor, "--golden", golden, "--out", tmp_path / "floor.json") == 0

    capsys.readouterr()
    assert run("score", oracle, "--against", "all", "--split-dir", split) == 0
    result = read_json(tmp_path / "runs/oracle.score-all.json")
    assert set(result["by_split"]) == {"dev", "eval"}
    assert result["questions"]["answered"] == n
    assert "sealed split" not in capsys.readouterr().err
    assert run("score", oracle, "--against", "eval", "--split-dir", split) == 0
    assert "warning: sealed split: score at milestones only" in capsys.readouterr().err
    held = read_json(tmp_path / "runs/oracle.score-eval.json")
    assert set(held["by_split"]) == {"eval"}
    assert run("score", oracle, "--against", "dev", "--split-dir", split) == 0


def test_refusals(questions_file: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    split = make_split(questions_file, tmp_path / "split")
    other = write_questions(tmp_path / "other.jsonl", make_questions()[:-1])
    out = tmp_path / "golden"
    assert run("select", "--questions", other, "--split-dir", split, "--out-dir", out) == 1
    assert "is not the file the split" in capsys.readouterr().err
    assert run("select", "--questions", questions_file, "--split-dir", split, "--out-dir", out) == 0

    answers = tmp_path / "answers.jsonl"
    answers.write_text("")
    assert run("score", answers, "--against", "all", "--split-dir", tmp_path / "none") == 1
    assert "run `python -m stoa_eval split` first" in capsys.readouterr().err

    golden = out / "golden_v1.jsonl"
    resplit = ("split", "--questions", questions_file, "--out-dir", split, "--seed", "7")
    assert run(*resplit) == 0
    baseline = ("baseline", "constant", "--golden", golden, "--split-dir", split)
    assert run(*baseline, "--out", tmp_path / "c.jsonl") == 1
    assert "was made from another split" in capsys.readouterr().err

    with (split / "dev.jsonl").open("a", encoding="utf-8") as dev:
        dev.write("\n")
    assert run("score", answers, "--against", "dev", "--split-dir", split) == 1
    assert "changed after the split" in capsys.readouterr().err


def test_bad_input_fails_with_file_and_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = tmp_path / "questions.jsonl"
    bad.write_text('{"path": "data/a/b.png", "question": "q", "answer": 1, "unit": "count"}\n')
    assert run("split", "--questions", bad, "--out-dir", tmp_path / "split") == 1
    assert f"{bad}:1:" in capsys.readouterr().err


def test_schema_check_passes_on_the_committed_schemas() -> None:
    assert run("schema", "--check") == 0

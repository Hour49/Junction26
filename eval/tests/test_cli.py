"""The commands end to end on made-up data: select, both baselines, score, schema check."""

from pathlib import Path

import pytest

from stoa_eval.cli import main
from tests.factories import make_questions, read_json, write_questions


def run(*argv: str | Path) -> int:
    return main([str(arg) for arg in argv])


def test_select_baselines_and_score(
    questions_file: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "golden"
    assert run("select", "--questions", questions_file, "--out-dir", out) == 0
    printed = capsys.readouterr().out
    assert "cubicasa5k count fi" in printed
    assert "in 8 cells" in printed
    golden = out / "golden_v0.jsonl"
    manifest = read_json(out / "golden_v0.manifest.json")
    assert manifest["params"] == {
        "version": "v0",
        "cell_keys": ["source", "type", "language"],
        "per_cell": 4,
        "holdout_ratio": 0.5,
        "seed": 20261113,
    }

    oracle = tmp_path / "runs/oracle.jsonl"
    assert run("baseline", "oracle", "--golden", golden, "--out", oracle) == 0
    assert run("score", oracle, "--golden", golden) == 0
    assert "overall" in capsys.readouterr().out
    oracle_score = read_json(tmp_path / "runs/oracle.score.json")
    assert oracle_score["overall"] == {
        "n": len(golden.read_text().splitlines()),
        "correct": len(golden.read_text().splitlines()),
        "accuracy": 1.0,
    }

    floor = tmp_path / "runs/constant.jsonl"
    argv = ("baseline", "constant", "--golden", golden, "--questions", questions_file)
    assert run(*argv, "--out", floor) == 0
    assert run("score", floor, "--golden", golden, "--out", tmp_path / "floor.json") == 0
    assert (tmp_path / "floor.json").exists()


def test_constant_refuses_another_questions_file(
    questions_file: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "golden"
    assert run("select", "--questions", questions_file, "--out-dir", out) == 0
    other = write_questions(tmp_path / "other.jsonl", make_questions()[:-1])
    argv = ("baseline", "constant", "--golden", out / "golden_v0.jsonl", "--out", tmp_path / "c")
    assert run(*argv, "--questions", other) == 1
    assert "is not the file golden_v0.jsonl was made from" in capsys.readouterr().err
    assert run(*argv, "--questions", questions_file) == 0


def test_bad_input_fails_with_file_and_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = tmp_path / "questions.jsonl"
    bad.write_text('{"path": "data/a/b.png", "question": "q", "answer": 1, "unit": "count"}\n')
    assert run("select", "--questions", bad, "--out-dir", tmp_path) == 1
    assert f"{bad}:1:" in capsys.readouterr().err


def test_schema_check_passes_on_the_committed_schemas() -> None:
    assert run("schema", "--check") == 0

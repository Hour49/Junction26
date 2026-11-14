"""stoa_eval ab: paired statistics, counts against gold, and the command on a made-up split with a
fake backend (CI has no backend environment; the real one is exercised by hand, see
.agents/exp/golden.md)."""

import json
from pathlib import Path
from typing import Any

import pytest

from stoa_eval import backend
from stoa_eval.ab import count_stats, hits_of, mcnemar_p, orientation_label, paired, style_of
from stoa_eval.extraction import Extraction
from stoa_eval.models import Answer, NumberedQuestion
from tests.test_exp_split import DOORS, WINDOWS, dataset, exp_split, run
from tests.test_extraction_scoring import element, extraction

__all__ = ["dataset"]  # the fixture, used by name


def question(id_: int, path: str, answer: int, text: str = DOORS) -> NumberedQuestion:
    return NumberedQuestion(
        id=id_, path=path, question=text, answer=answer, unit="count", type="count"
    )


def reply(id_: int, value: int | None) -> Answer:
    return Answer(
        id=id_, answer=value, unit="count", evidence=[], method="t", cost_usd=0, latency_s=0
    )


def test_mcnemar_exact_p() -> None:
    assert mcnemar_p(0, 0) == 1.0
    assert mcnemar_p(0, 5) == pytest.approx(2 / 32)  # all 5 discordant pairs one way
    assert mcnemar_p(3, 3) == 1.0
    assert mcnemar_p(1, 9) == pytest.approx(2 * 11 / 1024)


def test_hits_count_a_missing_answer_as_wrong() -> None:
    qs = [question(1, "data/cubicasa5k/a-1.png", 2), question(2, "data/cubicasa5k/a-1.png", 0)]
    assert hits_of(qs, {1: reply(1, 2)}) == {1: True, 2: False}
    assert hits_of(qs, {1: reply(1, 3), 2: reply(2, None)}) == {1: False, 2: False}


def test_paired_interval_and_verdict() -> None:
    qs = [question(i, f"data/cubicasa5k/p-{i // 3}.png", 1) for i in range(1, 61)]
    same = {q.id: q.id % 2 == 0 for q in qs}
    tie = paired(qs, same, same, reps=500)
    assert (tie.diff, tie.ci_low, tie.ci_high, tie.verdict) == (0.0, 0.0, 0.0, "no difference")
    worse = {q.id: False for q in qs}
    better = paired(qs, worse, same, reps=500)
    assert better.diff == pytest.approx(0.5) and better.b_only == 30 and better.a_only == 0
    assert better.ci_low is not None and better.ci_low > 0 and better.verdict == "B better"
    assert paired(qs, worse, same, seed=7, reps=500) == paired(qs, worse, same, seed=7, reps=500)
    assert paired(qs, same, worse, reps=500).verdict == "A better"


def test_count_stats_missing_and_unread_are_wrong() -> None:
    doors = [element(f"d{i}", [0.1, 0.1, 0.2, 0.2]) for i in range(3)]
    gold = {
        "data/cubicasa5k/a-1.png": extraction(file="data/cubicasa5k/a-1.png", elements=doors),
        "data/cubicasa5k/a-2.png": extraction(file="data/cubicasa5k/a-2.png", elements=doors[:1]),
        "data/cubicasa5k/a-3.png": extraction(file="data/cubicasa5k/a-3.png"),
    }
    pred: dict[str, Extraction] = {
        "data/cubicasa5k/a-1.png": extraction(file="data/cubicasa5k/a-1.png", elements=doors[:2]),
        "data/cubicasa5k/a-3.png": extraction(file="data/cubicasa5k/a-3.png", read=["window"]),
    }
    stats = count_stats(gold, pred, ["plan", "door"])
    assert stats["door"].exact == 0  # off by one, missing, not read (its 0 would match)
    assert stats["door"].mae == pytest.approx((1 + 1 + 0) / 3)
    assert stats["plan"].exact == 2  # the missing file misses its plan too


def test_style_of() -> None:
    assert style_of("data/cubicasa5k/high_quality_architectural-12.png") == (
        "high_quality_architectural"
    )


def fake_backend(*args: str) -> None:
    """The backend's three commands, for doors and windows only: answers are the derived counts
    of the file's extraction, refused (null) without one; the prior says 1 door, 2 windows."""
    command, opts = args[0], dict(zip(args[1::2], args[2::2], strict=True))
    if command == "prior":
        assert Path(opts["--train"]).name == "train_questions.jsonl"
        Path(opts["--out"]).write_text(json.dumps({"door": 1, "window": 2}), "utf-8")
        return
    rows = [json.loads(line) for line in Path(opts["--questions"]).read_text().splitlines()]
    family = {DOORS: "door", WINDOWS: "window"}
    if command == "families":
        Path(opts["--out"]).write_text(json.dumps({r["id"]: family[r["question"]] for r in rows}))
        return
    drawings: dict[str, Extraction] = {}
    for path in Path(opts["--drawings"]).rglob("*.json"):
        found = Extraction.model_validate_json(path.read_text())
        drawings[found.file] = found
    prior: dict[str, Any] = (
        json.loads(Path(opts["--prior"]).read_text()) if "--prior" in opts else {}
    )
    with Path(opts["--out"]).open("w") as out:
        for row in rows:
            drawing = drawings.get(row["path"])
            kind = family[row["question"]]
            value = prior.get(kind) if drawing is None else drawing.derived_counts().get(kind, 0)
            out.write(reply(row["id"], value).model_dump_json() + "\n")


def test_ab_command_end_to_end(
    dataset: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(backend, "run", fake_backend)
    exp = dataset / "exp"
    assert exp_split(dataset, exp) == 0
    split = json.loads((exp / "split.json").read_text())
    val = split["parts"]["val"]["files"]
    arm = exp / "core" / "half"  # one val image only: the rest are refused
    arm.mkdir(parents=True)
    gold = dataset / "gold/cubicasa5k"
    first = next(p for p in gold.iterdir() if json.loads(p.read_text())["file"] == val[0])
    (arm / "x.json").write_text(first.read_text(), "utf-8")
    common = ("--exp-dir", exp, "--gold", dataset / "gold", "--prior", dataset / "prior.json")
    assert run("ab", "--a", "gold", "--b", arm, *common, "--reps", 200) == 0
    printed = capsys.readouterr().out
    assert "A = gold, B = core-half" in printed
    assert "Verdict (from the interval)" in printed
    assert "McNemar exact p" in printed and "(questions, not independent" in printed
    result = json.loads((exp / "ab/gold-vs-core-half-val.json").read_text())
    questions = [
        json.loads(line) for line in (exp / "val_questions.jsonl").read_text().splitlines()
    ]
    golds = [Extraction.model_validate_json(path.read_text()) for path in gold.iterdir()]
    truth = {found.file: found.derived_counts() for found in golds}

    def right(files: set[str]) -> int:
        kind = {DOORS: "door", WINDOWS: "window"}
        return sum(
            q["answer"] == truth[q["path"]].get(kind[q["question"]], 0)
            for q in questions
            if q["path"] in files
        )

    assert result["a"]["overall"]["hits"] == right(set(val))
    assert result["b"]["missing_images"] == len(val) - 1
    assert result["b"]["overall"]["hits"] == right({val[0]})  # the refused images are wrong
    assert result["b"]["overall"]["n"] == len(questions)  # and still counted
    assert set(result["per_image"]) == set(val)
    assert run("ab", "--a", "none", "--b", "prior", *common, "--reps", 200) == 0
    none_prior = json.loads((exp / "ab/none-vs-prior-val.json").read_text())
    zeros = sum(q["answer"] == 0 for q in questions)
    assert none_prior["a"]["overall"]["hits"] == zeros  # the empty extraction: every count 0
    assert none_prior["b"]["counts"] is None
    ones = sum(q["answer"] == (1 if q["question"] == DOORS else 2) for q in questions)
    assert none_prior["b"]["overall"]["hits"] == ones
    assert none_prior["prior_sha256"] is not None


def test_ab_refuses_a_changed_questions_file(
    dataset: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(backend, "run", fake_backend)
    exp = dataset / "exp"
    assert exp_split(dataset, exp) == 0
    with (exp / "val_questions.jsonl").open("a") as lines:
        lines.write(question(999, "data/cubicasa5k/plan-0.png", 1).model_dump_json() + "\n")
    common = ("--exp-dir", exp, "--gold", dataset / "gold", "--prior", dataset / "prior.json")
    assert run("ab", "--a", "gold", "--b", "none", *common) == 1
    assert "not the file exp-split wrote" in capsys.readouterr().err


def test_ab_on_test_needs_certify_and_is_used_once(
    dataset: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(backend, "run", fake_backend)
    exp = dataset / "exp"
    assert exp_split(dataset, exp) == 0
    common = ("--exp-dir", exp, "--gold", dataset / "gold", "--prior", dataset / "prior.json")
    arms = ("--a", "prior", "--b", "gold", "--part", "test")
    arm = exp / "core" / "x"
    arm.mkdir(parents=True)
    challenger = ("--a", "prior", "--b", arm, "--part", "test")
    assert run("ab", *challenger, *common) == 1
    assert "--certify" in capsys.readouterr().err
    assert not (exp / "ab/prior-vs-core-x-test.json").exists()
    assert run("ab", *challenger, *common, "--certify", "--reps", 50) == 0
    assert run("ab", *challenger, *common, "--certify", "--reps", 50) == 1
    assert "already run on test" in capsys.readouterr().err
    assert run("ab", *arms, *common, "--certify", "--reps", 50) == 0  # references: no record
    runs = json.loads((exp / "test-certified.json").read_text())["runs"]
    assert [(r["command"], r["arm"]) for r in runs] == [("ab", "core-x")]


def test_orientation_labels() -> None:
    assert orientation_label("upright") == "upright"
    assert orientation_label({"turn": 0, "mirrored": False}) == "upright"
    assert orientation_label({"turn": 180, "mirrored": False}) == "turn 180"
    assert orientation_label({"turn": -90, "mirrored": True}) == "turn 270 mirrored"
    with pytest.raises(ValueError, match="orientation"):
        orientation_label({"rotation": 90})


def test_ab_splits_by_the_orientation_file_when_it_exists(
    dataset: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(backend, "run", fake_backend)
    exp = dataset / "exp"
    assert exp_split(dataset, exp) == 0
    common = ("--exp-dir", exp, "--gold", dataset / "gold", "--prior", dataset / "prior.json")
    assert run("ab", "--a", "gold", "--b", "none", *common, "--reps", 50) == 0
    plain = json.loads((exp / "ab/gold-vs-none-val.json").read_text())
    assert plain["a"]["by_orientation"] is None and "no " in plain["orientation"]
    val = json.loads((exp / "split.json").read_text())["parts"]["val"]["files"]
    turns = {file: {"turn": 180 if n == 0 else 0, "mirrored": False} for n, file in enumerate(val)}
    (exp / "orientation.json").write_text(json.dumps(turns), "utf-8")
    assert run("ab", "--a", "gold", "--b", "none", *common, "--reps", 50) == 0
    split = json.loads((exp / "ab/gold-vs-none-val.json").read_text())
    assert split["orientation"].startswith("from ")
    by = split["a"]["by_orientation"]
    assert set(by) == {"upright", "turn 180"}
    questions = [
        json.loads(line) for line in (exp / "val_questions.jsonl").read_text().splitlines()
    ]
    assert by["turn 180"]["n"] == sum(q["path"] == val[0] for q in questions)

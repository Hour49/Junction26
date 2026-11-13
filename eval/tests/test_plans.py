"""Golden v2 by plan: picking, the two-part layout, and scoring both parts, on made-up data."""

import json
from pathlib import Path
from typing import Any, Literal

import pytest

from stoa_eval.cli import main
from stoa_eval.history import read_history
from stoa_eval.plans import PlansParams, pick, pick_scale_cases
from stoa_eval.scale_scoring import ScaleCase
from tests.factories import make_questions, read_json, write_questions
from tests.test_extraction_scoring import extraction


def run(*argv: object) -> int:
    return main([str(arg) for arg in argv])


def test_pick_deals_round_robin_over_strata() -> None:
    stratum_of = {f"data/cubicasa5k/m{n}.png": "multi-plan" for n in range(4)}
    stratum_of |= {f"data/cubicasa5k/s{n}.png": "single-plan" for n in range(8)}
    stratum_of |= {f"data/ifc_models/{m}_plan-0{n}.pdf": m for m in "abc" for n in range(3)}
    params = PlansParams(quotas={"cubicasa5k": (6, 0), "ifc_models": (4, 0)})
    chosen, counts = pick(stratum_of, set(), params)
    cubicasa = [file for file in chosen if "cubicasa5k" in file]
    assert sum("/m" in file for file in cubicasa) == 3 and len(cubicasa) == 6
    models = [file.split("/")[2][0] for file in chosen if "ifc_models" in file]
    assert sorted(models[:3]) == ["a", "b", "c"] and len(models) == 4  # each once before twice
    assert counts["cubicasa5k"] == ((6, 0), (12, 0))
    assert pick(stratum_of, set(), params) == (chosen, counts)  # seeded, so the same again


def test_scale_cases_fill_each_case_in_dev_and_eval() -> None:
    cases: dict[str, tuple[ScaleCase, Literal["dev", "eval"]]] = {}
    for n in range(12):
        cases[f"data/cubicasa5k/n{n}.png"] = ("nothing", "dev")
        cases[f"data/swiss_dwellings/s{n}.pdf"] = ("scale_text_or_bar", "dev")
        cases[f"data/ifc_models/m{n}_plan-01.pdf"] = ("scale_text_or_bar", "eval")
    cases["data/cubicasa5k/x.png"] = ("not_to_scale", "dev")
    chosen: dict[str, Literal["dev", "eval"]] = {"data/cubicasa5k/n0.png": "dev"}
    params = PlansParams(scale_quota=(10, 3))
    extra, counts = pick_scale_cases(cases, chosen, params)
    assert "data/cubicasa5k/n0.png" not in extra  # a plan pick counts first
    assert counts["nothing"] == ((10, 0), (12, 0))
    assert counts["scale_text_or_bar"] == ((10, 3), (12, 12))
    assert counts["not_to_scale"] == ((1, 0), (1, 0))  # short: all there is
    assert sum(cases[file][0] == "nothing" for file in extra) == 9
    assert pick_scale_cases(cases, chosen, params) == (extra, counts)


@pytest.fixture
def dataset(tmp_path: Path) -> Path:
    """questions.jsonl with floors questions, the PNG of every swiss PDF, and a sealed split."""
    rows = make_questions()
    floors = "How many floors (storeys) does this floor plan show?"
    for n in range(1, 7):
        answer = 2 if n in (2, 5) else 1
        path = f"data/cubicasa5k/plan-{n}.png"
        rows.append(rows[0].model_copy(update={"path": path, "question": floors, "answer": answer}))
    questions = write_questions(tmp_path / "questions.jsonl", rows)
    for row in rows:
        if row.path.startswith("data/swiss_dwellings/"):
            png = tmp_path / row.path.removesuffix(".pdf")
            png.parent.mkdir(parents=True, exist_ok=True)
            png.with_suffix(".png").write_bytes(b"png")
    assert run("split", "--questions", questions, "--out-dir", tmp_path / "split") == 0
    return tmp_path


def select(dataset: Path, out: Path, *extra: object) -> int:
    return run(
        "select-plans", "--questions", dataset / "questions.jsonl", "--split-dir",
        dataset / "split", "--gold", dataset / "gold", "--out-dir", out, *extra,
    )  # fmt: skip


def write_gold(dataset: Path, files: list[dict[str, Any]]) -> None:
    for row in files:
        gold = extraction(file=row["file"], split=row["split"])
        folder = dataset / "gold" / row["source"]
        folder.mkdir(parents=True, exist_ok=True)
        name = row["file"].replace("/", "__") + ".json"  # a swiss PDF and its PNG: two names
        (folder / name).write_text(gold.model_dump_json(by_alias=True), encoding="utf-8")


def test_select_plans_writes_both_parts_and_both_parts_score(
    dataset: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = dataset / "v2"
    assert select(dataset, out) == 1
    assert "have no gold JSON" in capsys.readouterr().err
    assert select(dataset, out, "--allow-missing-gold") == 0
    files = [json.loads(line) for line in (out / "part1_extraction/files.jsonl").open()]
    swiss = [row["file"] for row in files if row["source"] == "swiss_dwellings"]
    assert len(swiss) == 10 and sum(file.endswith(".png") for file in swiss) == 5
    assert {row["split"] for row in files} == {"dev", "eval"}
    assert all(row["truth"] is None and row["scale_case"] is None for row in files)
    assert len(read_json(out / "manifest.json")["missing_gold"]) == len(files)

    write_gold(dataset, files)
    assert select(dataset, out) == 0
    again = dataset / "v2-again"
    assert select(dataset, again) == 0
    for name in (
        "manifest.json",
        "part1_extraction/files.jsonl",
        "part2_answering/questions.jsonl",
    ):
        assert (out / name).read_bytes() == (again / name).read_bytes()  # deterministic
    manifest = read_json(out / "manifest.json")
    assert manifest["missing_gold"] == []
    assert manifest["scale_cases"]["nothing"]["picked"][0] > 0  # the fixture gold says no_scale
    copied = sorted((out / "part1_extraction/gold").rglob("*.json"))
    assert len(copied) == len(files)
    assert all(path.relative_to(out).as_posix() in manifest["files_sha256"] for path in copied)
    questions = [json.loads(line) for line in (out / "part2_answering/questions.jsonl").open()]
    picked = {row["file"] for row in files}
    assert questions and all(question["path"] in picked for question in questions)
    assert {"en", "fi"} <= {question["language"] for question in questions}

    # Part 1: the gold scored against itself
    assert run("score-extraction", out / "part1_extraction/gold", "--golden-dir", out,
               "--out", dataset / "p1.json") == 0  # fmt: skip
    assert read_json(dataset / "p1.json")["counts_overall"]["rate"] == 1.0

    # Part 2: answers to the part2 questions; recording needs --reads
    golden = out / "part2_answering/questions.jsonl"
    answers = dataset / "oracle.jsonl"
    assert run("baseline", "oracle", "--golden", golden, "--out", answers) == 0
    results = dataset / "runs.jsonl"
    score = ("score", answers, "--golden", golden, "--results", results, "--record",
             "--name", "oracle")  # fmt: skip
    assert run(*score) == 1
    assert "--reads" in capsys.readouterr().err
    assert run(*score, "--reads", "gold-extraction") == 0
    [row] = read_history(results)
    assert row.golden_version == "v2" and row.reads == "gold-extraction"
    assert row.overall.accuracy == 1.0


def test_select_plans_refuses_gold_from_the_other_split(
    dataset: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = dataset / "v2"
    assert select(dataset, out, "--allow-missing-gold") == 0
    files = [json.loads(line) for line in (out / "part1_extraction/files.jsonl").open()]
    flipped = [{**row, "split": "dev" if row["split"] == "eval" else "eval"} for row in files[:1]]
    write_gold(dataset, flipped)
    assert select(dataset, out, "--allow-missing-gold") == 1
    assert "differs from the sealed split" in capsys.readouterr().err

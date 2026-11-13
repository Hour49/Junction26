"""Golden v2 by plan: picking, the two-part layout, and scoring both parts, on made-up data."""

import functools
import hashlib
import json
from pathlib import Path
from typing import Any, Literal

import pytest

from stoa_eval import cli, plans
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


# every image has a scale value (Bogdan, 2026-11-13 23:33); estimated is still the "nothing" case
ESTIMATED = {"status": "estimated", "m_per_unit": 0.01, "uncertainty": 0.08, "source": "annotation"}


def write_gold(dataset: Path, files: list[dict[str, Any]]) -> None:
    for row in files:
        gold = extraction(file=row["file"], split=row["split"], scale=ESTIMATED)
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
    assert manifest["scale_cases"]["nothing"]["picked"][0] > 0  # the fixture gold is estimated
    copied = sorted((out / "part1_extraction/gold").rglob("*.json"))
    assert len(copied) == len(files)
    assert all(path.relative_to(out).as_posix() in manifest["files_sha256"] for path in copied)
    questions = [json.loads(line) for line in (out / "part2_answering/questions.jsonl").open()]
    picked = {row["file"] for row in files}
    assert questions and all(question["path"] in picked for question in questions)
    assert {"en", "fi"} <= {question["language"] for question in questions}

    # Part 1: the gold scored against itself
    assert run("score-extraction", out / "part1_extraction/gold", "--golden-dir", out,
               "--out", dataset / "p1.json", "--no-record") == 0  # fmt: skip
    assert read_json(dataset / "p1.json")["counts_overall"]["rate"] == 1.0
    empty = dataset / "empty"
    assert run("baseline-extraction", "empty", "--golden-dir", out, "--out", empty) == 0
    assert run("score-extraction", empty, "--golden-dir", out, "--out", dataset / "floor.json",
               "--no-record") == 0  # fmt: skip
    floor = read_json(dataset / "floor.json")
    assert floor["predicted"] == floor["files"] and floor["counts_overall"]["rate"] == 0.0

    # Part 2: answers to the part2 questions; recording needs --reads
    golden = out / "part2_answering/questions.jsonl"
    answers = dataset / "oracle.jsonl"
    assert run("baseline", "oracle", "--golden", golden, "--out", answers) == 0
    results = dataset / "results"
    score = ("score", answers, "--golden", golden, "--results", results, "--name", "oracle")
    assert run(*score) == 1
    assert "a recorded golden v2 Part 2 run needs --reads" in capsys.readouterr().err
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


def test_select_plans_adds_the_conflict_slice_and_merges_extras(
    dataset: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = dataset / "v2"
    assert select(dataset, out, "--allow-missing-gold") == 0
    files = [json.loads(line) for line in (out / "part1_extraction/files.jsonl").open()]
    write_gold(dataset, files)
    # a gold file no plan or scale pick takes (no questions, not a scale case), with conflicts
    lonely = "data/cubicasa5k/plan-99.png"
    gold = extraction(file=lonely, scale=ESTIMATED, notes=["scale dropped: no scale case here"])
    (dataset / "gold/cubicasa5k/plan-99.json").write_text(gold.model_dump_json(by_alias=True))
    picked = next(row for row in files if row["source"] == "cubicasa5k" and row["split"] == "dev")
    counted = {
        "id": "c1",
        "quantity": "element_count",
        "subject": {"kind": "class", "ref": "door"},
        "status": "conflict",
        "tolerance": 0,
        "values": [{"value": 3, "method": "detector"}, {"value": 4, "method": "annotation"}],
    }
    agreed = {
        **counted,
        "status": "agree",
        "values": [{"value": 1, "method": "plan_drawing"}, {"value": 1, "method": "ifc_model"}],
    }
    folder = dataset / "gold/_conflicts"
    folder.mkdir()
    (folder / "conflicts.jsonl").write_text(
        json.dumps({"file": lonely, "split": "dev", "conflicts": [counted]}) + "\n"
        + json.dumps({"file": picked["file"], "split": "dev", "conflicts": [agreed]}) + "\n"
    )  # fmt: skip
    questions = [json.loads(line) for line in (out / "part2_answering/questions.jsonl").open()]
    origin = next(q for q in questions if q["path"] == picked["file"])
    review7 = json.dumps(
        {
            **origin,
            "id": 1000001,
            "kind": "paraphrase",
            "origin_id": origin["id"],
            "expect": {"answer": origin["answer"]},
            "why": None,
            "style": "typo",
        }
    )
    unanswerable = json.dumps(
        {
            **origin,
            "id": 1000002,
            "answer": None,
            "unit": None,
            "type": "unanswerable",
            "template": "unanswerable/fact",
            "kind": "unanswerable",
            "origin_id": None,
            "expect": {"abstain": True},
            "why": "no year on a plan",
        }
    )
    estimate = json.dumps(
        {
            **origin,
            "id": 1000003,
            "question": "living room area in m2?",
            "answer": 16.7,
            "unit": "m2",
            "type": "area",
            "template": "estimate/scale",
            "kind": "estimate",
            "origin_id": None,
            "expect": {"answer": 16.7, "tolerance": 0.2, "estimate": True},
            "why": "room r8; gold scale estimated",
            "style": "scale",
        }
    )
    (out / "part2_answering/extras.jsonl").write_text(f"{unanswerable}\n{estimate}\n{review7}\n")
    review10 = {
        **origin,
        "path": lonely,
        "group": "cubicasa5k/plan-99",
        "question": "doors?",
        "answer": 4,
        "unit": "count",
        "type": "count",
        "id": 1001001,
        "kind": "conflict",
        "origin_id": None,
        "expect": {"answer": 4, "conflict_values": [3, 4]},
        "why": "c1",
    }
    (folder / "extras.jsonl").write_text(json.dumps(review10) + "\n")  # fmt: skip

    assert select(dataset, out) == 0
    rows = {
        row["file"]: row for row in map(json.loads, (out / "part1_extraction/files.jsonl").open())
    }
    assert rows[lonely]["stratum"] == "conflict" and rows[lonely]["split"] == "dev"
    manifest = read_json(out / "manifest.json")
    assert manifest["conflict_files"] == sorted([lonely, picked["file"]])
    assert "part2_answering/extras.jsonl" in manifest["files_sha256"]
    copy = read_json(out / "part1_extraction/gold/cubicasa5k/plan-99.json")
    assert copy["conflicts"] == [counted]
    merged = (out / "part2_answering/extras.jsonl").read_text().splitlines()
    assert merged == [review7, unanswerable, estimate, json.dumps(review10)]  # by id, verbatim
    first = (out / "part2_answering/extras.jsonl").read_bytes()
    assert select(dataset, out) == 0  # again: review-10's lines replace their earlier merge
    assert (out / "part2_answering/extras.jsonl").read_bytes() == first

    # both parts' oracles pass the new slices
    assert run("score-extraction", out / "part1_extraction/gold", "--golden-dir", out,
               "--out", dataset / "p1.json", "--no-record") == 0  # fmt: skip
    part1 = read_json(dataset / "p1.json")["conflicts"]
    assert part1["files"] == 2 and part1["overall"]["recall"] == 1.0
    assert part1["overall"]["false_alarms"] == 0 and part1["overall"]["agree"] == 1
    golden = out / "part2_answering/questions.jsonl"
    answers = dataset / "oracle.jsonl"
    assert run("baseline", "oracle", "--golden", golden, "--out", answers) == 0
    results = dataset / "results"
    capsys.readouterr()
    assert run("score", answers, "--golden", golden, "--results", results, "--name", "oracle",
               "--reads", "gold-extraction") == 0  # fmt: skip
    printed = capsys.readouterr().out
    assert "unanswerable     1/1 100.0% abstained" in printed
    assert "estimate         1/1 100.0% pass" in printed
    [row] = read_history(results)
    assert row.overall.accuracy == 1.0 and row.extras is not None
    assert row.extras.paraphrase.rate == 1.0 and row.extras.conflict_pass.rate == 1.0
    assert row.extras.estimate_pass is not None and row.extras.estimate_pass.rate == 1.0
    assert row.answer_v1_1 is not None and row.answer_v1_1.abstained == 0


def test_select_plans_refuses_bad_extras_and_writes_nothing(
    dataset: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = dataset / "v2"
    assert select(dataset, out, "--allow-missing-gold") == 0
    files = [json.loads(line) for line in (out / "part1_extraction/files.jsonl").open()]
    write_gold(dataset, files)
    questions = [json.loads(line) for line in (out / "part2_answering/questions.jsonl").open()]
    origin = next(q for q in questions if q["split"] == "dev")
    line = {**origin, "id": 1000001, "kind": "paraphrase", "origin_id": origin["id"],
            "expect": {"answer": origin["answer"]}, "why": None}  # fmt: skip
    extras = out / "part2_answering/extras.jsonl"
    for bad, message in (
        ({**line, "path": "data/cubicasa5k/plan-77.png"}, "is not a dev file of v2"),
        ({**line, "origin_id": 99_999}, "is not a v2 question"),
        ({**line, "id": 1001005}, "merged by an earlier run"),
    ):
        extras.write_text(json.dumps(bad) + "\n")
        before = (out / "manifest.json").read_bytes()
        if message == "merged by an earlier run":  # review-10's range in review-7's file: dropped
            assert select(dataset, out) == 0
            assert extras.read_text() == ""
            continue
        assert select(dataset, out) == 1
        assert message in capsys.readouterr().err
        assert (out / "manifest.json").read_bytes() == before
    folder = dataset / "gold/_conflicts"
    folder.mkdir()
    (folder / "extras.jsonl").write_text(json.dumps({**line, "id": 1000009}) + "\n")
    extras.write_text("")
    assert select(dataset, out) == 1
    assert "outside range(1001001, 1002000)" in capsys.readouterr().err


def test_a_conflict_only_file_changes_neither_headline(
    dataset: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Orchestrator, 2026-11-13 23:29: a file in v2 only for the conflict slice is scored only
    there. It has questions and is a scale case, yet Part 2 and the Part 1 headline stay put."""
    monkeypatch.setattr(plans, "QUOTAS", {**plans.QUOTAS, "cubicasa5k": (2, 1)})
    monkeypatch.setattr(cli, "pick_scale_cases", lambda *_: ({}, {}))  # no scale picks at all
    out = dataset / "v2"
    assert select(dataset, out, "--allow-missing-gold") == 0
    files = [json.loads(line) for line in (out / "part1_extraction/files.jsonl").open()]
    write_gold(dataset, files)
    dev = [json.loads(line) for line in (dataset / "split/dev.jsonl").open()]
    lonely = next(
        row["path"]
        for row in dev
        if row["path"].startswith("data/cubicasa5k/")
        and row["path"] not in {f["file"] for f in files}
    )
    gold = extraction(  # estimated: a scale case; a stair: a class no headline gold file lists
        file=lonely,
        scale=ESTIMATED,
        elements=[{"id": "s1", "class": "stair", "page": 1, "box": [0.1, 0.1, 0.2, 0.2]}],
    )
    (dataset / "gold/cubicasa5k/lonely.json").write_text(gold.model_dump_json(by_alias=True))

    def build(name: str) -> tuple[bytes, dict[str, Any]]:
        assert select(dataset, out) == 0
        empty = dataset / f"empty-{name}"
        assert run("baseline-extraction", "empty", "--golden-dir", out, "--out", empty) == 0
        assert run("score-extraction", empty, "--golden-dir", out, "--no-record",
                   "--out", dataset / f"{name}.json") == 0  # fmt: skip
        part2 = (out / "part2_answering/questions.jsonl").read_bytes()
        return part2, read_json(dataset / f"{name}.json")

    before_questions, before = build("before")
    folder = dataset / "gold/_conflicts"
    folder.mkdir()
    entry = {
        "id": "c1",
        "quantity": "element_count",
        "subject": {"kind": "class", "ref": "stair"},
        "status": "conflict",
        "tolerance": 0,
        "values": [{"value": 1, "method": "detector"}, {"value": 2, "method": "annotation"}],
    }
    (folder / "conflicts.jsonl").write_text(
        json.dumps({"file": lonely, "split": "dev", "conflicts": [entry]}) + "\n"
    )
    asked = next(row for row in dev if row["path"] == lonely)  # not a v2 question any more
    line = {
        **asked,
        "id": 1001001,
        "kind": "conflict",
        "origin_id": asked["id"],
        "why": "c1",
        "source": "cubicasa5k",
        "language": "en",
        "template": "t",
        "group": "g",
        "split": "dev",
        "expect": {
            "answer": asked["answer"],
            "conflict_values": [asked["answer"], asked["answer"] + 1],
        },
    }
    (folder / "extras.jsonl").write_text(json.dumps(line) + "\n")  # fmt: skip
    after_questions, after = build("after")

    rows = {
        row["file"]: row for row in map(json.loads, (out / "part1_extraction/files.jsonl").open())
    }
    assert rows[lonely]["stratum"] == "conflict" and rows[lonely]["scale_case"] is None
    assert after_questions == before_questions  # Part 2 headline: the same questions
    headline = ["files", "predicted", "elements", "elements_by_source", "elements_overall",
                "centre", "not_scored", "rooms", "plans", "counts", "counts_by_source",
                "counts_overall", "scale", "scale_overall", "per_file"]  # fmt: skip
    assert {key: after[key] for key in headline} == {key: before[key] for key in headline}
    assert (before["conflicts"], before["slice_only_files"]) == (None, 0)
    assert after["conflicts"]["files"] == 1 and after["conflicts"]["overall"]["conflicts"] == 1
    assert after["slice_only_files"] == 1
    extras = (out / "part2_answering/extras.jsonl").read_text().splitlines()
    assert [json.loads(text)["id"] for text in extras] == [1001001]


def test_select_plans_stops_on_unscaled_gold(
    dataset: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Golden v2 gold has a scale value on every image (Bogdan, 2026-11-13 23:33)."""
    out = dataset / "v2"
    assert select(dataset, out, "--allow-missing-gold") == 0
    files = [json.loads(line) for line in (out / "part1_extraction/files.jsonl").open()]
    write_gold(dataset, files)
    first = files[0]
    name = first["file"].replace("/", "__") + ".json"
    unscaled = extraction(file=first["file"], split=first["split"])  # no_scale: no value
    (dataset / "gold" / first["source"] / name).write_text(unscaled.model_dump_json(by_alias=True))
    capsys.readouterr()
    assert select(dataset, out) == 1
    assert "1 picked gold files lack a scale value" in capsys.readouterr().err
    assert select(dataset, out, "--allow-unscaled") == 0
    assert read_json(out / "manifest.json")["unscaled"] == [first["file"]]


NOT_TO_SCALE = {
    "status": "not_to_scale",
    "m_per_unit": 0.01,
    "uncertainty": 0.2,
    "source": "door widths",
    "evidence": ["not_to_scale_note"],
}


def test_keep_freezes_the_file_set_when_the_gold_changes(
    dataset: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Orchestrator, 2026-11-13 23:48: a rebuilt v2 keeps its files, so every recorded run compares
    against one set. A gold change (a not-to-scale sheet gets an estimated scale, like every
    CubiCasa image did; another sheet becomes not-to-scale) drops one file from a fresh pick and
    adds another; --keep holds the set, with scale cases recomputed and Part 2 unchanged."""
    monkeypatch.setattr(plans, "QUOTAS", {**plans.QUOTAS, "cubicasa5k": (2, 1)})
    monkeypatch.setattr(cli, "PlansParams", functools.partial(PlansParams, scale_quota=(1, 0)))
    out = dataset / "v2"
    assert select(dataset, out, "--allow-missing-gold") == 0
    files = [json.loads(line) for line in (out / "part1_extraction/files.jsonl").open()]
    write_gold(dataset, files)
    dev = [json.loads(line) for line in (dataset / "split/dev.jsonl").open()]
    sheet, other = sorted(
        {
            row["path"]
            for row in dev
            if row["path"].startswith("data/cubicasa5k/")
            and row["path"] not in {f["file"] for f in files}
        }
    )[:2]

    def gold_for(file: str, scale: dict[str, Any]) -> None:
        gold = extraction(file=file, scale=scale)
        name = file.replace("/", "__") + ".json"
        (dataset / "gold/cubicasa5k" / name).write_text(gold.model_dump_json(by_alias=True))

    gold_for(sheet, NOT_TO_SCALE)
    assert select(dataset, out) == 0
    listed = (out / "part1_extraction/files.jsonl").read_bytes()
    questions = (out / "part2_answering/questions.jsonl").read_bytes()
    before = {row["file"]: row for row in map(json.loads, listed.splitlines())}
    assert before[sheet]["stratum"] == "scale" and before[sheet]["scale_case"] == "not_to_scale"
    assert sheet.encode() in questions

    gold_for(sheet, ESTIMATED)  # plan picks already fill the "nothing" case
    gold_for(other, NOT_TO_SCALE)
    fresh = dataset / "v2-fresh"
    assert select(dataset, fresh) == 0
    picked = (fresh / "part1_extraction/files.jsonl").read_text()
    assert sheet not in picked and other in picked

    assert select(dataset, out, "--keep", out / "manifest.json") == 0
    after = [json.loads(line) for line in (out / "part1_extraction/files.jsonl").open()]
    assert [row["file"] for row in after] == list(before)
    kept = {row["file"]: row for row in after}
    assert kept[sheet]["stratum"] == "scale" and kept[sheet]["scale_case"] == "nothing"
    assert (out / "part2_answering/questions.jsonl").read_bytes() == questions
    manifest = read_json(out / "manifest.json")
    assert manifest["kept"] == hashlib.sha256(listed).hexdigest()
    assert manifest["scale_cases"]["nothing"]["picked"][0] == sum(
        row["scale_case"] == "nothing" and row["split"] == "dev" for row in after
    )
    assert manifest["scale_cases"]["not_to_scale"] == {  # the new not-to-scale sheet: not kept
        "wanted": [1, 0], "picked": [0, 0], "available": [1, 0]
    }  # fmt: skip
    assert manifest["by_source"] == read_json(fresh / "manifest.json")["by_source"]
    again = (out / "part1_extraction/files.jsonl").read_bytes()
    assert select(dataset, out, "--keep", out / "manifest.json") == 0  # a kept set keeps itself
    assert (out / "part1_extraction/files.jsonl").read_bytes() == again

    (out / "part1_extraction/files.jsonl").write_bytes(again[: again.rindex(b"\n", 0, -1) + 1])
    capsys.readouterr()
    assert select(dataset, out, "--keep", out / "manifest.json") == 1
    assert "is not the files list its manifest describes" in capsys.readouterr().err

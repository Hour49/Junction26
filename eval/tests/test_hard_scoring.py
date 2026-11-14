"""The hard slice (r8 section BA): hard_set_v1 labels, printed scale ratios, the scores, a pipeline
run read as predictions, and the `hard` command's record (aggregates only) and public gold."""

import argparse
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from stoa_eval import backend
from stoa_eval.cli import main, run_hard_questions
from stoa_eval.hard_scoring import (
    FAMILIES,
    QUESTIONS,
    HardFile,
    HardPred,
    load_labels,
    merge_preds,
    preds_from_run,
    public_gold,
    questions_for,
    ratio_of,
    score,
)

SHA = "0" * 64


def label(file: str = "a.png", **changes: object) -> dict[str, object]:
    body: dict[str, object] = {
        "file": file, "sha256": SHA, "source_url": "https://example.org/a", "licence": "PD-USGov",
        "attribution": "US Army Corps of Engineers", "gold_commit_ok": True,
        "sheet_kind": "architectural_floor_plan", "floor_plan_on_sheet": True,
        "takeoff_possible": True, "advanced": True, "why": "a big school plan",
        "printed_scale": {"text": "1:200", "ratio": 200, "how": "both"},
        "counts": {"door": {"lo": 10, "hi": 12}, "toilet": {"lo": 3, "hi": 3},
                   "window": "cannot_tell", "plan": {"lo": 1, "hi": 1}},
        "checked_by": "test", "minutes": 1,
    }  # fmt: skip
    body.update(changes)
    return body


def write_labels(path: Path, *files: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema": "hard_set_v1", "files": list(files)}))
    return path


NON_PLAN = {
    "sheet_kind": "mep_plan", "floor_plan_on_sheet": False, "takeoff_possible": False,
    "advanced": False, "counts": None,
}  # fmt: skip


def test_labels_load_and_refuse_what_the_schema_rules_out(tmp_path: Path) -> None:
    good = write_labels(tmp_path / "one" / "labels.json", label())
    (loaded,) = load_labels([good])
    assert loaded.counts is not None and loaded.counts["window"] == "cannot_tell"
    bad = [
        {"sheet_kind": "floor_plan"},  # not the contract's word
        {"counts": {"door": {"lo": 5, "hi": 4}}},  # lo > hi
        {**NON_PLAN, "counts": {"door": {"lo": 1, "hi": 1}}},  # counts on a non-plan
        {**NON_PLAN, "advanced": True},  # advanced needs a floor plan
        {"licence": "CC-BY-NC-4.0"},  # never NC/ND
        {"licence": "other:unclear", "gold_commit_ok": True},  # gold only for a listed licence
        {"counts": {"doors": {"lo": 1, "hi": 1}}},  # not an eval family
        {"file": "a.pdf", "scale_check": {"p1": [0, 0], "p2": [10, 0], "metres": 1, "from": "bar"}},
        {"scale_check": {"p1": [5, 5], "p2": [5, 5], "metres": 1, "from": "bar"}},  # one point
    ]
    for changes in bad:
        with pytest.raises(ValidationError):
            HardFile.model_validate(label(**changes))
    again = write_labels(tmp_path / "two" / "labels.json", label())
    with pytest.raises(ValueError, match="labelled in"):
        load_labels([good, again])


def test_ratio_of_reads_metric_and_imperial_scales() -> None:
    assert ratio_of("1:200") == 200
    assert ratio_of("SCALE 1 : 50 @ A1") == 50
    assert ratio_of('1/4" = 1\'-0"') == 48
    assert ratio_of("3/16\u2033 = 1\u2019-0\u2033") == 64  # typographic marks
    assert ratio_of('1 1/2" = 1\'-0"') == 8
    assert ratio_of("1\" = 40'") == 480
    assert ratio_of("1 inch = 20 feet") == 240
    for none in ("NTS", "Not to scale", "scale bar only"):
        assert ratio_of(none) is None


def test_the_scores_follow_the_slice_rules() -> None:
    files = [
        HardFile.model_validate(
            label(scale_check={"p1": [0, 0], "p2": [100, 0], "metres": 5.0, "from": "bar"})
        ),
        HardFile.model_validate(label("b.png", **{**NON_PLAN, "sheet_kind": "structural_plan"})),
        HardFile.model_validate(
            label("c.png", counts={"sink": {"lo": 2, "hi": 4}, "door": {"lo": 1, "hi": 1}})
        ),
        HardFile.model_validate(label("d.png", **NON_PLAN, printed_scale=None)),
    ]
    preds = [
        HardPred(
            file="a.png", sheet_kind="architectural_floor_plan", floor_plan_on_sheet=True,
            printed_scale_ratio=200, m_per_px=0.055,
            counts={"door": 13, "toilet": 3, "window": 40, "plan": None},
        ),
        HardPred(file="b.png", sheet_kind="architectural_floor_plan", floor_plan_on_sheet=True,
                 counts={"door": 2, "window": 19, "plan": None}),
        HardPred(file="c.png", floor_plan_on_sheet=False, counts={"sink": 3}),
        HardPred(file="d.png", sheet_kind="mep_plan", floor_plan_on_sheet=False),
    ]  # fmt: skip
    report = score(files, preds)
    assert (report.kind.labelled, report.kind.said, report.kind.right) == (4, 3, 2)
    plan = report.plan
    assert (plan.tp, plan.fn, plan.fp, plan.tn, plan.not_said) == (1, 1, 1, 1, 0)
    assert plan.recall == 0.5 and plan.precision == 0.5
    door, toilet, window, sink = (report.families[f] for f in ("door", "toilet", "window", "sink"))
    assert (door.asked, door.hit) == (1, 0)  # 13 is outside 10-12
    assert (toilet.asked, toilet.hit) == (1, 1)
    assert (window.labelled, window.cannot_tell, window.asked) == (1, 1, 0)  # never scored
    assert (sink.asked, sink.hit) == (1, 1)
    plans = report.families["plan"]
    assert (plans.asked, plans.refused, plans.hit) == (1, 1, 0)  # a refusal is a miss
    # c.png's door is labelled but the arm did not answer it: not scored
    assert report.families["door"].labelled == 2 and report.families["door"].asked == 1
    assert sorted(report.non_plan_counts) == [("b.png", "door", 2), ("b.png", "window", 19)]
    assert (report.pooled.asked, report.pooled.hit) == (4, 2)
    s = report.scale
    assert (s.ratio_labelled, s.ratio_read, s.ratio_exact) == (3, 1, 1)
    assert s.px_labelled == 1 and s.px_errors == [pytest.approx(0.1)]  # truth 0.05 m/px


def test_a_pipeline_run_reads_as_predictions_and_a_classifier_lays_over_it() -> None:
    files = [HardFile.model_validate(label()), HardFile.model_validate(label("b.jpg", **NON_PLAN))]
    questions = questions_for(files, "data/inbox/hard")
    assert len(questions) == 2 * len(FAMILIES)
    assert questions[0] == {"id": 1, "path": "data/inbox/hard/a.png", "question": QUESTIONS["plan"]}
    by_id = {q["id"]: q for q in questions}
    door_a = next(i for i, q in by_id.items() if q["question"] == QUESTIONS["door"])
    plan_b = next(
        i
        for i, q in by_id.items()
        if str(q["path"]).endswith("b.jpg") and q["question"] == QUESTIONS["plan"]
    )
    answers = [
        {"id": door_a, "answer": 11},
        {"id": plan_b, "answer": None},
        {"id": 3, "answer": 2.5},  # not a whole count: a refusal
    ]
    ingest = {
        "sheets": [{"file": "data/inbox/hard/a.png"}],
        "set_aside": [{"path": "data/inbox/hard/b.jpg", "reason": "x"}],
    }
    preds = {p.file: p for p in preds_from_run(questions, answers, ingest, {"a.png": 0.02})}
    assert (
        preds["a.png"].floor_plan_on_sheet is True and preds["b.jpg"].floor_plan_on_sheet is False
    )
    assert preds["a.png"].counts == {"door": 11, "window": None}
    assert preds["b.jpg"].counts == {"plan": None}
    assert preds["a.png"].m_per_px == 0.02 and preds["b.jpg"].m_per_px is None
    kinds = [HardPred(file="b.jpg", sheet_kind="mep_plan", counts={"door": 0})]
    merged = {p.file: p for p in merge_preds(list(preds.values()), kinds)}
    assert merged["b.jpg"].sheet_kind == "mep_plan"
    assert merged["b.jpg"].floor_plan_on_sheet is False  # kept: the classifier line had null
    assert merged["b.jpg"].counts == {"plan": None, "door": 0}


def test_the_hard_command_records_aggregates_only_and_writes_public_gold(tmp_path: Path) -> None:
    root = tmp_path / "root"
    labels = write_labels(
        root / "data" / "inbox" / "hard" / "labels.json",
        label("secret-name-a.png"),
        label("secret-name-b.png", licence="other:all rights reserved", gold_commit_ok=False),
    )
    questions = tmp_path / "q.jsonl"
    run_hard_questions(argparse.Namespace(labels=[labels], root=root, out=questions))
    rows = [json.loads(line) for line in questions.read_text().splitlines()]
    assert rows[0]["path"] == "data/inbox/hard/secret-name-a.png" and len(rows) == 2 * len(FAMILIES)
    run = tmp_path / "run"
    (run / "extraction").mkdir(parents=True)
    door = next(r["id"] for r in rows if r["question"] == QUESTIONS["door"])
    (run / "answers.jsonl").write_text(json.dumps({"id": door, "answer": 11}) + "\n")
    (run / "ingest.json").write_text(json.dumps({"sheets": [], "set_aside": []}))
    scale = {"status": "estimated", "m_per_unit": 0.01}
    (run / "extraction" / "a.json").write_text(
        json.dumps({"file": rows[0]["path"], "scale": scale})
    )
    pred = tmp_path / "kinds.jsonl"
    pred.write_text(json.dumps({"file": "secret-name-a.png", "sheet_kind": "mep_plan"}) + "\n")
    results, public = tmp_path / "results", tmp_path / "gold.json"
    argv = [
        "hard", str(labels), "--run", str(run), "--questions", str(questions), "--pred", str(pred),
        "--name", "test arm", "--results", str(results), "--public", str(public),
    ]  # fmt: skip
    assert main(argv) == 0  # through the real parser: --run must not shadow the command
    (record_path,) = results.iterdir()
    text = record_path.read_text()
    assert "secret-name" not in text  # a public record: no file names
    record = json.loads(text)
    assert record["name"] == "test arm" and len(record["labels_sha256"]) == 1
    report = record["report"]
    assert report["families"]["door"]["hit"] == 1 and report["kind"]["right"] == 0
    gold = json.loads(public.read_text())
    assert [f["file"] for f in gold["files"]] == ["secret-name-a.png"]  # licence allows only a
    (first,) = public_gold(load_labels([labels]))
    assert first["counts"] == label()["counts"]  # as labelled


@pytest.mark.skipif(not (backend.BACKEND / ".venv").is_dir(), reason="backend/ has no environment")
def test_the_backend_parser_reads_each_question_as_its_family(tmp_path: Path) -> None:
    questions = tmp_path / "q.jsonl"
    rows = [
        {"id": n + 1, "path": "x.png", "question": QUESTIONS[f]} for n, f in enumerate(FAMILIES)
    ]
    questions.write_text("".join(json.dumps(row) + "\n" for row in rows))
    out = tmp_path / "families.json"
    backend.run("families", "--questions", str(questions), "--out", str(out))
    found = json.loads(out.read_text())
    assert [found[str(n + 1)] for n in range(len(FAMILIES))] == list(FAMILIES)

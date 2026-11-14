"""Part 1 scoring on made-up drawings and boxes."""

import json
from pathlib import Path
from typing import Any

import pytest

from stoa_eval.cli import main
from stoa_eval.extraction import Extraction
from stoa_eval.extraction_scoring import format_extraction_table, iou, match, score_extraction
from stoa_eval.history import read_extraction_history, read_history
from stoa_eval.scale_scoring import case_of

PLAN = "data/cubicasa5k/plan-1.png"


def element(
    i: str, box: list[float], cls: str = "door", page: int = 1, **extra: Any
) -> dict[str, Any]:
    return {"id": i, "class": cls, "page": page, "box": box, **extra}


def extraction(
    file: str = PLAN,
    elements: list[dict[str, Any]] | None = None,
    rooms: list[dict[str, Any]] | None = None,
    **extra: Any,
) -> Extraction:
    data: dict[str, Any] = {
        "schema": "extraction_v1",
        "file": file,
        "split": "dev",
        "truth": "elements",
        "pages": [
            {"page": 1, "width": 1000, "height": 800, "unit": "px"},
            {"page": 2, "width": 1000, "height": 800, "unit": "px"},
        ],
        "plans": [{"id": "p1", "page": 1, "box": [0.0, 0.0, 1.0, 1.0]}],
        "elements": elements or [],
        "rooms": rooms or [],
        "scale": {"status": "no_scale"},
        **extra,
    }
    return Extraction.model_validate(data)


def test_iou_of_boxes() -> None:
    assert iou((0.0, 0.0, 1.0, 1.0), (0.0, 0.0, 0.5, 1.0)) == 0.5
    assert iou((0.1, 0.1, 0.1, 0.4), (0.1, 0.1, 0.1, 0.4)) == 1.0  # a flat box matches itself
    assert iou((0.0, 0.0, 0.1, 0.1), (0.5, 0.5, 0.6, 0.6)) == 0.0


def test_matching_is_one_to_one_and_greedy_by_highest_iou() -> None:
    gold = extraction(elements=[element("g1", [0.0, 0.0, 0.2, 0.2])]).elements
    pred = extraction(
        elements=[element("p1", [0.0, 0.0, 0.2, 0.19]), element("p2", [0.0, 0.0, 0.2, 0.2])]
    ).elements
    assert match(gold, pred) == [(0, 1)]  # the exact box wins, the other is a false positive


def test_iou_exactly_at_the_threshold_matches() -> None:
    gold = extraction(elements=[element("g1", [0.2, 0.2, 0.6, 0.6])]).elements
    half = extraction(elements=[element("p1", [0.2, 0.2, 0.4, 0.6])]).elements  # IoU 0.5
    less = extraction(elements=[element("p1", [0.2, 0.2, 0.39, 0.6])]).elements
    assert match(gold, half) == [(0, 0)]
    assert match(gold, less) == []


def test_the_same_box_on_another_page_does_not_match() -> None:
    gold = extraction(elements=[element("g1", [0.2, 0.2, 0.4, 0.4])]).elements
    pred = extraction(elements=[element("p1", [0.2, 0.2, 0.4, 0.4], page=2)]).elements
    assert match(gold, pred) == []


def test_polygons_decide_when_both_have_one() -> None:
    """Two diagonal walls: their boxes are the same, their polygons barely touch."""
    up = [[0.0, 0.0], [0.05, 0.0], [1.0, 0.95], [1.0, 1.0], [0.95, 1.0], [0.0, 0.05]]
    down = [[1.0, 0.0], [1.0, 0.05], [0.05, 1.0], [0.0, 1.0], [0.0, 0.95], [0.95, 0.0]]
    box = [0.0, 0.0, 1.0, 1.0]
    gold = extraction(elements=[element("g1", box, "wall", polygon=up)]).elements
    crossing = extraction(elements=[element("p1", box, "wall", polygon=down)]).elements
    boxed = extraction(elements=[element("p1", box, "wall")]).elements
    assert match(gold, crossing) == []
    assert match(gold, boxed) == [(0, 0)]  # no polygon on one side: box IoU


def test_score_per_class_rooms_plans_counts_and_centres() -> None:
    gold = extraction(
        elements=[
            element("d1", [0.1, 0.1, 0.2, 0.2]),
            element("d2", [0.5, 0.5, 0.6, 0.6]),
            element("w1", [0.0, 0.3, 0.1, 0.4], "window"),
        ],
        rooms=[
            {"id": "r1", "type": "bedroom", "page": 1, "box": [0.1, 0.1, 0.5, 0.5],
             "area_m2": 10.0},
            {"id": "r2", "type": "kitchen", "page": 1, "box": [0.5, 0.5, 0.9, 0.9],
             "area_m2": 8.0},
        ],
    )  # fmt: skip
    pred = extraction(
        elements=[
            element("a", [0.1, 0.1, 0.2, 0.2]),
            element("b", [0.52, 0.52, 0.66, 0.66]),  # IoU < 0.5, but its centre is in d2
            element("c", [0.0, 0.3, 0.1, 0.4], "window"),
            element("s", [0.8, 0.8, 0.9, 0.9], "stair"),  # the gold has no stairs
        ],
        rooms=[
            {"id": "x", "type": "bedroom", "page": 1, "box": [0.1, 0.1, 0.5, 0.5],
             "area_m2": 10.19},
            {"id": "y", "type": "living", "page": 1, "box": [0.5, 0.5, 0.9, 0.9],
             "area_m2": 8.5},
        ],
    )  # fmt: skip
    result = score_extraction([gold], {PLAN: pred})
    doors = result.elements["cubicasa5k door"]
    assert (doors.tp, doors.fp, doors.fn) == (1, 1, 1)
    assert doors.f1 == 0.5
    assert result.elements["cubicasa5k window"].f1 == 1.0
    assert "cubicasa5k stair" not in result.elements
    assert result.not_scored == {"cubicasa5k stair": 1}
    centre = result.centre["cubicasa5k door"]
    assert (centre.pred_hit, centre.gold_hit) == (2, 2)
    rooms = result.rooms["cubicasa5k"]
    assert rooms.boxes.f1 == 1.0
    assert (rooms.type.correct, rooms.type.n) == (1, 2)
    assert (rooms.area.correct, rooms.area.n) == (1, 2)  # 10.19 is within 2% of 10, 8.5 is not
    assert result.plans["cubicasa5k"].rate == 1.0
    # counts: plan, door, window right; room:bedroom right; room:kitchen 0 vs 1 wrong
    assert result.counts["cubicasa5k door"].rate == 1.0
    assert result.counts["cubicasa5k room:kitchen"].rate == 0.0
    assert result.per_file[0].counts_wrong == {"room:kitchen": (1, 0)}
    by_source = result.elements_by_source["cubicasa5k"]
    assert (by_source.tp, by_source.fp, by_source.fn) == (2, 1, 1)
    counts = result.counts_by_source["cubicasa5k"]
    assert (counts.n, counts.correct) == (5, 4)  # plan, door, window, bedroom right; kitchen wrong


def test_a_missing_prediction_file_misses_everything() -> None:
    gold = extraction(elements=[element("d1", [0.1, 0.1, 0.2, 0.2])])
    result = score_extraction([gold], {})
    assert result.predicted == 0
    doors = result.elements["cubicasa5k door"]
    assert (doors.tp, doors.fp, doors.fn) == (0, 0, 1)
    assert result.counts_overall.correct == 0 and result.counts_overall.n == 2  # plan, door
    assert result.plans["cubicasa5k"].rate == 0.0


def test_read_changes_no_score_and_marks_a_class_nobody_read() -> None:
    """golden-7f: `read` lists what an extraction looked for. The score is unchanged (a class not
    read still counts its misses); the table marks a class no prediction file of the source read."""
    door, window = (
        element("d1", [0.1, 0.1, 0.2, 0.2]),
        element("w1", [0.0, 0.3, 0.1, 0.4], "window"),
    )
    gold = extraction(elements=[door, window])
    plain = extraction(elements=[element("a", [0.1, 0.1, 0.2, 0.2])])
    told = extraction(elements=[element("a", [0.1, 0.1, 0.2, 0.2])], read=["door", "room"])
    without, with_read = (score_extraction([gold], {PLAN: pred}) for pred in (plain, told))
    assert with_read.model_dump(exclude={"not_read"}) == without.model_dump(exclude={"not_read"})
    windows = with_read.elements["cubicasa5k window"]
    assert (windows.tp, windows.fn) == (0, 1)  # not reading is a miss
    assert (without.not_read, with_read.not_read) == ([], ["cubicasa5k window"])
    marked = [row for row in format_extraction_table(with_read).splitlines() if "not read" in row]
    assert len(marked) == 1 and marked[0].startswith("cubicasa5k window")
    assert "not read" not in format_extraction_table(without)
    other = "data/cubicasa5k/plan-2.png"  # a file of the source that read everything clears it
    mixed = score_extraction([gold, extraction(file=other)], {PLAN: told, other: extraction(other)})
    assert mixed.not_read == []


def test_truth_counts_scores_only_the_gold_counts() -> None:
    gold = extraction(truth="counts", counts={"door": 2, "room:sauna": 1})
    pred = extraction(
        elements=[element("a", [0.1, 0.1, 0.2, 0.2]), element("b", [0.3, 0.3, 0.4, 0.4]),
                  element("c", [0.5, 0.5, 0.6, 0.6], "window")],
    )  # fmt: skip
    result = score_extraction([gold], {PLAN: pred})
    assert result.elements == {} and result.plans == {}
    assert set(result.counts) == {"cubicasa5k door", "cubicasa5k room:sauna"}
    assert result.counts["cubicasa5k door"].rate == 1.0
    assert result.counts["cubicasa5k room:sauna"].rate == 0.0


def test_multiplicity_counts_only_when_asked() -> None:
    gold = extraction(elements=[element("d1", [0.1, 0.1, 0.2, 0.2], attrs={"multiplicity": 2})])
    pred = extraction(elements=[element("a", [0.1, 0.1, 0.2, 0.2])])
    assert score_extraction([gold], {PLAN: pred}).counts["cubicasa5k door"].rate == 1.0
    weighed = score_extraction([gold], {PLAN: pred}, multiplicity=True)
    assert weighed.counts["cubicasa5k door"].rate == 0.0
    assert weighed.elements["cubicasa5k door"].f1 == 1.0  # still one object when matching
    with pytest.raises(ValueError, match="multiplicity"):
        extraction(elements=[element("d1", [0.1, 0.1, 0.2, 0.2], attrs={"multiplicity": 0})])


SCALED = {"status": "scaled", "m_per_unit": 0.01, "evidence": ["printed_areas"], "source": "t"}
NTS = {"status": "not_to_scale", "evidence": ["not_to_scale_note"]}


def estimate(m_per_unit: float) -> dict[str, Any]:
    return {"status": "estimated", "m_per_unit": m_per_unit, "uncertainty": 0.1, "source": "doors"}


@pytest.mark.parametrize(
    ("gold_scale", "pred_scale", "pred_width", "outcome", "status_ok", "m_ok"),
    [
        (SCALED, None, 1000, "scaled->missing", False, False),
        (SCALED, {**SCALED, "m_per_unit": 0.0102}, 1000, "scaled->scaled", True, True),
        (SCALED, {**SCALED, "m_per_unit": 0.0103}, 1000, "scaled->scaled", True, False),
        # rendered at half the resolution: twice the metres per pixel is the same scale
        (SCALED, {**SCALED, "m_per_unit": 0.02}, 500, "scaled->scaled", True, True),
        (SCALED, estimate(0.01), 1000, "scaled->estimated", False, False),
        ({"status": "no_scale"}, SCALED, 1000, "no_scale->scaled", False, None),
        ({"status": "no_scale"}, estimate(0.01), 1000, "no_scale->estimated", True, None),
        ({"status": "no_scale"}, {"status": "no_scale"}, 1000, "no_scale->no_scale", True, None),
        (NTS, NTS, 1000, "not_to_scale->not_to_scale", True, None),
        (NTS, {"status": "no_scale"}, 1000, "not_to_scale->no_scale", False, None),
    ],
)  # fmt: skip
def test_scale_cases(
    gold_scale: dict[str, Any],
    pred_scale: dict[str, Any] | None,
    pred_width: int,
    outcome: str,
    status_ok: bool,
    m_ok: bool | None,
) -> None:
    gold = extraction(scale=gold_scale)
    pages = [{"page": 1, "width": pred_width, "height": 800, "unit": "px"}]
    preds = {} if pred_scale is None else {PLAN: extraction(scale=pred_scale, pages=pages)}
    result = score_extraction([gold], preds)
    assert result.per_file[0].scale == outcome
    gold_status, column = outcome.split("->")
    assert result.scale_overall.confusion[gold_status][column] == 1
    [stats] = result.scale["cubicasa5k"].by_case.values()
    assert stats.status.correct == status_ok
    assert stats.m_per_unit.n == (m_ok is not None)
    if m_ok is not None:
        assert stats.m_per_unit.correct == m_ok
        assert result.scale_overall.by_evidence["printed_areas"].correct == m_ok


def test_scale_case_kinds_estimates_and_exclusions() -> None:
    def gold(file: str, scale: dict[str, Any], notes: list[str] | None = None) -> Extraction:
        return extraction(file=file, scale=scale, notes=notes or [])

    text = {**SCALED, "evidence": ["scale_text", "printed_areas"]}
    dims = {**SCALED, "evidence": ["dimension_lines"]}
    nothing = {"status": "no_scale", "reference_m_per_unit": 0.01}
    golds = [
        gold("data/cubicasa5k/a.png", text),
        gold("data/cubicasa5k/b.png", SCALED),
        gold("data/cubicasa5k/c.png", dims),
        gold("data/cubicasa5k/d.png", nothing),
        gold("data/cubicasa5k/e.png", nothing),
        gold("data/cubicasa5k/f.png", nothing),
        gold("data/cubicasa5k/g.png", NTS),
        gold("data/cubicasa5k/h.png", {"status": "no_scale"}, ["scale not reviewed"]),
        gold("data/cubicasa5k/i.png", SCALED, ["scale dropped: two rooms disagree by 3%"]),
    ]
    preds = {
        "data/cubicasa5k/d.png": extraction(file="data/cubicasa5k/d.png", scale=estimate(0.0105)),
        "data/cubicasa5k/e.png": extraction(file="data/cubicasa5k/e.png", scale=estimate(0.0115)),
        "data/cubicasa5k/f.png": extraction(file="data/cubicasa5k/f.png", scale=estimate(0.013)),
    }
    score = score_extraction(golds, preds).scale_overall
    assert set(score.by_case) == {
        "scale_text_or_bar", "printed_areas", "dimension_lines", "nothing", "not_to_scale"
    }  # fmt: skip
    assert score.excluded == 2
    assert score.by_case["nothing"].status.correct == 3
    assert score.estimates.median_error == pytest.approx(0.15)
    assert score.estimates.within_10 == pytest.approx(1 / 3)
    assert score.estimates.within_20 == pytest.approx(2 / 3)
    assert case_of(gold(PLAN, estimate(0.01))) == "nothing"  # gold may be estimated (23:33)


def write(folder: Path, name: str, item: Extraction) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(item.model_dump_json(by_alias=True), encoding="utf-8")


def test_score_extraction_command_records_a_part1_row(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    gold = extraction(elements=[element("d1", [0.1, 0.1, 0.2, 0.2])])
    write(tmp_path / "gold/cubicasa5k", "plan-1.json", gold)
    (tmp_path / "gold/cubicasa5k/_report.json").write_text("{}", encoding="utf-8")  # skipped
    (tmp_path / "gold/_reports").mkdir()
    (tmp_path / "gold/_reports/rulecheck.json").write_text("{}", encoding="utf-8")  # skipped
    write(tmp_path / "pred", "plan-1.json", gold)
    results, runs = tmp_path / "results", tmp_path / "runs"
    old_row = (Path(__file__).parent / "data/old_run_row.json").read_text("utf-8")
    results.mkdir()
    (results / "20261113-204152-answering-oracle.json").write_text(old_row, encoding="utf-8")
    argv = ["score-extraction", str(tmp_path / "pred"), "--against", "dev",
            "--gold", str(tmp_path / "gold"), "--results", str(results),
            "--runs-dir", str(runs), "--name", "copy-of-gold"]  # fmt: skip
    assert main(argv) == 0
    assert "1 of 1 gold files have a prediction" in capsys.readouterr().out
    [kept] = list(results.glob("*-extraction-copy-of-gold.json"))
    score = json.loads((runs / kept.name).read_text("utf-8"))
    assert score["elements"]["cubicasa5k door"]["f1"] == 1.0
    [part1] = read_extraction_history(results)
    assert part1.part == "extraction" and part1.elements_f1 == 1.0
    assert part1.scale_status_by_source["cubicasa5k"].rate == 1.0  # no_scale -> no_scale
    [old] = read_history(results)
    assert old.part == "answering" and old.reads is None  # a row from before v2 still loads
    assert main(["history", "--part", "extraction", "--results", str(results)]) == 0
    printed = capsys.readouterr().out
    assert "copy-of-gold" in printed and "Part 2" not in printed
    assert main([*argv[:-2], "--against", "eval", "--name", "x"]) == 1
    assert "refused" in capsys.readouterr().err
    assert main([*argv[:-2], "--no-record", "--out", str(tmp_path / "s.json")]) == 0
    assert len(list(results.glob("*.json"))) == 2  # --no-record kept nothing
    assert main([*argv[:-2], "--no-record"]) == 0  # no --out: no file at all
    assert "not written" in capsys.readouterr().out
    assert [p.name for p in runs.iterdir()] == [kept.name]  # only the recorded run's score
    assert len(list(results.glob("*.json"))) == 2

"""Every image has a scale and every room an area (Bogdan, 2026-11-13 23:33: "We should have ON ALL
IMAGES THE SCALE TO GET THE AREA, BY APROXIMATING IT IN DIFFERENT WAYS IF NOT GOOD SCALE ETC."):
estimated gold scales and areas, and the strict golden v2 check, on made-up files."""

from pathlib import Path
from typing import Any

import pytest

from stoa_eval.cli import main
from stoa_eval.extraction_scoring import score_extraction
from stoa_eval.history import read_extraction_history
from tests.test_extraction_scoring import PLAN, extraction, write
from tests.test_plans import ESTIMATED
from tests.test_tables_conflicts import DOORS, schedule

SCALED = {"status": "scaled", "m_per_unit": 0.01, "evidence": ["printed_areas"], "source": "t"}
NTS = {"status": "not_to_scale", "evidence": ["not_to_scale_note"], "m_per_unit": 0.01,
       "uncertainty": 0.15, "source": "annotation"}  # fmt: skip


def estimate(m_per_unit: float, status: str = "estimated") -> dict[str, Any]:
    extra = {"evidence": ["not_to_scale_note"]} if status == "not_to_scale" else {}
    return {"status": status, "m_per_unit": m_per_unit, "uncertainty": 0.1, "source": "doors",
            **extra}  # fmt: skip


@pytest.mark.parametrize(
    ("gold_scale", "pred_scale", "outcome", "status_ok", "error"),
    [
        (ESTIMATED, estimate(0.0105), "estimated->estimated", True, 0.05),
        (ESTIMATED, {**SCALED, "m_per_unit": 0.01}, "estimated->scaled", False, None),
        (ESTIMATED, {"status": "no_scale"}, "estimated->no_scale", False, None),
        (ESTIMATED, None, "estimated->missing", False, None),
        (NTS, estimate(0.012, "not_to_scale"), "not_to_scale->not_to_scale", True, 0.2),
        (NTS, {"status": "not_to_scale", "evidence": ["not_to_scale_note"]},
         "not_to_scale->not_to_scale", True, None),
        ({"status": "no_scale", "reference_m_per_unit": 0.01}, estimate(0.011),
         "no_scale->estimated", True, 0.1),
        (SCALED, estimate(0.01), "scaled->estimated", False, None),  # no estimate on scaled gold
    ],
)  # fmt: skip
def test_estimated_gold_scales(
    gold_scale: dict[str, Any],
    pred_scale: dict[str, Any] | None,
    outcome: str,
    status_ok: bool,
    error: float | None,
) -> None:
    gold = extraction(scale=gold_scale)
    preds = {} if pred_scale is None else {PLAN: extraction(scale=pred_scale)}
    result = score_extraction([gold], preds)
    assert result.per_file[0].scale == outcome
    gold_status, column = outcome.split("->")
    assert result.scale_overall.confusion[gold_status][column] == 1
    [(case, stats)] = result.scale_overall.by_case.items()
    assert stats.status.correct == status_ok
    assert case == {"scaled": "printed_areas", "not_to_scale": "not_to_scale"}.get(
        gold_status, "nothing"
    )
    errors = result.scale_overall.estimates.errors
    assert errors == ([] if error is None else [pytest.approx(error)])


def room(id_: str, box: list[float], area: float, **extra: Any) -> dict[str, Any]:
    return {"id": id_, "type": "bedroom", "page": 1, "box": box, "area_m2": area, **extra}


ESTIMATED_AREA = {"area_status": "estimated", "area_source": "geometry_x_estimate",
                  "area_uncertainty": 0.1}  # fmt: skip


BOXES = [[0.0, 0.0, 0.1, 0.1], [0.2, 0.0, 0.3, 0.1], [0.4, 0.0, 0.5, 0.1],
         [0.6, 0.0, 0.7, 0.1], [0.8, 0.0, 0.9, 0.1]]  # fmt: skip


def test_estimated_room_areas_damaged_copy_scores_exactly(tmp_path: Path) -> None:
    gold = extraction(
        scale=ESTIMATED,
        rooms=[
            room("r1", BOXES[0], 12.2, area_status="exact", area_source="printed"),
            room("r2", BOXES[1], 8.0),  # unset: exact, as swiss and ifc gold
            room("r3", BOXES[2], 20.0, **ESTIMATED_AREA),
            room("r4", BOXES[3], 10.0, **ESTIMATED_AREA),
            room("r5", BOXES[4], 5.0, **ESTIMATED_AREA),
        ],
    )
    pred = extraction(
        scale=estimate(0.01),
        rooms=[
            room("a", BOXES[0], 12.4),  # within 2% of 12.2
            room("b", BOXES[1], 8.5),  # 6% off: wrong
            room("c", BOXES[2], 22.0),  # 10% off
            room("d", BOXES[3], 13.0),  # 30% off
            {"id": "e", "type": "bedroom", "page": 1, "box": BOXES[4]},  # no area
        ],
    )
    rooms = score_extraction([gold], {PLAN: pred}).rooms["cubicasa5k"]
    assert (rooms.area.correct, rooms.area.n) == (1, 2)  # only the exact gold areas
    assert rooms.area_estimated.errors == [pytest.approx(0.1), pytest.approx(0.3)]
    assert rooms.area_estimated.median_error == pytest.approx(0.2)
    assert rooms.area_estimated.within_10 == 0.5 and rooms.area_estimated.within_20 == 0.5
    assert rooms.area_estimated_missing == 1

    write(tmp_path / "gold/cubicasa5k", "plan-1.json", gold)
    write(tmp_path / "pred", "plan-1.json", pred)
    results = tmp_path / "results"
    assert main(["score-extraction", str(tmp_path / "pred"), "--against", "dev", "--gold",
                 str(tmp_path / "gold"), "--results", str(results), "--runs-dir",
                 str(tmp_path / "runs"), "--name", "damaged"]) == 0  # fmt: skip
    [record] = read_extraction_history(results)
    assert record.room_area_accuracy == 0.5  # the headline number, exact areas only
    summary = record.room_area_estimates["cubicasa5k"]
    assert (summary.rooms, summary.missing) == (3, 1)
    assert summary.median_error == pytest.approx(0.2) and summary.within_20 == 0.5


def test_strict_v2_names_every_shortfall(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    polygon = [[0.0, 0.0], [0.1, 0.0], [0.1, 0.1]]
    files = {
        "good": extraction(scale=ESTIMATED, rooms=[room("r1", BOXES[0], 3.0, polygon=polygon)]),
        "schedule": schedule([DOORS]),  # no plan to measure: exempt
        "unscaled": extraction(file="data/cubicasa5k/b.png"),
        "unreviewed": extraction(file="data/cubicasa5k/c.png", scale=ESTIMATED,
                                 notes=["scale not reviewed: no printed evidence"]),
        "bare": extraction(file="data/cubicasa5k/d.png", scale=ESTIMATED,
                           rooms=[{"id": "r1", "type": "hall", "page": 1, "box": BOXES[0],
                                   "polygon": polygon}]),
    }  # fmt: skip
    assert [name for name, item in files.items() if item.strict_v2_problems()] == [
        "unscaled", "unreviewed", "bare",
    ]  # fmt: skip
    for name, item in files.items():
        write(tmp_path, f"{name}.json", item)
    assert main(["validate-extraction", str(tmp_path)]) == 0  # all valid extraction_v1
    capsys.readouterr()
    assert main(["validate-extraction", "--strict-v2", str(tmp_path)]) == 1
    printed = capsys.readouterr().out
    assert "scale no_scale has no m_per_unit" in printed
    assert 'still says "scale not reviewed"' in printed
    assert "1 rooms with a polygon have no area_m2 (first r1)" in printed
    assert "2 of 5 files are valid golden v2 gold" in printed

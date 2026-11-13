"""Part 1 slices outside the headline: schedules (tables) and stage-8 conflicts, made up."""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from stoa_eval.cli import main
from stoa_eval.extraction import Extraction
from stoa_eval.extraction_scoring import score_extraction
from stoa_eval.history import read_extraction_history
from tests.test_extraction_scoring import PLAN, extraction, write

SHEET = "data/opening_design/Gym/Sheets/A-801 Schedules.pdf"


def table(
    id_: str,
    title: str | None,
    box: list[float],
    columns: list[str],
    rows: list[list[str | None]],
    **extra: Any,
) -> dict[str, Any]:
    return {"id": id_, "page": 1, "box": box, "title": title, "columns": columns,
            "rows": [{"cells": cells} for cells in rows], **extra}  # fmt: skip


DOORS = table(
    "t1", "DOOR SCHEDULE", [0.05, 0.1, 0.45, 0.5], ["MARK", "WIDTH", "TYPE"],
    [["101", "3'-0\"", "A"], ["102", "3'-0\"", "B"], ["103", "6'-0\"", "A"], ["104", None, "C"]],
)  # fmt: skip
FINISHES = table(
    "t2", "FINISH SCHEDULE", [0.55, 0.1, 0.95, 0.5], ["AREA", "ROOM", "FLOOR"],
    [["Gym", "101", "WD"], ["Gym", "102", "RB"]], key_column=1,
)  # fmt: skip


def schedule(tables: list[dict[str, Any]], truth: str = "tables") -> Extraction:
    return extraction(file=SHEET, truth=truth, plans=[], tables=tables)


def test_tables_damaged_copy_scores_exactly() -> None:
    gold = schedule([DOORS, FINISHES])
    pred = schedule(
        [
            table(  # moved so far that only the title (case and spaces aside) finds it
                "x", " door  Schedule", [0.05, 0.6, 0.45, 0.95], ["Mark", "Door Width", "TYPE"],
                [["101", "3'-0\"", "A"],  # all right
                 ["102", "3'-6\"", "B"],  # width wrong
                 [" 103 ", "6'-0\"", " a "],  # right after whitespace and case
                 ["999", "1'-0\"", "A"]],  # extra; 104 is missing
            ),
            table("y", "TITLE BLOCK", [0.55, 0.6, 0.95, 0.95], ["A"], [["x"]]),  # extra table
        ]
    )  # fmt: skip
    tables = score_extraction([gold], {SHEET: pred}).tables
    assert tables is not None and tables.files == 1
    assert (tables.tables_found.correct, tables.tables_found.n) == (1, 2)  # FINISHES not found
    assert tables.tables_extra == 1
    assert (tables.row_recall.correct, tables.row_recall.n) == (3, 6)  # 101-103 of 4 + 2
    assert (tables.row_precision.correct, tables.row_precision.n) == (3, 4)
    assert (tables.cell_accuracy.correct, tables.cell_accuracy.n) == (5, 6)  # 3 rows x 2 cells
    assert tables.headers_differ == 1  # "Door Width" vs "WIDTH": counted, not scored


def test_tables_key_column_and_positional_columns() -> None:
    """FINISHES is keyed by ROOM (its AREA repeats); columns pair by position, not by header."""
    gold = schedule([FINISHES])
    swapped = table("x", "FINISH SCHEDULE", FINISHES["box"], ["Area", "Room No", "Floor"],
                    [["Gym", "102", "RB"], ["Gym", "101", "WD"]])  # fmt: skip
    tables = score_extraction([gold], {SHEET: schedule([swapped])}).tables
    assert tables is not None
    assert (tables.row_recall.correct, tables.cell_accuracy.correct) == (2, 4)
    assert tables.headers_differ == 1
    reordered = table("x", "FINISH SCHEDULE", FINISHES["box"], ["ROOM", "AREA", "FLOOR"],
                      [["101", "Gym", "WD"], ["102", "Gym", "RB"]])  # fmt: skip
    tables = score_extraction([gold], {SHEET: schedule([reordered])}).tables
    assert tables is not None
    assert tables.row_recall.correct == 0  # its key column 1 holds "Gym", "Gym"


def test_a_schedule_sheet_is_scored_on_its_tables_only() -> None:
    gold = schedule([DOORS])
    result = score_extraction([gold], {SHEET: schedule([DOORS])})
    assert result.counts == {} and result.plans == {} and result.elements == {}
    assert result.scale_overall.excluded == 1  # not a scale case
    assert result.tables is not None and result.tables.cell_accuracy.rate == 1.0
    missing = score_extraction([gold], {}).tables
    assert missing is not None and missing.tables_found.correct == 0
    plain = score_extraction([extraction()], {PLAN: extraction()})
    assert plain.tables is None and plain.conflicts is None  # no section without gold for it


def conflict(
    id_: str, quantity: str, subject: dict[str, Any], status: str, values: tuple[float, float]
) -> dict[str, Any]:
    methods = ("printed_label", "polygon_x_scale")
    measured = [{"value": v, "method": m} for v, m in zip(values, methods, strict=True)]
    return {"id": id_, "quantity": quantity, "subject": subject, "status": status,
            "tolerance": 0.02, "values": measured}  # fmt: skip


def room(id_: str, box: list[float]) -> dict[str, Any]:
    return {"id": id_, "type": "bedroom", "page": 1, "box": box}


R1, R2 = [0.1, 0.1, 0.4, 0.4], [0.5, 0.5, 0.9, 0.9]
GOLD_CONFLICTS = [
    conflict("c1", "room_area", {"kind": "room", "ref": "r1"}, "conflict", (12.5, 13.4)),
    conflict("c2", "room_area", {"kind": "room", "ref": "r2"}, "agree", (8.0, 8.1)),
    conflict("c3", "element_count", {"kind": "class", "ref": "window"}, "conflict", (4, 5)),
    conflict("c4", "scale", {"kind": "sheet", "ref": None}, "agree", (0.01, 0.01)),
]


def test_conflicts_damaged_copy_scores_exactly() -> None:
    gold = extraction(rooms=[room("r1", R1), room("r2", R2)], conflicts=GOLD_CONFLICTS)
    pred = extraction(
        rooms=[room("x2", R2), room("x1", R1)],  # the pipeline's own room ids
        conflicts=[
            conflict("p1", "room_area", {"kind": "room", "ref": "x1"}, "conflict", (12.5, 13)),
            conflict("p2", "room_area", {"kind": "room", "ref": "x2"}, "conflict", (8, 9)),
            conflict("p3", "element_count", {"kind": "class", "ref": "door"}, "conflict", (2, 3)),
            conflict("p4", "scale", {"kind": "sheet", "ref": None}, "agree", (0.01, 0.01)),
        ],
    )
    other = "data/cubicasa5k/plan-2.png"
    outside = extraction(file=other, conflicts=[GOLD_CONFLICTS[2]])  # gold lists none there
    score = score_extraction([gold, extraction(file=other)], {PLAN: pred, other: outside})
    conflicts = score.conflicts
    assert conflicts is not None and conflicts.files == 1 and conflicts.not_scored == 1
    area, count = conflicts.by_quantity["room_area"], conflicts.by_quantity["element_count"]
    assert (area.found, area.conflicts, area.false_alarms, area.agree) == (1, 1, 1, 1)
    assert (count.found, count.conflicts, count.unlisted) == (0, 1, 1)  # door is not window
    scale = conflicts.by_quantity["scale"]
    assert (scale.false_alarms, scale.agree) == (0, 1)
    overall = conflicts.overall
    assert (overall.found, overall.conflicts, overall.false_alarms, overall.agree) == (1, 2, 1, 2)
    assert overall.recall == 0.5 and overall.false_alarm_rate == 0.5 and overall.unlisted == 1
    [file] = conflicts.per_file
    assert (file.missed, file.false_alarms, file.unlisted) == (["c3"], ["c2"], ["p3"])
    quiet = {PLAN: pred.model_copy(update={"conflicts": None}), other: extraction(file=other)}
    without = score_extraction([gold, extraction(file=other)], quiet)
    assert score.rooms == without.rooms and score.counts == without.counts  # headline unchanged


def test_conflicts_oracle_and_missing_file() -> None:
    gold = extraction(
        rooms=[room("r1", R1), room("r2", R2)],
        apartments=[{"id": "a1", "label": "Apt 2"}],
        conflicts=[
            *GOLD_CONFLICTS,
            conflict("c5", "apartment_area", {"kind": "apartment", "ref": "a1"}, "conflict",
                     (60, 64)),
        ],
    )  # fmt: skip
    oracle = score_extraction([gold], {PLAN: gold}).conflicts
    assert oracle is not None
    assert oracle.overall.recall == 1.0 and oracle.overall.false_alarms == 0
    by_label = extraction(  # another apartment id, the same label
        apartments=[{"id": "z9", "label": "apt  2"}],
        conflicts=[conflict("q", "apartment_area", {"kind": "apartment", "ref": "z9"}, "conflict",
                            (60, 64))],
    )  # fmt: skip
    labelled = score_extraction([gold], {PLAN: by_label}).conflicts
    assert labelled is not None and labelled.by_quantity["apartment_area"].found == 1
    missing = score_extraction([gold], {}).conflicts
    assert missing is not None
    assert missing.overall.found == 0 and missing.overall.false_alarms == 0
    assert missing.per_file[0].missed == ["c1", "c3", "c5"]


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"rows": [{"cells": ["1", "2"]}]}, "do not have 3 cells"),
        ({"key_column": 3}, "key_column 3 is not a column"),
        ({"columns": []}, "at least 1"),
    ],
)
def test_a_bad_table_is_refused(change: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        schedule([{**DOORS, **change}])


@pytest.mark.parametrize(
    ("entry", "message"),
    [
        ({**GOLD_CONFLICTS[0], "subject": {"kind": "room", "ref": "r9"}}, "names room 'r9'"),
        ({**GOLD_CONFLICTS[3], "subject": {"kind": "sheet", "ref": "x"}}, "null for a sheet"),
        ({**GOLD_CONFLICTS[2], "subject": {"kind": "class", "ref": "socket"}}, "not an element"),
        ({**GOLD_CONFLICTS[0], "values": GOLD_CONFLICTS[0]["values"][:1]}, "at least 2"),
        ({**GOLD_CONFLICTS[0], "values": [{"value": 1, "method": "detector"}] * 2}, "different"),
        ({**GOLD_CONFLICTS[0], "status": "maybe"}, "conflict"),
        ({**GOLD_CONFLICTS[0], "values": [{"value": 1, "method": "detector", "page": 3},
                                          {"value": 2, "method": "parser"}]}, "page 3"),
    ],
)  # fmt: skip
def test_a_bad_conflict_is_refused(entry: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        extraction(rooms=[room("r1", R1)], conflicts=[entry])


def test_truth_tables_needs_tables_and_no_elements() -> None:
    with pytest.raises(ValidationError, match="truth: tables needs tables"):
        schedule([])
    with pytest.raises(ValidationError, match="truth: tables needs tables"):
        extraction(file=SHEET, truth="tables", tables=[DOORS], rooms=[room("r1", R1)])
    assert schedule([DOORS], truth="elements").tables  # a plan sheet with a schedule


def test_score_extraction_records_both_sections(tmp_path: Path) -> None:
    gold = schedule([DOORS])
    plan = extraction(rooms=[room("r1", R1), room("r2", R2)], conflicts=GOLD_CONFLICTS)
    write(tmp_path / "gold/opening_design", "a801.json", gold)
    write(tmp_path / "gold/cubicasa5k", "plan-1.json", plan)
    write(tmp_path / "pred", "a801.json", gold)
    write(tmp_path / "pred", "plan-1.json", plan)
    results = tmp_path / "results"
    argv = ["score-extraction", str(tmp_path / "pred"), "--against", "dev",
            "--gold", str(tmp_path / "gold"), "--results", str(results),
            "--runs-dir", str(tmp_path / "runs"), "--name", "copy"]  # fmt: skip
    assert main(argv) == 0
    [record] = read_extraction_history(results)
    assert record.tables is not None and record.tables.cell_accuracy.rate == 1.0
    assert record.conflicts is not None and record.conflicts.overall.found.rate == 1.0
    assert record.conflicts.by_quantity["room_area"].agree == 1
    assert record.counts_exact.rate == 1.0  # headline as before
    text = json.loads(next(results.glob("*.json")).read_text("utf-8"))
    assert SHEET not in json.dumps(text)  # aggregates only: the repo is public

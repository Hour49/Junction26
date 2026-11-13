"""The two output formats against their contracts: what the writers put on disk is valid against
eval/schemas/*.schema.json (decision records 0002 and 0004), and the extraction reader gives back
the drawing that was written."""

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from app.adapters.answer_v1 import AnswerV1Writer
from app.adapters.extraction_v1 import ExtractionV1Reader, ExtractionV1Writer
from app.core.answering.model import Answer, Evidence
from app.core.drawing.model import (
    Apartment,
    Conflict,
    Drawing,
    Element,
    MeasuredValue,
    Page,
    Plan,
    Room,
    Scale,
    Subject,
    Table,
    TableRow,
)
from app.core.errors import InvalidInputError, NotFoundError

SCHEMAS = Path(__file__).parents[2] / "eval" / "schemas"
FILE = "data/demo/plan.pdf"
BOX = (0.1, 0.2, 0.3, 0.4)
PAGE = Page(page=1, width=1190.55, height=841.89, unit="pt")

EMPTY = Drawing(file=FILE, pages=(PAGE,), scale=Scale(status="no_scale"))
FULL = Drawing(
    file=FILE,
    pages=(PAGE,),
    scale=Scale(
        status="scaled",
        m_per_unit=0.035278,
        evidence=("scale_text", "scale_bar"),
        text="1:100",
        source="title block",
    ),
    plans=(Plan(id="p1", page=1, box=(0.0, 0.0, 1.0, 0.9), storey=2),),
    elements=(
        Element(
            id="e1",
            class_="door",
            page=1,
            plan="p1",
            box=BOX,
            polygon=((0.1, 0.2), (0.3, 0.2), (0.3, 0.4)),
            attrs={"source_class": "DOOR", "multiplicity": 1},
        ),
        Element(id="e2", class_="window", page=1, box=(0.5, 0.5, 0.6, 0.6)),
    ),
    rooms=(
        Room(
            id="r1",
            type="bedroom",
            label="Zimmer",
            page=1,
            plan="p1",
            box=(0.2, 0.2, 0.8, 0.8),
            area_m2=14.2,
            apartment="aA",
        ),
    ),
    apartments=(Apartment(id="aA", label="A", area_m2=86.8),),
    notes=("synthetic",),
)
WITH_EXTRAS = FULL.model_copy(
    update={
        "tables": (
            Table(
                id="t1",
                page=1,
                box=BOX,
                title="DOOR SCHEDULE",
                columns=("MARK", "WIDTH"),
                rows=(TableRow(cells=("101A", None), box=BOX),),
            ),
        ),
        "conflicts": (
            Conflict(
                id="c1",
                quantity="element_count",
                subject=Subject(kind="class", ref="door"),
                status="conflict",
                tolerance=0.0,
                values=(
                    MeasuredValue(value=1, unit="count", method="parser"),
                    MeasuredValue(value=2, unit="count", method="detector", page=1, box=BOX),
                ),
            ),
        ),
    }
)


def schema(name: str) -> dict[str, Any]:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def written(tmp_path: Path, drawing: Drawing, split: str = "dev") -> dict[str, Any]:
    ExtractionV1Writer(tmp_path, {FILE: "eval" if split == "eval" else "dev"}).write(drawing)
    return json.loads((tmp_path / "demo" / "plan.pdf.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("drawing", [EMPTY, FULL], ids=["empty", "full"])
def test_a_written_drawing_is_valid_extraction_v1(tmp_path: Path, drawing: Drawing) -> None:
    body = written(tmp_path, drawing, split="eval")
    Draft202012Validator(schema("extraction_v1.schema.json")).validate(body)
    assert (body["schema"], body["file"], body["split"], body["truth"]) == (
        "extraction_v1",
        FILE,
        "eval",
        "elements",
    )
    # Written only when the drawing has them, so the file is also valid before 0004's amendment.
    assert "tables" not in body
    assert "conflicts" not in body


def test_tables_and_conflicts_are_written_in_the_pinned_shape(tmp_path: Path) -> None:
    body = written(tmp_path, WITH_EXTRAS)
    assert body["tables"] == [
        {
            "id": "t1",
            "page": 1,
            "box": list(BOX),
            "title": "DOOR SCHEDULE",
            "columns": ["MARK", "WIDTH"],
            "rows": [{"cells": ["101A", None], "box": list(BOX)}],
        }
    ]
    parser = {"value": 1.0, "unit": "count", "method": "parser", "page": None, "box": None}
    detector = {"value": 2.0, "unit": "count", "method": "detector", "page": 1, "box": list(BOX)}
    assert body["conflicts"] == [
        {
            "id": "c1",
            "quantity": "element_count",
            "subject": {"kind": "class", "ref": "door"},
            "status": "conflict",
            "tolerance": 0.0,
            "values": [parser, detector],
            "resolution": None,
            "note": None,
        }
    ]
    properties = schema("extraction_v1.schema.json")["properties"]
    if "tables" not in properties or "conflicts" not in properties:
        pytest.skip("eval/schemas/extraction_v1.schema.json has no tables and conflicts yet")
    Draft202012Validator(schema("extraction_v1.schema.json")).validate(body)


def test_a_drawing_of_stated_totals_is_written_as_truth_counts(tmp_path: Path) -> None:
    body = written(tmp_path, EMPTY.model_copy(update={"counts": {"door": 9, "room:sauna": 1}}))
    Draft202012Validator(schema("extraction_v1.schema.json")).validate(body)
    assert (body["truth"], body["counts"]) == ("counts", {"door": 9, "room:sauna": 1})


def test_the_writer_refuses_a_file_without_a_split_or_outside_its_folder(tmp_path: Path) -> None:
    with pytest.raises(InvalidInputError, match="needs its split"):
        ExtractionV1Writer(tmp_path, {}).write(EMPTY)
    outside = EMPTY.model_copy(update={"file": "data/../../outside.pdf"})
    with pytest.raises(InvalidInputError, match="not a path inside"):
        ExtractionV1Writer(tmp_path / "out", {outside.file: "dev"}).write(outside)
    assert not (tmp_path / "outside.pdf.json").exists()


def test_the_reader_gives_back_the_drawing_that_was_written(tmp_path: Path) -> None:
    written(tmp_path, WITH_EXTRAS)
    reader = ExtractionV1Reader(tmp_path)
    assert reader.drawing(FILE) == WITH_EXTRAS
    assert reader.drawing("data/demo/other.pdf") is None


def test_the_reader_finds_files_by_their_file_field_and_skips_underscore_folders(
    tmp_path: Path,
) -> None:
    body = written(tmp_path / "scratch", EMPTY)
    gold = tmp_path / "gold"
    (gold / "demo").mkdir(parents=True)
    (gold / "demo" / "some-other-name.json").write_text(json.dumps(body), encoding="utf-8")
    (gold / "_reports").mkdir()
    (gold / "_reports" / "summary.json").write_text('{"not": "an extraction"}', encoding="utf-8")
    assert ExtractionV1Reader(gold).drawing(FILE) == EMPTY


def test_the_reader_takes_counts_only_from_a_truth_counts_file(tmp_path: Path) -> None:
    body = written(tmp_path / "scratch", EMPTY)
    for truth, expected in (("counts", {"door": 9}), ("elements", None)):
        folder = tmp_path / truth
        folder.mkdir()
        gold = {**body, "truth": truth, "counts": {"door": 9}}
        (folder / "plan.json").write_text(json.dumps(gold), encoding="utf-8")
        loaded = ExtractionV1Reader(folder).drawing(FILE)
        assert loaded is not None
        assert loaded.counts == expected


def test_the_reader_fails_loudly_on_a_bad_folder_or_file(tmp_path: Path) -> None:
    with pytest.raises(NotFoundError, match="not a folder"):
        ExtractionV1Reader(tmp_path / "missing")
    body = written(tmp_path / "scratch", EMPTY)
    for name, broken in (
        ("twice", None),
        ("typo", {**body, "scale": {"status": "no_scale", "colour": "red"}}),
        ("version", {**body, "schema": "extraction_v0"}),
    ):
        folder = tmp_path / name
        folder.mkdir()
        (folder / "a.json").write_text(json.dumps(broken or body), encoding="utf-8")
        if broken is None:
            (folder / "b.json").write_text(json.dumps(body), encoding="utf-8")
            with pytest.raises(InvalidInputError, match="both describe"):
                ExtractionV1Reader(folder)
        else:
            with pytest.raises(InvalidInputError, match=r"a\.json"):
                ExtractionV1Reader(folder).drawing(FILE)


def test_written_answers_are_valid_answer_v1_lines(tmp_path: Path) -> None:
    answers = [
        Answer(
            id=7,
            answer=2,
            unit="count",
            evidence=(Evidence(file=FILE, page=1, box=BOX),),
            method="takeoff",
            cost_usd=0.0,
            latency_s=0.25,
        ),
        Answer(
            id=8,
            answer=12.5,
            unit="m2",
            evidence=(),
            method="takeoff",
            cost_usd=0.002,
            latency_s=1.5,
        ),
        Answer(
            id=9,
            answer=None,
            unit=None,
            evidence=(),
            method="refused:unsupported-question",
            cost_usd=0.0,
            latency_s=0.0,
        ),
    ]
    path = tmp_path / "run" / "answers.jsonl"
    sink = AnswerV1Writer(path)
    assert path.read_text(encoding="utf-8") == ""
    for answer in answers:
        sink.write(answer)

    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    validator = Draft202012Validator(schema("answer_v1.schema.json"))
    for line in lines:
        validator.validate(line)
    assert [(line["id"], line["answer"], line["unit"]) for line in lines] == [
        (7, 2, "count"),
        (8, 12.5, "m2"),
        (9, None, None),
    ]
    assert lines[0]["evidence"] == [{"file": FILE, "page": 1, "box": list(BOX)}]

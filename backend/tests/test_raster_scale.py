"""RASTER_SCALE=priors: a raster sheet without a scale gets an estimated one from its detected
doors (else the page size), each room its outline area at it, and area answers say "estimated"
with the uncertainty. Off by default; without doors read the sheet stays no_scale. Synthetic."""

import json
import math
from collections.abc import Callable
from pathlib import Path

import pytest
from ingest.test_ingest_kind_wiring import drawing_png
from test_raster_composite import FILE, PNG, SHEET, Fake, Sink, element, gold

from app.adapters.extraction_v1 import ExtractionV1Reader, ExtractionV1Writer
from app.adapters.raster_scale import PriorScale
from app.composition import build_ingest, build_pipeline
from app.core.answering.model import Answer, Question
from app.core.drawing.model import Element, Page, Room, Scale
from app.core.errors import InvalidInputError
from app.core.pipeline.raster_scale import (
    BOX_RATIO,
    DOOR_M,
    FEW_DOORS,
    SPREAD_FEW,
    SPREAD_MANY,
    door_sides,
    estimate_scale,
    rooms_with_areas,
)
from app.settings import Settings

PAGE = Page(page=1, width=1000, height=500, unit="px")


def test_the_door_prior_counts_sure_located_doors_by_their_long_side() -> None:
    added = Element.model_validate(
        {"id": "a", "class": "door", "page": 1, "box": (0, 0, 1, 1), "attrs": {"located": False}}
    )
    elements = [
        element("door", (0.10, 0.10, 0.18, 0.12)),  # 80 x 10 px
        element("door", (0.30, 0.10, 0.31, 0.30)),  # 10 x 100 px
        element("door", (0.50, 0.10, 0.60, 0.30), score=0.3),  # unsure: left out
        element("window", (0.70, 0.10, 0.90, 0.30)),
        added,  # a count swap's door has no box of its own
    ]
    assert door_sides(elements, [PAGE]) == pytest.approx([80.0, 100.0])


def test_doors_give_an_estimated_scale_with_its_source_and_uncertainty() -> None:
    scale = estimate_scale([80.0, 100.0, 90.0])
    assert scale is not None and scale.status == "estimated"
    assert scale.m_per_unit == pytest.approx(DOOR_M / 90.0)
    assert scale.source is not None and "3 detected doors" in scale.source


def test_fewer_doors_print_a_wider_uncertainty() -> None:
    few, many = estimate_scale([90.0] * (FEW_DOORS - 1)), estimate_scale([90.0] * FEW_DOORS)
    assert few is not None and many is not None
    assert (few.uncertainty, many.uncertainty) == (SPREAD_FEW, SPREAD_MANY)
    assert SPREAD_FEW > SPREAD_MANY


def test_without_a_detected_door_there_is_no_estimate() -> None:
    assert estimate_scale([]) is None


def test_a_rooms_box_area_is_corrected_to_its_outline_and_marked_estimated() -> None:
    scale = Scale(status="estimated", m_per_unit=0.01, uncertainty=0.1)
    box = Room(id="r1", type="living", page=1, box=(0.0, 0.0, 0.4, 0.5))  # 400 x 250 px
    square = ((0.0, 0.0), (0.2, 0.0), (0.2, 0.4), (0.0, 0.4))  # 200 x 200 px
    outlined = Room(id="r2", type="bedroom", page=1, box=(0.0, 0.0, 0.2, 0.4), polygon=square)
    printed = Room(id="r3", type="wc", page=1, box=(0.5, 0.5, 0.6, 0.6), area_m2=1.5)

    got = rooms_with_areas([box, outlined, printed], scale, [PAGE])

    assert got[0].area_m2 == pytest.approx(round(400 * 250 * 0.01**2 / BOX_RATIO, 2))
    assert got[1].area_m2 == pytest.approx(4.0)
    assert (got[0].area_status, got[0].area_source) == ("estimated", "geometry_x_estimate")
    # the scale's spread counts twice for an area, with the outline's on top
    assert got[0].area_uncertainty is not None and got[0].area_uncertainty > math.expm1(0.2)
    assert got[2] == printed


def test_the_wrapper_estimates_only_a_missing_scale_and_only_when_doors_were_read() -> None:
    door = element("door", (0.1, 0.1, 0.3, 0.2))  # 8 px on the 40 x 30 sheet
    living = Room(id="r1", type="living", page=1, box=(0.0, 0.0, 0.5, 0.5))
    found = PriorScale(Fake(elements=[door], rooms=[living])).extract(FILE, SHEET)
    assert found.scale.status == "estimated"
    assert found.scale.m_per_unit == pytest.approx(DOOR_M / 8)
    assert found.rooms[0].area_status == "estimated"
    assert found.notes[-1].startswith("scale estimate: door-leaf prior")

    no_doors = PriorScale(Fake(rooms=[living], read=["room"])).extract(FILE, SHEET)
    assert no_doors.scale.status == "no_scale"
    assert no_doors.rooms[0].area_m2 is None
    assert no_doors.notes[-1] == "scale estimate: not made, the doors were not read"

    doorless = PriorScale(Fake(rooms=[living])).extract(FILE, SHEET)  # doors read, none found
    assert doorless.scale.status == "no_scale"
    assert doorless.rooms[0].area_m2 is None
    assert doorless.notes[-1] == "scale estimate: not made, no door was detected"

    measured = Fake(elements=[door])
    measured.found = measured.found.model_copy(
        update={"scale": Scale(status="scaled", m_per_unit=0.02, evidence=("scale_text",))}
    )
    assert PriorScale(measured).extract(FILE, SHEET).scale.m_per_unit == 0.02


def write_arm(arm: Path) -> None:
    doors = [
        {"id": f"d{i}", "class": "door", "page": 1, "plan": "p1", "box": box}
        for i, box in enumerate(([0.1, 0.1, 0.3, 0.2], [0.6, 0.1, 0.8, 0.2]))
    ]
    living = {"id": "r", "type": "living", "label": "OH", "page": 1, "plan": "p1"}
    rooms = [{**living, "box": [0.0, 0.0, 0.5, 0.5]}]
    arm.mkdir()
    (arm / "colorful-1.json").write_text(json.dumps(gold(PNG, elements=doors, rooms=rooms)))


def ask(tmp_path: Path, question: str) -> Answer:
    dataset, out = tmp_path / "dataset", tmp_path / "out"
    pipeline = build_pipeline(Settings(), dataset)
    pipeline.ingest([PNG], ExtractionV1Writer(out, {PNG: "dev"}))
    answers: list[Answer] = []
    pipeline.answer_questions(
        [Question(id=1, file=PNG, text=question)], ExtractionV1Reader(out), Sink(answers)
    )
    return answers[0]


def test_an_area_question_is_answered_as_an_estimate_only_when_the_setting_is_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, make_png: Callable[[int, int], bytes]
) -> None:
    (tmp_path / "dataset" / "data" / "cubicasa5k").mkdir(parents=True)
    (tmp_path / "dataset" / PNG).write_bytes(make_png(40, 30))
    write_arm(tmp_path / "arm")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EXTRACTOR_RASTER", "composite")
    arm = tmp_path / "arm"
    monkeypatch.setenv("RASTER_COMPONENTS", f"elements=dir:{arm},rooms=dir:{arm},plans=dir:{arm}")
    monkeypatch.setenv("QUESTION_PARSER", "templates")
    monkeypatch.setenv("ANSWER_PRIOR", "none")
    question = "What is the floor area of the living room (OH) in square metres?"

    off = ask(tmp_path, question)  # RASTER_SCALE is off by default
    assert (off.answer, off.abstain) == (None, True)

    monkeypatch.setenv("RASTER_SCALE", "priors")
    on = ask(tmp_path, question)
    side = DOOR_M / 8  # both doors are 8 px long
    assert on.answer == pytest.approx(round(20 * 15 * side**2 / BOX_RATIO, 2), abs=0.01)
    assert on.estimate is True
    assert on.explanation is not None
    assert "estimated" in on.explanation and "uncertainty" in on.explanation


def test_priors_with_a_scale_part_is_refused_at_startup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EXTRACTOR_RASTER", "composite")
    monkeypatch.setenv("RASTER_COMPONENTS", "plans=one-plan,scale=one-plan")
    monkeypatch.setenv("RASTER_SCALE", "priors")
    with pytest.raises(InvalidInputError, match="RASTER_SCALE=priors"):
        build_pipeline(Settings(), tmp_path)


def test_the_setting_is_part_of_the_ingest_reuse_key_only_when_on(tmp_path: Path) -> None:
    def readers(**on: str) -> dict[str, str]:
        settings = Settings(_env_file=None, **on)  # pyright: ignore[reportCallIssue]
        ingest = build_ingest(settings, tmp_path / "projects", background=False)
        status = ingest.status(ingest.start("plan.png", drawing_png()))
        ingest.close()
        return status.readers

    assert "raster_scale" not in readers()  # the default keeps the keys it had before
    assert readers(raster_scale="priors")["raster_scale"] == "priors"

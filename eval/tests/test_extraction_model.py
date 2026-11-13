"""extraction_v1: a good file parses, malformed ones are refused, the CLI check works."""

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from stoa_eval.cli import main
from stoa_eval.extraction import Extraction

GOOD: dict[str, Any] = {
    "schema": "extraction_v1",
    "file": "data/cubicasa5k/plan-1.png",
    "split": "dev",
    "truth": "elements",
    "pages": [{"page": 1, "width": 1000, "height": 800, "unit": "px"}],
    "scale": {"status": "no_scale"},
    "plans": [{"id": "p1", "page": 1, "box": [0.05, 0.1, 0.6, 0.9], "storey": None}],
    "elements": [
        {"id": "e1", "class": "door", "page": 1, "plan": "p1", "box": [0.2, 0.3, 0.25, 0.35],
         "polygon": None, "attrs": {"source_class": "Door Swing"}},
        {"id": "e2", "class": "door", "page": 1, "plan": "p1", "box": [0.4, 0.3, 0.45, 0.35]},
    ],
    "rooms": [
        {"id": "r1", "type": "bedroom", "label": "MH", "page": 1, "plan": "p1",
         "polygon": [[0.3, 0.2], [0.45, 0.2], [0.45, 0.4], [0.3, 0.4]],
         "box": [0.3, 0.2, 0.45, 0.4], "area_m2": 11.8, "apartment": "a1", "outdoor": False,
         "attrs": {}},
    ],
    "apartments": [{"id": "a1", "label": "Apt 2", "area_m2": 74.2}],
    "counts": None,
    "notes": [],
}  # fmt: skip


# formats v1.2: a sheet of a BIM model lists every object of the model, drawn here or not
MODEL: dict[str, Any] = {
    **GOOD,
    "model_objects": [
        {"id": "m1", "class": "door", "storey": "Level 1", "global_id": "g-1", "name": "D1",
         "quantities": {"width_m": 0.9, "height_m": 2.1}, "element": "e1",
         "attrs": {"source_class": "IfcDoor"}},
        {"id": "m2", "class": "space", "storey": "Level 1", "name": "101",
         "long_name": "Bedroom", "quantities": {"area_m2": 11.8}, "element": "r1"},
        {"id": "m3", "class": "wall", "storey": "Level 2",
         "quantities": {"length_m": 4.0, "side_area_m2": 10.4, "volume_m3": 1.0}},
        {"id": "m4", "class": "slab", "storey": None, "quantities": {}},
    ],
}  # fmt: skip
# a question on the .ifc path itself: no rendered page, only the model
PAGELESS: dict[str, Any] = {
    **MODEL,
    "file": "data/ifc_models/b1.ifc",
    "pages": [],
    "plans": [],
    "elements": [],
    "rooms": [],
    "apartments": [],
    "model_objects": [{**item, "element": None} for item in MODEL["model_objects"]],
}


def changed(path: str, value: Any, base: dict[str, Any] = GOOD) -> dict[str, Any]:
    """`base` with one value replaced; `path` like "elements.0.box"."""
    data = copy.deepcopy(base)
    *parents, last = path.split(".")
    target: Any = data
    for key in parents:
        target = target[int(key)] if key.isdigit() else target[key]
    target[int(last) if last.isdigit() else last] = value
    return data


def test_a_good_file_parses_and_counts_itself() -> None:
    extraction = Extraction.model_validate(GOOD)
    assert extraction.elements[0].class_ == "door"
    assert extraction.derived_counts() == {"plan": 1, "door": 2, "room:bedroom": 1}
    dumped = json.loads(extraction.model_dump_json(by_alias=True))
    assert dumped["schema"] == "extraction_v1" and dumped["elements"][0]["class"] == "door"
    counts_only = {**GOOD, "truth": "counts", "elements": [], "rooms": [], "apartments": [],
                   "counts": {"door": 7, "room:bedroom": 2, "plan": 1}}  # fmt: skip
    assert Extraction.model_validate(counts_only).counts == {
        "door": 7,
        "room:bedroom": 2,
        "plan": 1,
    }


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("plans.0.storey", 2),  # CubiCasa gold numbers its storeys
        ("plans.0.storey", "Level 1"),  # IFC names them
        (
            "scale",
            {
                "status": "scaled",
                "m_per_unit": 0.02,
                "evidence": ["printed_areas"],
                "source": "hand: printed area MH 12,5 m2 and KH 8 m2 agree within 0.4%",
            },
        ),
        (
            "scale",
            {
                "status": "scaled",
                "m_per_unit": 0.035278,
                "text": "1:100",
                "evidence": ["scale_text", "scale_bar", "printed_areas"],
                "source": "title block",
            },
        ),
        ("scale", {"status": "not_to_scale", "evidence": ["not_to_scale_note"]}),
        ("scale", {"status": "no_scale", "reference_m_per_unit": 0.01, "source": "annotation"}),
        (
            "scale",
            {
                "status": "estimated",
                "m_per_unit": 0.02,
                "uncertainty": 0.1,
                "source": "door widths",
            },
        ),
        (
            "scale",
            {
                "status": "estimated",
                "m_per_unit": 0.0101,
                "uncertainty": 0.08,
                "reference_m_per_unit": 0.0101,
                "source": "annotation unit; door widths 0.0104 (3% apart)",
            },
        ),
        (
            "scale",
            {
                "status": "not_to_scale",
                "evidence": ["not_to_scale_note"],
                "m_per_unit": 0.01,
                "uncertainty": 0.15,
                "source": "annotation unit",
            },
        ),
        (
            "rooms.0",
            {
                "id": "r1",
                "type": "bedroom",
                "page": 1,
                "box": [0.3, 0.2, 0.45, 0.4],
                "area_m2": 12.2,
                "area_status": "exact",
                "area_source": "printed",
            },
        ),
        (
            "rooms.0",
            {
                "id": "r1",
                "type": "bedroom",
                "page": 1,
                "box": [0.3, 0.2, 0.45, 0.4],
                "area_m2": 12.9,
                "area_status": "estimated",
                "area_source": "geometry_x_estimate",
                "area_uncertainty": 0.1,
            },
        ),
        ("elements.0.attrs", {"multiplicity": 2}),
        ("read", ["door", "window", "room"]),  # golden-7f: what the extraction looked for
        ("read", []),  # looked for nothing
    ],
)
def test_widened_fields_parse(path: str, value: Any) -> None:
    Extraction.model_validate(changed(path, value))


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        ("elements.0.box", [0.3, 0.3, 0.25, 0.35], "x0 <= x1"),
        ("elements.0.box", [0.2, 0.3, 1.25, 0.35], "less than or equal to 1"),
        ("elements.0.class", "doors", "door"),
        ("elements.0.colour", "red", "Extra inputs"),
        ("rooms.0.type", "lounge", "bedroom"),
        ("rooms.0.polygon", [[0.1, 0.1], [0.2, 0.2]], "at least 3"),
        ("elements.1.id", "e1", "repeated element ids"),
        ("elements.0.plan", "p9", "names plan 'p9'"),
        ("rooms.0.page", 2, "on page 2"),
        ("rooms.0.apartment", "a9", "apartment 'a9'"),
        ("truth", "counts", "needs a counts object"),
        ("counts", {"doors": 3}, "not a class"),
        ("counts", {"room:lounge": 1}, "not a class"),
        ("split", "holdout", "dev"),
        ("schema", "extraction_v2", "extraction_v1"),
        ("file", "cubicasa5k/plan-1.png", "pattern"),
        ("pages", [], "at least 1"),
        ("scale", None, "valid dictionary"),  # the old `scale: null` is refused
        ("scale", {"status": "scaled", "evidence": ["scale_text"]}, "m_per_unit is required"),
        ("scale", {"status": "scaled", "m_per_unit": 0.02}, "needs the evidence"),
        ("scale", {"status": "no_scale", "m_per_unit": 0.02}, "m_per_unit is null"),
        ("scale", {"status": "no_scale", "evidence": ["scale_bar"]}, "no_scale has no evidence"),
        ("scale", {"status": "not_to_scale"}, "not_to_scale_note"),
        ("scale", {"status": "estimated", "m_per_unit": 0.02}, "needs uncertainty"),
        (
            "scale",
            {"status": "scaled", "m_per_unit": 0.02, "evidence": ["scale_bar", "scale_bar"]},
            "twice",
        ),
        (
            "scale",
            {
                "status": "scaled",
                "m_per_unit": 0.02,
                "evidence": ["scale_bar"],
                "reference_m_per_unit": 0.02,
            },
            "reference_m_per_unit is not for scaled",
        ),
        # every image gets a value (Bogdan, 2026-11-13 23:33): the rules around it
        (
            "scale",
            {"status": "not_to_scale", "evidence": ["not_to_scale_note"], "m_per_unit": 0.01},
            "needs uncertainty and source",
        ),
        (
            "scale",
            {
                "status": "scaled",
                "m_per_unit": 0.02,
                "evidence": ["scale_bar"],
                "uncertainty": 0.05,
            },
            "uncertainty is for an approximate value",
        ),
        ("rooms.0.area_status", "estimated", "area_uncertainty is set exactly"),
        ("rooms.0.area_uncertainty", 0.1, "area_uncertainty is set exactly"),
        ("rooms.0.area_source", "printed", "area_source needs area_status"),
        (
            "rooms.0",
            {
                "id": "r1",
                "type": "bedroom",
                "page": 1,
                "box": [0.3, 0.2, 0.45, 0.4],
                "area_status": "exact",
            },
            "describe an area_m2",
        ),
        (
            "rooms.0",
            {
                "id": "r1",
                "type": "bedroom",
                "page": 1,
                "box": [0.3, 0.2, 0.45, 0.4],
                "area_m2": 11.8,
                "area_status": "exact",
                "area_source": "geometry_x_scale",
            },
            "a printed area is exact",
        ),
        (
            "rooms.0",
            {
                "id": "r1",
                "type": "bedroom",
                "page": 1,
                "box": [0.3, 0.2, 0.45, 0.4],
                "area_m2": 11.8,
                "area_status": "estimated",
                "area_source": "printed",
                "area_uncertainty": 0.1,
            },
            "a printed area is exact",
        ),
        ("scale", {"status": "scaled", "m_per_unit": 0.02, "evidence": ["ruler"]}, "scale_text"),
        ("elements.0.attrs", {"multiplicity": 0}, "multiplicity"),
        ("elements.0.attrs", {"multiplicity": True}, "multiplicity"),
        ("read", ["door", "doors"], "Input should be 'door'"),
        ("read", ["rooms"], "Input should be 'room'"),
        ("read", ["door", "room", "door"], "read lists"),
    ],
)
def test_a_bad_file_is_refused(path: str, value: Any, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        Extraction.model_validate(changed(path, value))


def test_validate_extraction_command(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    good = tmp_path / "gold/cubicasa5k/plan-1.json"
    good.parent.mkdir(parents=True)
    good.write_text(json.dumps(GOOD), encoding="utf-8")
    assert main(["validate-extraction", str(tmp_path / "gold")]) == 0
    assert "1 of 1 files are valid" in capsys.readouterr().out
    bad = tmp_path / "gold/cubicasa5k/plan-2.json"
    bad.write_text(json.dumps(changed("elements.0.class", "doors")), encoding="utf-8")
    assert main(["validate-extraction", str(tmp_path / "gold")]) == 1
    printed = capsys.readouterr()
    assert "plan-2.json" in printed.out and "1 of 2 files are valid" in printed.out


def test_model_objects_parse_and_leave_the_drawn_lists_alone() -> None:
    extraction = Extraction.model_validate(MODEL)
    objects = extraction.model_objects or []
    assert [item.class_ for item in objects] == ["door", "space", "wall", "slab"]
    assert objects[0].quantities == {"width_m": 0.9, "height_m": 2.1}
    assert objects[2].element is None and objects[3].storey is None
    assert extraction.derived_counts() == Extraction.model_validate(GOOD).derived_counts()
    dumped = json.loads(extraction.model_dump_json(by_alias=True))
    assert dumped["model_objects"][1]["class"] == "space"
    assert Extraction.model_validate(GOOD).model_objects is None  # every file without a model
    assert Extraction.model_validate({**MODEL, "model_objects": []}).model_objects == []


def test_an_ifc_file_without_pages_carries_only_the_model() -> None:
    extraction = Extraction.model_validate(PAGELESS)
    assert extraction.pages == [] and len(extraction.model_objects or []) == 4
    assert extraction.strict_v2_problems() == []  # no image, so no scale to ask for


def test_an_element_and_a_room_with_one_id_can_each_be_named_once() -> None:
    data = changed("rooms.0.id", "e1", MODEL)
    data["model_objects"][1]["element"] = "e1"  # the space names room e1, the door element e1
    Extraction.model_validate(data)


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        ("model_objects.0.class", "doors", "Input should be 'door'"),
        ("model_objects.0.class", "room", "'space'"),
        ("model_objects.0.colour", "red", "Extra inputs"),
        ("model_objects.0.id", "", "at least 1 character"),
        ("model_objects.0.quantities", {"perimeter_m": 3.0}, "'length_m'"),
        ("model_objects.0.quantities", {"width_m": -0.1}, "greater than or equal to 0"),
        ("model_objects.0.quantities", {"width_m": True}, "valid number"),
        ("model_objects.0.quantities", {"width_m": float("inf")}, "finite number"),
        ("model_objects.0.quantities", {"width_m": float("nan")}, "finite number"),
        ("model_objects.0.attrs", {"layers": ["a"]}, "attrs"),
        ("model_objects.1.id", "m1", "repeated model object ids"),
        ("model_objects.2.id", "e2", r"model object ids \['e2'\] are also element or room ids"),
        ("model_objects.2.id", "r1", r"model object ids \['r1'\] are also element or room ids"),
        ("model_objects.0.element", "e9", "names element 'e9', not listed"),
        ("model_objects.0.element", "r1", "names element 'r1', not listed"),
        ("model_objects.1.element", "e1", "names room 'e1', not listed"),
        ("model_objects.0.class", "window", "m1 is a window, element e1 a door"),
        ("model_objects.2.element", "e1", "element e1 is named twice"),
        ("model_objects.2",
         {"id": "m3", "class": "space", "element": "r1"}, "room r1 is named twice"),
        ("pages", [], "at least 1 page, unless an .ifc file has model_objects"),
    ],
)  # fmt: skip
def test_bad_model_objects_are_refused(path: str, value: Any, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        Extraction.model_validate(changed(path, value, MODEL))


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        ("model_objects", None, "unless an .ifc file has model_objects"),
        ("model_objects", [], "unless an .ifc file has model_objects"),
        ("file", "data/ifc_models/b1.pdf", "unless an .ifc file has model_objects"),
        ("plans", [{"id": "p1", "page": 1, "box": [0, 0, 1, 1]}], "empty plans, elements"),
        ("elements", [{"id": "e1", "class": "door", "page": 1, "box": [0, 0, 0.1, 0.1]}],
         "empty plans, elements"),
        ("rooms", [{"id": "r1", "type": "other", "page": 1, "box": [0, 0, 0.1, 0.1]}],
         "empty plans, elements"),
    ],
)  # fmt: skip
def test_only_an_ifc_model_file_goes_without_pages(path: str, value: Any, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        Extraction.model_validate(changed(path, value, PAGELESS))

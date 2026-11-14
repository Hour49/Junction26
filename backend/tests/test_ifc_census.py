from pathlib import Path
from typing import Any

import ifcopenshell
import ifcopenshell.guid
from ifc_models import Schema

from app.adapters.ifc_model.census import entity_census
from app.core.discipline import discipline_from_census


def _model(schema: Schema, classes: dict[str, int]) -> Any:
    file: Any = ifcopenshell.file(schema=schema)
    file.create_entity("IfcProject", GlobalId=ifcopenshell.guid.new())
    for name, count in classes.items():
        for _ in range(count):
            file.create_entity(name, GlobalId=ifcopenshell.guid.new())
    return file


def test_counts_each_class_without_its_subclasses() -> None:
    census = entity_census(_model("IFC4", {"IfcWall": 2, "IfcWallStandardCase": 1}))
    assert census == {"IfcProject": 1, "IfcWall": 2, "IfcWallStandardCase": 1}


def test_counts_a_lazily_opened_file_as_read_model_opens_it(tmp_path: Path) -> None:
    path = tmp_path / "m.ifc"
    _model("IFC2X3", {"IfcFlowSegment": 3, "IfcDuctSegmentType": 1}).write(str(path))
    opened: Any = ifcopenshell.open  # its typed overloads leave `lazy` out
    census = entity_census(opened(str(path), lazy=True))
    assert census["IfcFlowSegment"] == 3
    assert discipline_from_census(census)[0][0] == "ventilation"

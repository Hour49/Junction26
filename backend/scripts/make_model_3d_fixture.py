"""Writes frontend/e2e/fixtures/model-3d-house.ifc: a tiny synthetic IFC model with geometry for the
3D view's e2e (MODEL_3D=1): four walls, a slab and a door, each a box, plus a room (left out of the
view). Licence-safe: made here, no partner data. GlobalIds and the header time are fixed, so the
file is the same on every run.

    cd backend && uv run python scripts/make_model_3d_fixture.py
"""

import sys
from pathlib import Path

import ifcopenshell.guid

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "tests"))

from ifc_models import IfcFile, box  # noqa: E402

OUT = BACKEND.parent / "frontend" / "e2e" / "fixtures" / "model-3d-house.ifc"


def house() -> bytes:
    model = IfcFile()
    storey = model.storey("Ground floor")
    for name, outline in (
        ("Wall south", box(0, 0, 8, 0.2)),
        ("Wall east", box(7.8, 0, 8, 6)),
        ("Wall north", box(0, 5.8, 8, 6)),
        ("Wall west", box(0, 0, 0.2, 6)),
    ):
        model.element("IfcWall", storey=storey, name=name, solid=(outline, 0, 2.6))
    model.element("IfcSlab", storey=storey, name="Floor slab", solid=(box(0, 0, 8, 6), -0.25, 0.25))
    model.element(
        "IfcDoor", storey=storey, name="Front door", solid=(box(3.5, -0.05, 4.4, 0.25), 0, 2.1)
    )
    model.space(storey, "0.01", "Living", (box(0.2, 0.2, 7.8, 5.8), 0, 2.6))
    stable = ifcopenshell.file.from_string(model.ifc().decode())
    for at, rooted in enumerate(stable.by_type("IfcRoot"), start=1):
        rooted.GlobalId = ifcopenshell.guid.compress(f"{at:032x}")
    stable.header.file_name.time_stamp = "2026-11-14T00:00:00"
    return stable.to_string().encode()


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(house())
    print(f"wrote {OUT}")

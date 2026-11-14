"""The architecture and structural facts (facts_arch.py) of a small synthetic model, built with
ifcopenshell.api: no partner data."""

from typing import Any

import ifcopenshell
import ifcopenshell.api.aggregate
import ifcopenshell.api.context
import ifcopenshell.api.geometry
import ifcopenshell.api.material
import ifcopenshell.api.pset
import ifcopenshell.api.root
import ifcopenshell.api.spatial
import ifcopenshell.api.type
import ifcopenshell.api.unit
import pytest

from app.adapters.ifc_model.facts_arch import arch_facts
from app.core.ifc_facts import Fact


def _model(per_metre: float) -> Any:
    """Two storeys; on the ground floor two external brick walls (4 m and 6 m), one internal
    partition, a fire-rated door, a door of a Revit "Family:Type", a floor slab, a column, a
    pad footing and a kitchen of 4 x 3 m."""
    file = ifcopenshell.file(schema="IFC4")
    new = ifcopenshell.api.root.create_entity
    project = new(file, ifc_class="IfcProject", name="Demo")
    millimetres = per_metre == 1000
    ifcopenshell.api.unit.assign_unit(
        file,
        units=[
            ifcopenshell.api.unit.add_si_unit(
                file, unit_type="LENGTHUNIT", prefix="MILLI" if millimetres else None
            ),
            ifcopenshell.api.unit.add_si_unit(file, unit_type="AREAUNIT"),
            ifcopenshell.api.unit.add_si_unit(file, unit_type="VOLUMEUNIT"),
        ],
    )
    model = ifcopenshell.api.context.add_context(file, context_type="Model")
    body = ifcopenshell.api.context.add_context(
        file,
        context_type="Model",
        context_identifier="Body",
        target_view="MODEL_VIEW",
        parent=model,
    )
    site = new(file, ifc_class="IfcSite", name="Site")
    site.RefLatitude = (49, 6, 1, 566000)
    building = new(file, ifc_class="IfcBuilding", name="House")
    ground = new(file, ifc_class="IfcBuildingStorey", name="Ground")
    upper = new(file, ifc_class="IfcBuildingStorey", name="Upper")
    ground.Elevation, upper.Elevation = 0.0, 3.0 * per_metre
    ifcopenshell.api.aggregate.assign_object(file, products=[site], relating_object=project)
    ifcopenshell.api.aggregate.assign_object(file, products=[building], relating_object=site)
    ifcopenshell.api.aggregate.assign_object(
        file, products=[ground, upper], relating_object=building
    )

    def layered(ifc_class: str, name: str, layers: list[tuple[str, float]]) -> Any:
        kind = new(file, ifc_class=ifc_class, name=name)
        layer_set = ifcopenshell.api.material.add_material_set(
            file, name=name, set_type="IfcMaterialLayerSet"
        )
        for material, metres in layers:
            layer = ifcopenshell.api.material.add_layer(
                file,
                layer_set=layer_set,
                material=ifcopenshell.api.material.add_material(file, name=material),
            )
            layer.LayerThickness = metres * per_metre
        ifcopenshell.api.material.assign_material(
            file, products=[kind], type="IfcMaterialLayerSet", material=layer_set
        )
        return kind

    def placed(ifc_class: str, name: str, kind: Any | None = None, **attributes: Any) -> Any:
        element = new(file, ifc_class=ifc_class, name=name)
        for attribute, value in attributes.items():
            setattr(element, attribute, value)
        ifcopenshell.api.spatial.assign_container(
            file, products=[element], relating_structure=ground
        )
        if kind is not None:
            ifcopenshell.api.type.assign_type(file, related_objects=[element], relating_type=kind)
        return element

    def stated(element: Any, pset: str, properties: dict[str, Any]) -> None:
        added = ifcopenshell.api.pset.add_pset(file, product=element, name=pset)
        ifcopenshell.api.pset.edit_pset(file, pset=added, properties=properties)

    def quantities(element: Any, values: dict[str, Any]) -> None:
        added = ifcopenshell.api.pset.add_qto(file, product=element, name="Qto_BaseQuantities")
        ifcopenshell.api.pset.edit_qto(file, qto=added, properties=values)

    brick = layered("IfcWallType", "Brick 300", [("Brick", 0.2), ("Insulation", 0.1)])
    partition = layered("IfcWallType", "Partition 100", [("Gypsum", 0.1)])
    for name, length, kind, external in (
        ("W1", 4.0, brick, True),
        ("W2", 6.0, brick, True),
        ("W3", 2.0, partition, False),
    ):
        wall = placed("IfcWall", name, kind)
        stated(wall, "Pset_WallCommon", {"IsExternal": external, "LoadBearing": external})
        quantities(wall, {"Length": length * per_metre})
    door = placed("IfcDoor", "D1", OverallWidth=0.9 * per_metre, OverallHeight=2.1 * per_metre)
    stated(door, "Pset_DoorCommon", {"FireRating": "EI30"})
    revit = placed("IfcDoor", "D2", new(file, ifc_class="IfcDoorType", name="1000 x 2100"))
    revit.ObjectType = "Single-Flush:1000 x 2100:123456"
    placed(
        "IfcDoor",
        "Single-Flush:800 x 2000:800 x 2000:42",
        new(file, ifc_class="IfcDoorType", name="800 x 2000"),
    )
    footing = placed("IfcFooting", "F1", ObjectType="Pad footing 1200")
    quantities(footing, {"NetVolume": 2.0})
    slab = placed("IfcSlab", "S1", layered("IfcSlabType", "Floor 250", [("Concrete", 0.25)]))
    slab.PredefinedType = "FLOOR"
    quantities(slab, {"NetVolume": 5.0})
    column = placed("IfcColumn", "C1")
    section = file.create_entity(
        "IfcRectangleProfileDef", ProfileType="AREA", XDim=0.3 * per_metre, YDim=0.4 * per_metre
    )
    ifcopenshell.api.geometry.assign_representation(
        file,
        product=column,
        representation=ifcopenshell.api.geometry.add_profile_representation(
            file, context=body, profile=section, depth=3.0
        ),
    )
    kitchen = new(file, ifc_class="IfcSpace", name="101")
    kitchen.LongName = "Kitchen"
    ifcopenshell.api.aggregate.assign_object(file, products=[kitchen], relating_object=ground)
    ifcopenshell.api.geometry.edit_object_placement(file, product=kitchen)
    ifcopenshell.api.geometry.assign_representation(
        file,
        product=kitchen,
        representation=ifcopenshell.api.geometry.add_wall_representation(
            file, context=body, length=4.0, height=2.5, thickness=3.0
        ),
    )
    quantities(kitchen, {"NetFloorArea": 11.5})
    return file


def _value(facts: list[Fact], topic: str, subject: str, storey: str | None = None) -> Any:
    found = [f.value for f in facts if (f.topic, f.subject, f.storey) == (topic, subject, storey)]
    assert len(found) == 1, (topic, subject, storey, found)
    return found[0]


@pytest.fixture(scope="module", params=[1.0, 1000.0], ids=["metres", "millimetres"])
def facts(request: pytest.FixtureRequest) -> list[Fact]:
    return arch_facts(_model(request.param))


def test_project_and_storeys(facts: list[Fact]) -> None:
    assert _value(facts, "project.name", "Demo") == "Demo"
    assert _value(facts, "project.schema", "project") == "IFC4"
    assert _value(facts, "site.latitude", "Site") == pytest.approx(49.100435, abs=1e-6)
    assert _value(facts, "storey.count", "all") == 2
    assert _value(facts, "storey.elevation", "Upper", "Upper") == pytest.approx(3.0)
    assert _value(facts, "storey.height", "Ground", "Ground") == pytest.approx(3.0)


def test_walls_by_type_and_by_part(facts: list[Fact]) -> None:
    assert _value(facts, "wall.count", "all") == 3
    assert _value(facts, "wall.count", "all", "Ground") == 3
    assert _value(facts, "wall.length", "external") == pytest.approx(10.0)
    assert _value(facts, "wall.length", "internal") == pytest.approx(2.0)
    assert _value(facts, "wall.count", "load_bearing") == 2
    assert _value(facts, "wall_type.count", "Brick 300") == 2
    assert _value(facts, "wall_type.count", "Partition 100 | internal") == 1
    assert _value(facts, "wall_type.thickness", "Brick 300") == pytest.approx(0.3)
    assert _value(facts, "wall_type.layer", "Brick 300 | layer 2 | Insulation") == pytest.approx(
        0.1
    )
    assert _value(facts, "wall_thickness.count", "300 mm") == 2
    materials = {f.value for f in facts if f.topic == "wall_type.material"}
    assert materials == {"Brick", "Insulation", "Gypsum"}


def test_doors_slabs_and_columns(facts: list[Fact]) -> None:
    assert _value(facts, "door.width", "D1", "Ground") == pytest.approx(0.9)
    assert _value(facts, "door_size.count", "900 x 2100 mm") == 1
    assert _value(facts, "door_type.fire_rating", "D1") == "EI30"  # untyped: named by itself
    assert _value(facts, "slab.net_volume", "predefined:FLOOR") == pytest.approx(5.0)
    assert _value(facts, "slab_type.thickness", "Floor 250") == pytest.approx(0.25)
    assert _value(facts, "material.net_volume", "Concrete") == pytest.approx(5.0)
    assert _value(facts, "column.profile_width", "C1", "Ground") == pytest.approx(0.3)
    assert _value(facts, "column.profile_depth", "C1", "Ground") == pytest.approx(0.4)
    assert _value(facts, "beam.count", "all") == 0


def test_a_space_has_the_footprint_area_and_the_stated_one_apart(facts: list[Fact]) -> None:
    assert _value(facts, "space.area", "101", "Ground") == pytest.approx(12.0)
    assert _value(facts, "space.net_floor_area", "101", "Ground") == pytest.approx(11.5)
    assert _value(facts, "space.long_name", "101", "Ground") == "Kitchen"
    assert _value(facts, "space_function.area", "Kitchen") == pytest.approx(12.0)
    assert _value(facts, "space.count", "all", "Ground") == 1


def test_every_fact_is_of_its_discipline(facts: list[Fact]) -> None:
    assert {f.discipline for f in facts if f.topic.startswith(("slab", "column"))} == {"structural"}
    assert {f.discipline for f in facts if f.topic.startswith(("wall", "space"))} == {
        "architecture"
    }


def test_derived_numbers_are_facts(facts: list[Fact]) -> None:
    assert _value(facts, "structural.count.total", "all") == 5  # slab, column, footing, W1, W2
    assert _value(facts, "structural.count.total", "all", "Ground") == 5
    assert _value(facts, "foundation.net_volume.total", "all") == pytest.approx(2.0)
    assert _value(facts, "foundation.count.total", "footing") == 1
    assert _value(facts, "slab.volume.by_material_kind", "concrete") == pytest.approx(5.0)
    assert _value(facts, "wall.count.by_material_kind", "masonry") == 2
    assert _value(facts, "wall.count.by_material", "Gypsum") == 1
    assert _value(facts, "element.volume.by_material_kind", "concrete") == pytest.approx(5.0)
    assert _value(facts, "wall.length.min", "all") == pytest.approx(2.0)
    assert _value(facts, "wall.length.max", "external") == pytest.approx(6.0)
    assert _value(facts, "wall.length.average", "all") == pytest.approx(4.0)
    assert _value(facts, "wall.length.per_storey", "all") == pytest.approx(12.0)
    assert _value(facts, "space.area.per_storey", "all") == pytest.approx(12.0)


def test_a_revit_type_is_also_named_family_and_type(facts: list[Fact]) -> None:
    assert _value(facts, "door_type.count", "1000 x 2100") == 1
    assert _value(facts, "door_type.count", "Single-Flush:1000 x 2100") == 1
    assert _value(facts, "door_type.count", "Single-Flush:800 x 2000") == 1  # from its Name
    types = {f.value for f in facts if (f.topic, f.subject) == ("door.type", "D2")}
    assert types == {"1000 x 2100", "Single-Flush:1000 x 2100"}


def test_storeys_without_elevation_still_give_a_sheet() -> None:
    file = ifcopenshell.file(schema="IFC4")
    ifcopenshell.api.root.create_entity(file, ifc_class="IfcProject", name="P")
    ifcopenshell.api.unit.assign_unit(file)
    building = ifcopenshell.api.root.create_entity(file, ifc_class="IfcBuilding", name="B")
    storeys = [
        ifcopenshell.api.root.create_entity(file, ifc_class="IfcBuildingStorey", name=name)
        for name in ("A", "B")
    ]
    ifcopenshell.api.aggregate.assign_object(file, products=storeys, relating_object=building)
    facts = arch_facts(file)
    assert _value(facts, "storey.count", "all") == 2
    assert not [f for f in facts if f.topic in ("storey.elevation", "storey.height")]

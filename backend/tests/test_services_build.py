"""Building the services model from IFC, and its store (services-model.md SV-1..SV-5, SV-8)."""

import gzip
import json
from pathlib import Path
from typing import Any, Literal

import ifcopenshell
import ifcopenshell.guid
import pytest

from app.adapters.ifc_model.facts_mep import mep_facts
from app.adapters.ifc_model.services_model import build_services_model
from app.adapters.services_store import ServicesStore
from app.core.services import derive

Schema = Literal["IFC4", "IFC2X3"]
# IFC4 class, IFC2X3 class + its type class (an IFC2X3 file writes the generic class)
CLASSES = {
    "boiler": ("IfcBoiler", "IfcEnergyConversionDevice", "IfcBoilerType"),
    "heater": ("IfcSpaceHeater", "IfcFlowTerminal", "IfcSpaceHeaterType"),
    "pipe": ("IfcPipeSegment", "IfcFlowSegment", "IfcPipeSegmentType"),
    "tee": ("IfcPipeFitting", "IfcFlowFitting", "IfcPipeFittingType"),
}


class _Ifc:
    """A model in millimetres with one storey at 3 m, built from boxes."""

    def __init__(self, schema: Schema = "IFC4", shift: float = 0.0) -> None:
        self.schema, self.shift = schema, shift
        self.f: Any = ifcopenshell.file(schema=schema)
        mm = self.f.createIfcSIUnit(None, "LENGTHUNIT", "MILLI", "METRE")
        self.context = self.f.createIfcGeometricRepresentationContext(
            None, "Model", 3, 1e-5, self._axes((0.0, 0.0, 0.0))
        )
        project = self._new(
            "IfcProject",
            Name="p",
            UnitsInContext=self.f.createIfcUnitAssignment([mm]),
            RepresentationContexts=[self.context],
        )
        self.storey = self._new(
            "IfcBuildingStorey",
            Name="Level 1",
            Elevation=3000.0,
            ObjectPlacement=self.f.createIfcLocalPlacement(None, self._axes((0.0, 0.0, 3000.0))),
        )
        self._new("IfcRelAggregates", RelatingObject=project, RelatedObjects=[self.storey])
        self.contained: list[Any] = []

    def _new(self, ifc_class: str, **attrs: Any) -> Any:
        return self.f.create_entity(ifc_class, GlobalId=ifcopenshell.guid.new(), **attrs)

    def _axes(self, at: tuple[float, float, float]) -> Any:
        return self.f.createIfcAxis2Placement3D(self.f.createIfcCartesianPoint(at), None, None)

    def _placed(self, x: float, y: float, z: float, parent: Any = None) -> Any:
        """A placement at (x, y, z) metres above the storey (shifted by `shift` in plan)."""
        at = ((x + self.shift) * 1000, (y + self.shift) * 1000, z * 1000)
        return self.f.createIfcLocalPlacement(parent or self.storey.ObjectPlacement, self._axes(at))

    def box(self, ifc_class: str, x: float, y: float, z: float, size: tuple, **attrs: Any) -> Any:
        """A box centred on (x, y) in plan, from z up, `size` (dx, dy, dz) in metres."""
        dx, dy, dz = size
        solid = self.f.createIfcExtrudedAreaSolid(
            self.f.createIfcRectangleProfileDef(
                "AREA",
                None,
                self.f.createIfcAxis2Placement2D(self.f.createIfcCartesianPoint((0.0, 0.0))),
                dx * 1000,
                dy * 1000,
            ),  # a Position: IFC2X3 needs one
            self._axes((0.0, 0.0, 0.0)),
            self.f.createIfcDirection((0.0, 0.0, 1.0)),
            dz * 1000,
        )
        shape = self.f.createIfcShapeRepresentation(self.context, "Body", "SweptSolid", [solid])
        element = self._new(
            ifc_class,
            Name=attrs.pop("Name", ifc_class),
            ObjectPlacement=self._placed(x, y, z),
            Representation=self.f.createIfcProductDefinitionShape(None, None, [shape]),
            **attrs,
        )
        if ifc_class == "IfcSpace":
            self._new("IfcRelAggregates", RelatingObject=self.storey, RelatedObjects=[element])
        else:
            self.contained.append(element)
        return element

    def service(self, what: str, type_name: str, x: float, y: float, z: float, size: tuple,
                ports: list[tuple[float, float, float, str]]) -> Any:  # fmt: skip
        ifc4, generic, type_class = CLASSES[what]
        element = self.box(ifc4 if self.schema == "IFC4" else generic, x, y, z, size)
        kind = self._new(type_class, Name=type_name, PredefinedType="NOTDEFINED")
        self._new("IfcRelDefinesByType", RelatedObjects=[element], RelatingType=kind)
        for px, py, pz, flow in ports:
            port = self._new(
                "IfcDistributionPort",
                ObjectPlacement=self._placed(px, py, pz),
                FlowDirection=flow,
            )
            if self.schema == "IFC4":
                self._new("IfcRelNests", RelatingObject=element, RelatedObjects=[port])
            else:
                self._new("IfcRelConnectsPortToElement", RelatingPort=port, RelatedElement=element)
        return element

    def in_space(self, element: Any, name: str) -> None:
        """Moves `element` from the storey into a new space of this file named `name`."""
        space = self._new("IfcSpace", Name=name)
        self._new("IfcRelAggregates", RelatingObject=self.storey, RelatedObjects=[space])
        self.contained.remove(element)
        self._new(
            "IfcRelContainedInSpatialStructure", RelatingStructure=space, RelatedElements=[element]
        )

    def connect(self, a: Any, i: int, b: Any, j: int) -> None:
        import ifcopenshell.util.system as system

        pa, pb = system.get_ports(a)[i], system.get_ports(b)[j]
        self._new("IfcRelConnectsPorts", RelatingPort=pa, RelatedPort=pb)

    def pset(self, element: Any, name: str, **labels: str) -> None:
        values = [
            self.f.createIfcPropertySingleValue(key, None, self.f.createIfcLabel(value), None)
            for key, value in labels.items()
        ]
        self._new(
            "IfcRelDefinesByProperties",
            RelatedObjects=[element],
            RelatingPropertyDefinition=self._new("IfcPropertySet", Name=name, HasProperties=values),
        )

    def system(self, name: str, members: list[Any]) -> None:
        group = self._new(
            "IfcDistributionSystem" if self.schema == "IFC4" else "IfcSystem", Name=name
        )
        self._new("IfcRelAssignsToGroup", RelatedObjects=members, RelatingGroup=group)

    def save(self, path: Path) -> Path:
        self._new(
            "IfcRelContainedInSpatialStructure",
            RelatingStructure=self.storey,
            RelatedElements=self.contained,
        )
        self.f.write(str(path))
        return path


def _services(
    path: Path, schema: Schema = "IFC4", *, ports: bool = True, extra: bool = False
) -> Path:
    """A boiler in room 1 feeding two radiators (one per room) through a tee, one system."""
    m = _Ifc(schema)

    def at(*placed: tuple[float, float, float, str]) -> list[tuple[float, float, float, str]]:
        return list(placed) if ports else []

    boiler = m.service("boiler", "Boiler 24 kW", 0.5, 0.6, 0.0, (0.5, 0.4, 0.8),
                       at((0.5, 0.25, 0.15, "SOURCE")))  # fmt: skip
    tee = m.service("tee", "Tee DN20", 2.0, 0.25, 0.1, (0.1, 0.1, 0.1),
                    at((2.0, 0.25, 0.15, "SINK"), (2.0, 0.25, 0.15, "SOURCE"),
                     (2.0, 0.25, 0.15, "SOURCE")))  # fmt: skip
    rad1 = m.service("heater", "Radiator 22-600", 2.5, 0.1, 0.2, (1.0, 0.06, 0.6),
                     at((2.05, 0.1, 0.25, "SINK")))  # fmt: skip
    rad2 = m.service("heater", "Radiator 22-600", 7.5, 0.1, 0.2, (1.0, 0.06, 0.6),
                     at((7.05, 0.1, 0.25, "SINK")))  # fmt: skip
    main = m.service("pipe", "Pipe DN20", 1.25, 0.25, 0.1, (1.5, 0.02, 0.02),
                     at((0.5, 0.25, 0.15, "SINK"), (2.0, 0.25, 0.15, "SOURCE")))  # fmt: skip
    to1 = m.service("pipe", "Pipe DN15", 2.0, 0.17, 0.1, (0.02, 0.15, 0.02),
                    at((2.0, 0.25, 0.15, "SINK"), (2.05, 0.1, 0.25, "SOURCE")))  # fmt: skip
    to2 = m.service("pipe", "Pipe DN15", 4.5, 0.25, 0.1, (5.0, 0.02, 0.02),
                    at((2.0, 0.25, 0.15, "SINK"), (7.05, 0.1, 0.25, "SOURCE")))  # fmt: skip
    members = [boiler, tee, rad1, rad2, main, to1, to2]
    if ports:
        for a, i, b, j in [(boiler, 0, main, 0), (main, 1, tee, 0), (tee, 1, to1, 0),
                           (to1, 1, rad1, 0), (tee, 2, to2, 0), (to2, 1, rad2, 0)]:  # fmt: skip
            m.connect(a, i, b, j)
    if extra:
        members.append(m.service("heater", "Radiator 22-600", 4.0, 3.9, 0.2, (1.0, 0.06, 0.6), []))
    m.system("Heating Supply", members)
    m.in_space(rad2, "102")
    return m.save(path)


def _architecture(path: Path, shift: float = 0.0) -> Path:
    """Two rooms 5 x 4 m side by side, a south wall, a partition with a door, a window."""
    m = _Ifc(shift=shift)
    for name, x in (("1 Living", 2.5), ("2 Bedroom", 7.5)):
        m.box("IfcSpace", x, 2.0, 0.0, (5.0, 4.0, 2.7), Name=name)
    south = m.box("IfcWall", 5.0, -0.05, 0.0, (10.2, 0.1, 2.7), Name="south")
    partition = m.box("IfcWall", 5.0, 2.0, 0.0, (0.1, 4.0, 2.7), Name="partition")
    for host, kind, x, y, z, size in [
        (partition, "IfcDoor", 5.0, 1.95, 0.0, (0.1, 0.9, 2.1)),
        (south, "IfcWindow", 7.5, -0.05, 0.9, (1.2, 0.1, 1.2)),
    ]:
        void = m._new("IfcOpeningElement", ObjectPlacement=m._placed(x, y, z))
        m._new("IfcRelVoidsElement", RelatingBuildingElement=host, RelatedOpeningElement=void)
        filling = m.box(kind, x, y, z, size)
        m._new("IfcRelFillsElement", RelatingOpeningElement=void, RelatedBuildingElement=filling)
    return m.save(path)


def _stored(model: Any) -> dict:
    return json.loads(model.model_dump_json())


@pytest.mark.parametrize("schema", ["IFC4", "IFC2X3"])
def test_sv1_sv3_elements_ports_and_connections(tmp_path: Path, schema: Schema) -> None:
    model, _ = build_services_model(_services(tmp_path / "s.ifc", schema), {})
    kinds = sorted(e.kind for e in model.elements)
    assert kinds == ["boiler", "pipe_fitting", "pipe_segment", "pipe_segment", "pipe_segment",
                     "space_heater", "space_heater"]  # fmt: skip
    assert model.source.ifc_schema == schema and model.storeys[0].elevation_m == 3.0
    by_type = {e.type: e for e in model.elements}
    boiler = by_type["Boiler 24 kW"]
    assert boiler.discipline == "heating" and boiler.systems == ("Heating Supply",)
    assert boiler.at == pytest.approx((0.5, 0.6, 3.0)) and boiler.storey == "L1"
    assert [p.flow for p in boiler.ports] == ["source"]
    main = by_type["Pipe DN20"]
    assert [c for p in main.path or () for c in p] == pytest.approx(
        [0.5, 0.25, 3.15, 2.0, 0.25, 3.15]
    )
    radiator = next(e for e in model.elements if e.kind == "space_heater")
    assert radiator.body_m == pytest.approx((1.0, 0.06, 0.6), abs=1e-3)
    assert len(model.connections) == 6 and {c.state for c in model.connections} == {"stated"}
    owner = {p.id: e.kind for e in model.elements for p in e.ports}
    pairs = {frozenset((owner[c.a], owner[c.b])) for c in model.connections}
    assert frozenset(("boiler", "pipe_segment")) in pairs
    assert frozenset(("space_heater", "pipe_segment")) in pairs


def test_sv2_the_same_file_gives_the_same_bytes(tmp_path: Path) -> None:
    path = _services(tmp_path / "s.ifc")
    one, ids = build_services_model(path, {})
    two, again = build_services_model(path, ids)
    assert one.model_dump_json() == two.model_dump_json() and ids == again
    assert sorted(ids.values(), key=lambda i: int(i[1:])) == [f"E{n}" for n in range(1, 8)]


def test_sv2_a_re_export_keeps_every_old_id(tmp_path: Path) -> None:
    first, ids = build_services_model(_services(tmp_path / "a.ifc"), {})
    # a re-export: new GlobalIds for everything but the ones the map knows are kept by guid
    _, more = build_services_model(_services(tmp_path / "b.ifc", extra=True), dict(ids))
    assert all(more[g] == i for g, i in ids.items())
    assert set(more.values()) - set(ids.values()) == {f"E{n}" for n in range(8, 16)}
    assert {e.id for e in first.elements} == set(ids.values())


def test_sv4_connectivity(tmp_path: Path) -> None:
    model, _ = build_services_model(_services(tmp_path / "s.ifc"), {})
    assert model.connectivity.state == "connected" and model.connectivity.reason is None
    loose, _ = build_services_model(_services(tmp_path / "x.ifc", extra=True), {})
    assert loose.connectivity.state == "partial"
    assert "1 space heater" in (loose.connectivity.reason or "")
    none, _ = build_services_model(_services(tmp_path / "n.ifc", ports=False), {})
    assert none.connectivity.state == "none" and none.connections == ()


def test_sv5_rooms_walls_and_openings_from_the_building_model(tmp_path: Path) -> None:
    services = _services(tmp_path / "s.ifc")
    model, _ = build_services_model(services, {}, _architecture(tmp_path / "a.ifc"))
    assert sorted((r.name, r.id) for r in model.rooms)[0][0] == "1 Living"
    room = {r.name: r.id for r in model.rooms}
    assert sorted(room.values()) == ["SR1", "SR2"]
    assert model.rooms[0].polygon and model.source.architecture_sha256
    radiators = sorted((e.at[0], e.room) for e in model.elements if e.kind == "space_heater"
                       if e.at)  # fmt: skip
    assert [r for _, r in radiators] == [room["1 Living"], room["2 Bedroom"]]
    walls = {w.id: w for w in model.walls}
    assert len(walls) == 2 and {frozenset(w.rooms) for w in walls.values()} == {
        frozenset(("SR1", "SR2"))
    }
    door = next(o for o in model.openings if o.kind == "door")
    window = next(o for o in model.openings if o.kind == "window")
    assert door.wall in walls and door.sill_m == pytest.approx(0.0, abs=0.01)
    assert door.head_m == pytest.approx(2.1, abs=0.01) and window.sill_m == pytest.approx(0.9)
    x0, y0, x1, y1 = model.storeys[0].frame_m
    assert x0 <= -2.0 and y0 <= -2.0 and x1 >= 12.0 and y1 >= 6.0  # rooms + 2 m


def test_sv5_a_building_model_that_does_not_line_up_is_left_out(tmp_path: Path) -> None:
    services = _services(tmp_path / "s.ifc")
    model, _ = build_services_model(services, {}, _architecture(tmp_path / "a.ifc", shift=100))
    assert model.rooms == model.walls == model.openings == ()
    assert all(e.room is None for e in model.elements)


def test_sv8_the_store_builds_once_and_keeps_ids_across_versions(tmp_path: Path) -> None:
    store = ServicesStore(tmp_path / "cache")
    data = _services(tmp_path / "s.ifc").read_bytes()
    model = store.build("project/heating.ifc", data)
    assert model is not None
    sha = model.source.sha256
    stored = tmp_path / "cache" / f"{sha}.services.v1.json.gz"
    assert json.loads(gzip.decompress(stored.read_bytes())) == _stored(model)
    assert store.load(sha) == model and store.build("project/heating.ifc", data) == model
    assert not list((tmp_path / "cache").glob("*.part"))
    newer = store.build(
        "project/heating.ifc", _services(tmp_path / "t.ifc", extra=True).read_bytes()
    )
    assert newer is not None and newer.source.sha256 != sha
    assert store.load("0" * 64) is None


def test_sv8_a_file_that_is_no_ifc_has_no_model(tmp_path: Path) -> None:
    assert ServicesStore(tmp_path).build("x.ifc", b"not an ifc file") is None


@pytest.mark.parametrize("schema", ["IFC4", "IFC2X3"])
def test_sv9_facts_derived_from_the_model_equal_the_fact_sheet(
    tmp_path: Path, schema: Schema
) -> None:
    path = _services(tmp_path / "s.ifc", schema)
    model, _ = build_services_model(path, {}, _architecture(tmp_path / "a.ifc"))
    expected = mep_facts(ifcopenshell.open(str(path)))
    assert any(f.topic == "space_heater.space" for f in expected)  # the space is covered
    assert any(f.topic.startswith("system.") for f in expected)
    assert derive.facts(model) == expected
    stored = type(model).model_validate_json(model.model_dump_json())
    assert derive.facts(stored) == expected  # and from the stored JSON


def test_sv1_a_device_that_states_its_panel_keeps_its_circuit(tmp_path: Path) -> None:
    m = _Ifc()
    boiler = m.service("boiler", "Boiler 24 kW", 0.5, 0.6, 0.0, (0.5, 0.4, 0.8), [])
    pump = m.service("boiler", "Boiler 12 kW", 2.5, 0.6, 0.0, (0.5, 0.4, 0.8), [])
    m.pset(boiler, "Electrical", Panel="DB1", **{"Circuit Number": "3"})
    m.pset(pump, "Electrical", Panel="DB2")
    model, _ = build_services_model(m.save(tmp_path / "s.ifc"), {})
    circuits = {e.type: e.circuit for e in model.elements}
    assert circuits == {"Boiler 24 kW": "DB1/3", "Boiler 12 kW": "DB2"}
    assert {e.discipline for e in model.elements} == {"heating"}  # not electrical elements

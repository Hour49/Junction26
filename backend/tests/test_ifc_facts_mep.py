import itertools
from typing import Any, Literal

import ifcopenshell
import ifcopenshell.guid
import pytest

from app.adapters.ifc_model.facts_mep import mep_facts, trace_system
from app.core.ifc_facts import Fact


class _Model:
    """A synthetic model in millimetres: one storey holding one space, built with plain
    ifcopenshell entities so that both schemas take the same code."""

    def __init__(self, schema: Literal["IFC4", "IFC2X3"] = "IFC4") -> None:
        self.file: Any = ifcopenshell.file(schema=schema)
        mm = self.file.create_entity(
            "IfcSIUnit", UnitType="LENGTHUNIT", Prefix="MILLI", Name="METRE"
        )
        project = self._rooted(
            "IfcProject", UnitsInContext=self.file.create_entity("IfcUnitAssignment", [mm])
        )
        self.storey = self._rooted("IfcBuildingStorey", Name="Level 1")
        self.space = self._rooted("IfcSpace", Name="101")
        self._rooted("IfcRelAggregates", RelatingObject=project, RelatedObjects=[self.storey])
        self._rooted("IfcRelAggregates", RelatingObject=self.storey, RelatedObjects=[self.space])

    def _rooted(self, ifc_class: str, **attrs: Any) -> Any:
        return self.file.create_entity(ifc_class, GlobalId=ifcopenshell.guid.new(), **attrs)

    def add(self, ifc_class: str, name: str, inside: Any = None, **props: Any) -> Any:
        """An element contained in `inside` (the storey by default) with `props` as its
        property set "Dimensions"."""
        element = self._rooted(ifc_class, Name=name)
        self._rooted(
            "IfcRelContainedInSpatialStructure",
            RelatingStructure=inside or self.storey,
            RelatedElements=[element],
        )
        if props:
            self.pset(element, "Dimensions", **props)
        return element

    def pset(self, element: Any, set_name: str, **props: Any) -> None:
        """A float is a length in the file's unit, a str a label."""
        values = [
            self.file.create_entity(
                "IfcPropertySingleValue",
                Name=key,
                NominalValue=self.file.create_entity(
                    "IfcLengthMeasure" if isinstance(value, float) else "IfcLabel", value
                ),
            )
            for key, value in props.items()
        ]
        self._rooted(
            "IfcRelDefinesByProperties",
            RelatedObjects=[element],
            RelatingPropertyDefinition=self._rooted(
                "IfcPropertySet", Name=set_name, HasProperties=values
            ),
        )

    def typed(self, elements: list[Any], type_class: str, name: str) -> None:
        relating = self._rooted(type_class, Name=name)
        self._rooted("IfcRelDefinesByType", RelatedObjects=elements, RelatingType=relating)

    def system(self, name: str, members: list[Any]) -> None:
        group = self._rooted("IfcDistributionSystem", Name=name)
        self._rooted("IfcRelAssignsToGroup", RelatedObjects=members, RelatingGroup=group)

    def connect(self, upstream: Any, downstream: Any) -> None:
        ports = []
        for element in (upstream, downstream):
            port = self._rooted("IfcDistributionPort")
            self._rooted("IfcRelNests", RelatingObject=element, RelatedObjects=[port])
            ports.append(port)
        self._rooted("IfcRelConnectsPorts", RelatingPort=ports[0], RelatedPort=ports[1])


def _heating() -> tuple[Any, list[Any]]:
    """boiler -> pipe (DN20, 2 m) -> elbow -> pipe (DN15, 1.5 m) -> radiator, in one system;
    a third pipe outside the system."""
    built = _Model()
    chain = [
        built.add("IfcBoiler", "Boiler:B1:11"),
        built.add("IfcPipeSegment", "Pipe:Copper:12", Length=2000.0, Size="DN20"),
        built.add("IfcPipeFitting", "Elbow:Std:13"),
        built.add("IfcPipeSegment", "Pipe:Copper:14", Length=1500.0, Size="DN15"),
        built.add("IfcSpaceHeater", "Radiator:R1:15", built.space),
    ]
    built.add("IfcPipeSegment", "Pipe:Steel:16", Length=500.0)
    built.pset(chain[1], "Type_Other", Size="Size")  # Revit's placeholder for an unset value
    # listed out of order: the trace follows the ports, not the file
    built.system("Heating 1", [chain[2], *chain[:2], *chain[3:]])
    for upstream, downstream in itertools.pairwise(chain):
        built.connect(upstream, downstream)
    ports = built.file.by_type("IfcDistributionPort")
    built.system("Heating 1 ports", ports)  # an IFC4 export assigns the ports to a system too
    return built.file, chain


def _one(facts: list[Fact], topic: str, subject: str = "all", **where: object) -> Fact:
    found = [
        f
        for f in facts
        if f.topic == topic
        and f.subject == subject
        and all(getattr(f, k) == v for k, v in ({"storey": None, "system": None} | where).items())
    ]
    assert len(found) == 1, found
    return found[0]


def test_segments_are_counted_and_measured_in_metres_per_type_storey_and_system() -> None:
    facts = mep_facts(_heating()[0])
    assert _one(facts, "pipe_segment.count").value == 3
    assert _one(facts, "pipe_segment.length").value == 4.0
    assert _one(facts, "pipe_segment.length", "Pipe:Copper").value == 3.5
    assert _one(facts, "pipe_segment.length", storey="Level 1").value == 4.0
    assert _one(facts, "pipe_segment.length", system="Heating 1").value == 3.5
    assert _one(facts, "pipe_segment.size_length", "DN20", system="Heating 1").value == 2.0
    assert _one(facts, "flow_segment.count").value == 3
    assert _one(facts, "element.count").value == 6
    length = _one(facts, "pipe_segment.length")
    assert (length.unit, length.source, length.discipline) == ("m", "Dimensions.Length", "plumbing")


def test_systems_ports_and_rooms_are_facts() -> None:
    facts = mep_facts(_heating()[0])
    assert _one(facts, "system.count").value == 2
    assert (
        _one(facts, "system.element_count", "Heating 1 ports", system="Heating 1 ports").value == 0
    )
    assert _one(facts, "system.element_count", "Heating 1", system="Heating 1").value == 5
    assert _one(facts, "port.count").value == 8
    assert _one(facts, "port.connected").value == 8
    radiator = _one(facts, "space_heater.space", "Radiator:R1:15", storey="Level 1")
    assert (radiator.value, radiator.discipline) == ("101", "heating")
    assert _one(facts, "space_heater.count_in_space", "101").value == 1


def test_a_system_is_traced_from_its_source_to_its_terminals() -> None:
    file, chain = _heating()
    trace = trace_system(file, "Heating 1")
    assert trace.order == tuple(e.GlobalId for e in chain)
    assert trace.start == chain[0].GlobalId
    assert trace.terminals == (chain[-1].GlobalId,)
    assert trace.run_m_by_size == {"DN20": 2.0, "DN15": 1.5}
    assert trace.unreached == 0
    with pytest.raises(KeyError):
        trace_system(file, "Cooling")


def test_an_ifc2x3_flow_element_takes_its_kind_from_its_type_and_a_revit_name() -> None:
    built = _Model("IFC2X3")
    lights = [built.add("IfcFlowTerminal", f"Sconce:100W:100W:{n}") for n in range(2)]
    for light in lights:
        light.ObjectType = "100W"
    built.typed(lights, "IfcLightFixtureType", "100W")
    built.add("IfcBuildingElementProxy", "Toilet:Domestic:7").ObjectType = "Domestic"
    facts = mep_facts(built.file)
    assert _one(facts, "light_fixture.count", "Sconce:100W:100W").value == 2
    assert _one(facts, "flow_terminal.count").value == 2
    assert _one(facts, "building_element_proxy.count", "Toilet:Domestic").value == 1
    assert _one(facts, "building_element_proxy.count").value == 1  # its kind is its group
    assert not [f for f in facts if f.topic.startswith("port.")]


def test_totals_by_class_storey_average_and_typed_elements_are_facts() -> None:
    built = _Model()
    pvc = built.add("IfcPipeSegment", "Pipe Types:PVC Waste:1", Length=2000.0, Material="Plastic")
    copper = built.add("IfcPipeSegment", "Pipe Types:Copper Cold Water:2", Length=1000.0)
    fittings = [built.add("IfcPipeFitting", f"Fitting:{n}:3") for n in ("Bend 90", "Tee", "Bocht")]
    valve = built.add("IfcValve", "Valve:Ball Valve DN20:4")
    meter = built.add("IfcFlowMeter", "Meter:Water Meter:5")
    duct = built.add("IfcDuctSegment", "Rectangular Duct:Verzinkt:6", Length=500.0)
    sensor = built.add("IfcSensor", "Sensor:Smoke:7")
    built.add("IfcBuildingElementProxy", "Generic:8")  # no type: not in the typed total
    for element, type_class in [
        (pvc, "IfcPipeSegmentType"),
        (copper, "IfcPipeSegmentType"),
        *((f, "IfcPipeFittingType") for f in fittings),
        (valve, "IfcValveType"),
        (meter, "IfcFlowMeterType"),
        (duct, "IfcDuctSegmentType"),
        (sensor, "IfcSensorType"),
    ]:
        built.typed([element], type_class, element.Name)
        built.pset(element, "Pset_ProductRequirements", Category="Pipes")
    built.system("Heating", [pvc, copper])  # the type name says what a pipe is for, first
    facts = mep_facts(built.file)

    def value(topic: str, subject: str = "all") -> object:
        return _one(facts, topic, subject).value

    assert value("element.count", "typed") == 8
    assert value("pipe_segment.count_by_material", "plastic") == 1  # the stated material wins
    assert value("pipe_segment.count_by_material", "copper") == 1
    assert value("duct_segment.count_by_material", "galvanised steel") == 1
    assert value("duct_segment.count_by_shape", "rectangular") == 1
    assert value("pipe_segment.length_by_application", "drainage") == 2.0
    assert value("pipe_segment.with_length_by_application", "water supply") == 1
    assert value("flow_segment.length_by_material", "copper") == 1.0
    for fitting_type in ("bend", "tee", "other"):  # "bocht" is Dutch: other, as the answers do
        assert value("pipe_fitting.count_by_fitting_type", fitting_type) == 1
    assert value("pipe_fitting.count_by_fitting_type_true", "bend") == 2  # the true reading
    assert value("flow_controller.count_by_function", "shutoff") == 1
    assert value("flow_controller.count_by_function", "metering") == 1
    assert value("pipe_segment.length_mean") == 1.5
    assert value("pipe_segment.length_per_storey") == 3.0  # one storey
    assert value("category_group.count", "Pipe") == 9

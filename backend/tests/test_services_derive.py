"""SV-9: the services facts derived from the stored model equal facts_mep's on the same file,
on synthetic IFC4 and IFC2X3 files built here."""

from typing import Any, Literal

import ifcopenshell
import ifcopenshell.guid
import ifcopenshell.util.system
import pytest

from app.adapters.ifc_model import facts_mep
from app.core.services import derive

Schema = Literal["IFC4", "IFC2X3"]


class _Heating:
    """One storey in millimetres: boiler -> pump -> pipe -> tee -> two pipes -> two radiators,
    a valve on one branch, a loose proxy, one system; IFC4 classes or IFC2X3's generic ones."""

    def __init__(self, schema: Schema) -> None:
        self.schema = schema
        self.file: Any = ifcopenshell.file(schema=schema)
        mm = self.file.create_entity(
            "IfcSIUnit", UnitType="LENGTHUNIT", Prefix="MILLI", Name="METRE"
        )
        project = self._new(
            "IfcProject", UnitsInContext=self.file.create_entity("IfcUnitAssignment", [mm])
        )
        self.storeys = [self._new("IfcBuildingStorey", Name=n) for n in ("Level 0", "Level 1")]
        self.space = self._new("IfcSpace", Name="R1")
        self._new("IfcRelAggregates", RelatingObject=project, RelatedObjects=self.storeys)
        self._new("IfcRelAggregates", RelatingObject=self.storeys[0], RelatedObjects=[self.space])

    def _new(self, ifc_class: str, **attrs: Any) -> Any:
        return self.file.create_entity(ifc_class, GlobalId=ifcopenshell.guid.new(), **attrs)

    def add(self, kind: str, generic: str, name: str, storey: int = 0, **props: Any) -> Any:
        """IFC4: `kind` (IfcPipeSegment); IFC2X3: `generic` (IfcFlowSegment) typed by
        `kind`Type. `props` go in a property set: floats as lengths, str as labels."""
        ifc4 = self.schema == "IFC4"
        element = self._new(kind if ifc4 else generic, Name=name)
        inside = self.space if props.pop("in_space", False) else self.storeys[storey]
        self._new(
            "IfcRelContainedInSpatialStructure", RelatingStructure=inside, RelatedElements=[element]
        )
        type_class = f"{kind}Type"
        if kind != "IfcBuildingElementProxy":
            type_ = self._new(type_class, Name=name.split(":")[1], PredefinedType="NOTDEFINED")
            self._new("IfcRelDefinesByType", RelatedObjects=[element], RelatingType=type_)
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
        if values:
            self._new(
                "IfcRelDefinesByProperties",
                RelatedObjects=[element],
                RelatingPropertyDefinition=self._new(
                    "IfcPropertySet", Name="Dimensions", HasProperties=values
                ),
            )
        return element

    def port(self, element: Any, flow: str = "SOURCEANDSINK") -> Any:
        port = self._new("IfcDistributionPort", FlowDirection=flow)
        if self.schema == "IFC4":
            self._new("IfcRelNests", RelatingObject=element, RelatedObjects=[port])
        else:
            self._new("IfcRelConnectsPortToElement", RelatingPort=port, RelatedElement=element)
        return port

    def connect(self, a: Any, b: Any) -> None:
        self._new(
            "IfcRelConnectsPorts",
            RelatingPort=self.port(a, "SOURCE"),
            RelatedPort=self.port(b, "SINK"),
        )

    def build(self) -> Any:
        boiler = self.add(
            "IfcBoiler",
            "IfcEnergyConversionDevice",
            "Boiler:Gas:1",
            Category="Mechanical Equipment",
        )
        pump = self.add("IfcPump", "IfcFlowMovingDevice", "Pump:Inline:2")
        main = self.add(
            "IfcPipeSegment", "IfcFlowSegment", "Pipe:Copper:3", Length=2000.0, Size="DN20"
        )
        tee = self.add("IfcPipeFitting", "IfcFlowFitting", "Tee:Std:4", Category="Pipe Fittings")
        a = self.add(
            "IfcPipeSegment", "IfcFlowSegment", "Pipe:Copper:5", Length=1500.0, Size="DN15"
        )
        b = self.add("IfcPipeSegment", "IfcFlowSegment", "Pipe:PE:6", 1, Length=500.0, Size="DN15")
        valve = self.add("IfcValve", "IfcFlowController", "Valve:Ball:7")
        r1 = self.add("IfcSpaceHeater", "IfcFlowTerminal", "Radiator:R600:8", in_space=True)
        r2 = self.add("IfcSpaceHeater", "IfcFlowTerminal", "Radiator:R600:9", 1)
        self.add("IfcBuildingElementProxy", "IfcBuildingElementProxy", "Socket:Double:10")
        for x, y in ((boiler, pump), (pump, main), (main, tee), (tee, a), (a, r1), (tee, valve)):
            self.connect(x, y)
        self.connect(valve, b)
        self.connect(b, r2)
        self.port(r2)  # an open port
        group = self._new(
            "IfcDistributionSystem" if self.schema == "IFC4" else "IfcSystem",
            Name="Heating 1",
            ObjectType="Heating Supply",
        )
        members = [boiler, pump, main, tee, a, b, valve, r1, r2]
        self._new("IfcRelAssignsToGroup", RelatedObjects=members, RelatingGroup=group)
        return self.file


def stored(model: Any) -> dict[str, Any]:
    """The stored services model of `model` in the spec's JSON shape (SV-1..SV-4), built from
    facts_mep's elements. shortcut: a stand-in for slice A's builder; switch to it when in."""
    elements = facts_mep.mep_elements(model)
    entity = {e.GlobalId: e for e in model.by_type("IfcProduct")}
    storey_id = {s.Name: f"L{i}" for i, s in enumerate(model.by_type("IfcBuildingStorey"), 1)}
    port_id: dict[int, str] = {}
    docs = []
    for n, e in enumerate(elements, 1):
        ports = ifcopenshell.util.system.get_ports(entity[e.guid])
        for k, port in enumerate(ports, 1):
            port_id[port.id()] = f"E{n}.p{k}"
        docs.append(
            {
                "id": f"E{n}",
                "ref": {"guid": e.guid},
                "kind": e.kind,
                "group": e.group,
                "predefined": e.predefined,
                "type": e.type_name,
                "name": e.name,
                "category": e.category,
                "typed": e.typed,
                "systems": list(e.systems),
                "system_type": e.system_type,
                "discipline": e.discipline,
                "storey": storey_id.get(e.storey or ""),
                "space": e.space,
                "size": e.size,
                "length_m": e.length_m,
                "length_source": e.length_source,
                "classes": dict(e.classes),
                "ports": [
                    {"id": port_id[p.id()], "flow": (p.FlowDirection or "").lower() or None}
                    for p in ports
                ],
            }
        )
    systems = [s for s in model.by_type("IfcSystem") if not s.is_a("IfcZone")]
    return {
        "version": 1,
        "connectivity": {"state": "connected", "reason": None},
        "storeys": [{"id": i, "name": name} for name, i in storey_id.items()],
        "systems": [
            {
                "name": s.Name or "",
                "type": facts_mep._system_type(s),  # pyright: ignore[reportPrivateUsage]
                "element_count": len(facts_mep._members(s)),  # pyright: ignore[reportPrivateUsage]
            }
            for s in systems
        ],
        "elements": docs,
        "connections": [
            {"a": port_id[r.RelatingPort.id()], "b": port_id[r.RelatedPort.id()], "state": "stated"}
            for r in model.by_type("IfcRelConnectsPorts")
        ],
    }


@pytest.mark.parametrize("schema", ["IFC4", "IFC2X3"])
def test_sv9_derived_facts_equal_facts_mep(schema: Schema) -> None:
    model = _Heating(schema).build()
    want = facts_mep.mep_facts(model)
    got = derive.facts(stored(model))
    assert len(want) > 60  # the fixture reaches lengths, sizes, systems, ports, spaces
    assert got == want


def test_sv9_the_discipline_words_are_facts_meps() -> None:
    assert derive.DISCIPLINE_WORDS == facts_mep.DISCIPLINE_WORDS
    assert derive.CLASSES == facts_mep.CLASSES

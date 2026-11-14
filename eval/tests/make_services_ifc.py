"""Writes a small synthetic IFC4 services model (run in backend/'s environment, which has
ifcopenshell; tests/test_services_ifc.py starts it). Millimetres; two storeys, L2 3 m up.

    AHU:Big:101 (L2) -port- Duct:Rect:102 (2 m) -port- Damper:FD:103 -port- Duct:Rect:104 (3 m, L1)
    -port- Grille:G:105 (L1)
    Fan:F:106 (L1): one port, not connected.   Lamp:L:107 (L1): Panel P1, Circuit Number 3.
    System SA1 (Supply Air): the AHU's chain.

usage: make_services_ifc.py OUT.ifc
"""

# pyright: reportMissingImports=false
# (ifcopenshell lives in backend/'s environment, which runs this file)
import itertools
import sys
from typing import Any

import ifcopenshell
import ifcopenshell.guid

F: Any = ifcopenshell.file(schema="IFC4")


def rooted(ifc_class: str, **attrs: Any) -> Any:
    return F.create_entity(ifc_class, GlobalId=ifcopenshell.guid.new(), **attrs)


def pset(element: Any, name: str, **props: Any) -> None:
    values = [
        F.create_entity(
            "IfcPropertySingleValue",
            Name=key,
            NominalValue=F.create_entity(
                "IfcLengthMeasure" if isinstance(value, float) else "IfcLabel", value
            ),
        )
        for key, value in props.items()
    ]
    prop_set = rooted("IfcPropertySet", Name=name, HasProperties=values)
    rooted(
        "IfcRelDefinesByProperties", RelatedObjects=[element], RelatingPropertyDefinition=prop_set
    )


def port(element: Any) -> Any:
    p = rooted("IfcDistributionPort")
    rooted("IfcRelNests", RelatingObject=element, RelatedObjects=[p])
    return p


def main(out: str) -> None:
    mm = F.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Prefix="MILLI", Name="METRE")
    project = rooted("IfcProject", UnitsInContext=F.create_entity("IfcUnitAssignment", [mm]))
    l1 = rooted("IfcBuildingStorey", Name="L1", Elevation=0.0)
    l2 = rooted("IfcBuildingStorey", Name="L2", Elevation=3000.0)
    rooted("IfcRelAggregates", RelatingObject=project, RelatedObjects=[l1, l2])

    def add(ifc_class: str, name: str, storey: Any, **props: Any) -> Any:
        element = rooted(ifc_class, Name=name)
        rooted("IfcRelContainedInSpatialStructure", RelatingStructure=storey,
               RelatedElements=[element])  # fmt: skip
        if props:
            pset(element, "Dimensions", **props)
        return element

    chain = [
        add("IfcUnitaryEquipment", "AHU:Big:101", l2),
        add("IfcDuctSegment", "Duct:Rect:102", l2, Length=2000.0),
        add("IfcDamper", "Damper:FD:103", l2),
        add("IfcDuctSegment", "Duct:Rect:104", l1, Length=3000.0),
        add("IfcAirTerminal", "Grille:G:105", l1),
    ]
    for a, b in itertools.pairwise(chain):
        rooted("IfcRelConnectsPorts", RelatingPort=port(a), RelatedPort=port(b))
    port(add("IfcFan", "Fan:F:106", l1))
    lamp = add("IfcLightFixture", "Lamp:L:107", l1)
    pset(lamp, "Electrical", Panel="P1", **{"Circuit Number": "3"})
    system = rooted("IfcDistributionSystem", Name="SA1", ObjectType="Supply Air")
    rooted("IfcRelAssignsToGroup", RelatedObjects=chain, RelatingGroup=system)
    F.write(out)


if __name__ == "__main__":
    main(sys.argv[1])

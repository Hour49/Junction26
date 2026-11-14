"""The backend half of `stoa_eval services-gen`: runs in backend/'s environment (ifcopenshell) and
writes one IFC model's services graph as plain JSON (`services_graph_v1`), which eval's own truth
code (`stoa_eval.services`) reads. `stoa_eval` starts it; nobody needs to call it by hand.

    graph --ifc MODEL.ifc --out GRAPH.json

- Nodes: the backend's own element reader (`facts_mep.mep_elements`: kind, group, type name,
  category, storey, systems, segment length, size) plus the STEP id, the port count, the
  connected-port count and a Revit `Panel` / `Circuit Number` when a property set states one.
- Edges: raw IfcRelConnectsPorts, each port's host found here (IFC2X3 ContainedIn, IFC4 Nests),
  not through `ifcopenshell.util.system`, so the truth shares no edge code with the backend.
- Storeys with their elevation in metres; each system's type (IfcSystem ObjectType, else the
  first member's `System Type` property).
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import ifcopenshell
import ifcopenshell.util.element as uel
from app.adapters.ifc_model.facts_mep import mep_elements
from app.adapters.ifc_model.objects import _unit_scales


def _host(port: Any) -> Any | None:
    for rel in getattr(port, "ContainedIn", None) or ():  # IFC2X3 IfcRelConnectsPortToElement
        return rel.RelatedElement
    for rel in getattr(port, "Nests", None) or ():  # IFC4 IfcRelNests
        return rel.RelatingObject
    return None


def _said(props: dict[str, Any], key: str) -> str | None:
    value = props.get(key)
    # a Revit export fills unset properties with their own name ("Panel": "Panel")
    return None if value in (None, "", key) else str(value)


def graph(ifc: Path) -> dict[str, Any]:
    model = ifcopenshell.open(str(ifc))
    scale = _unit_scales(model)["LENGTHUNIT"]
    ports, connected = {}, set()
    for port in model.by_type("IfcDistributionPort"):
        host = _host(port)
        ports[port.id()] = None if host is None else host.GlobalId
    edges = []
    for rel in model.by_type("IfcRelConnectsPorts"):
        a, b = rel.RelatingPort.id(), rel.RelatedPort.id()
        connected |= {a, b}
        ha, hb = ports.get(a), ports.get(b)
        if ha and hb and ha != hb:
            edges.append((ha, hb))
    nports: dict[str, int] = {}
    nconn: dict[str, int] = {}
    for pid, host in ports.items():
        if host:
            nports[host] = nports.get(host, 0) + 1
            nconn[host] = nconn.get(host, 0) + (pid in connected)
    types = {s.Name: s.ObjectType for s in model.by_type("IfcSystem") if s.Name}
    nodes = []
    for e in mep_elements(model):
        entity = model.by_guid(e.guid)
        panel = circuit = None
        for props in uel.get_psets(entity).values():
            panel = panel or _said(props, "Panel")
            circuit = circuit or _said(props, "Circuit Number")
        for name in e.systems:
            types.setdefault(name, e.system_type)
        nodes.append({
            "guid": e.guid, "step": entity.id(), "name": e.name, "type_name": e.type_name,
            "kind": e.kind, "group": e.group, "category": e.category, "storey": e.storey,
            "length_m": e.length_m, "size": e.size, "ports": nports.get(e.guid, 0),
            "connected": nconn.get(e.guid, 0), "panel": panel, "circuit": circuit,
            "systems": list(e.systems),
        })  # fmt: skip
    storeys = [
        {"name": s.Name, "elevation": None if s.Elevation is None else s.Elevation * scale}
        for s in model.by_type("IfcBuildingStorey")
        if s.Name
    ]
    return {
        "schema": "services_graph_v1", "model": ifc.stem, "storeys": storeys, "nodes": nodes,
        "edges": edges, "system_types": types,
    }  # fmt: skip


def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="services_backend.py")
    commands = parser.add_subparsers(dest="command", required=True)
    one = commands.add_parser("graph", help="one IFC model's services graph as JSON")
    one.add_argument("--ifc", type=Path, required=True)
    one.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(graph(args.ifc)), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1:])

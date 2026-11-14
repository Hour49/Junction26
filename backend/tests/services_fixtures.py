"""A small services model for the services tests (docs/specs/backend/services-model.md section 7).

`two_rooms()`, one storey L1 (elevation 0), plan in metres:

    y=4  +-----------SW2-----------+-----------SW2-----------+
         |                         |                         |
         SW3        SR1           SW5 (door SO1,             SW4
         |   boiler E1             |  y 1.5..2.4) SR2        |
    y=0  +---[E2 radiator]----SW1--+---[E3 radiator]---------+
         x=0                      x=5                       x=10

- E1 boiler at (0.5, 0.6), feeds system "Heating Supply" (E1.p1) and takes "Heating Return" (E1.p2).
- Supply main along the south wall (y 0.25, z 0.15): E8 boiler -> tee E4 (x 2.05), E9 E4 -> tee E5
  (x 7.05); branches E10 E4 -> radiator E2, E11 E5 -> radiator E3. E5.p3 is a capped end.
- Return main (y 0.31): branches E12 E2 -> tee E6 (x 2.95), E13 E3 -> tee E7 (x 7.95); E14 E7 ->
  E6, E15 E6 -> boiler. E7.p3 is a capped end.
- Radiators E2 (SR1) and E3 (SR2): 1.0 x 0.06 x 0.6 m, centre 0.1 m off the south wall, z 0.5.
Every port states its flow (an element's SOURCE port is where water leaves it). Fully connected.
"""

import math
from typing import Any

from app.core.services.stored import Point3, ServicesModel

SUPPLY, RETURN = "Heating Supply", "Heating Return"
Y_SUPPLY, Y_RETURN, Z_MAIN = 0.25, 0.31, 0.15


def _ports(eid: str, *ports: tuple[Point3, str | None]) -> list[dict[str, Any]]:
    return [{"id": f"{eid}.p{k}", "at": at, "flow": flow} for k, (at, flow) in enumerate(ports, 1)]


def _element(eid: str, kind: str, group: str, type_: str, system: str, **fields: Any) -> dict:
    return {
        "id": eid,
        "ref": {"guid": f"guid-{eid}"},
        "kind": kind,
        "group": group,
        "type": type_,
        "label": type_,
        "typed": True,
        "systems": [system] if system else [],
        "system_type": "Hydronic Supply" if system == SUPPLY else "Hydronic Return",
        "discipline": "heating",
        "storey": "L1",
        **fields,
    }


def _segment(eid: str, system: str, size: str, a: Point3, b: Point3, room: str) -> dict:
    return _element(
        eid,
        "pipe_segment",
        "flow_segment",
        f"Pipe {size}",
        system,
        room=room,
        size=size,
        length_m=round(math.dist(a, b), 4),
        at=a,
        path=[a, b],
        ports=_ports(eid, (a, "sink"), (b, "source")),
    )


def _tee(eid: str, system: str, at: Point3, flows: tuple[str, str, str], room: str) -> dict:
    return _element(
        eid,
        "pipe_fitting",
        "flow_fitting",
        "Tee DN20",
        system,
        room=room,
        at=at,
        ports=_ports(eid, *((at, flow) for flow in flows)),
    )


def _radiator(eid: str, x: float, room: str) -> dict:
    return {
        **_element(
            eid,
            "space_heater",
            "flow_terminal",
            "Radiator 22-600",
            "",
            room=room,
            at=(x, 0.1, 0.5),
            body_m=(1.0, 0.06, 0.6),
            ports=_ports(eid, ((x - 0.45, 0.1, 0.25), "sink"), ((x + 0.45, 0.1, 0.25), "source")),
        ),
        "systems": [SUPPLY, RETURN],
        "system_type": None,
    }


def _square(x0: float, y0: float, x1: float, y1: float) -> list[list[float]]:
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def two_rooms() -> ServicesModel:
    boiler_out, boiler_in = (0.4, Y_SUPPLY, Z_MAIN), (0.6, Y_RETURN, Z_MAIN)
    t1, t2 = (2.05, Y_SUPPLY, Z_MAIN), (7.05, Y_SUPPLY, Z_MAIN)
    t3, t4 = (2.95, Y_RETURN, Z_MAIN), (7.95, Y_RETURN, Z_MAIN)
    boiler = {
        **_element(
            "E1",
            "boiler",
            "energy_conversion_device",
            "Boiler 24 kW",
            "",
            room="SR1",
            at=(0.5, 0.6, 0.5),
            body_m=(0.5, 0.4, 0.8),
            ports=_ports("E1", (boiler_out, "source"), (boiler_in, "sink")),
        ),
        "systems": [SUPPLY, RETURN],
        "system_type": None,
    }
    elements = [
        boiler,
        _radiator("E2", 2.5, "SR1"),
        _radiator("E3", 7.5, "SR2"),
        _tee("E4", SUPPLY, t1, ("sink", "source", "source"), "SR1"),
        _tee("E5", SUPPLY, t2, ("sink", "source", "source"), "SR2"),
        _tee("E6", RETURN, t3, ("sink", "sink", "source"), "SR1"),
        _tee("E7", RETURN, t4, ("sink", "source", "sink"), "SR2"),
        _segment("E8", SUPPLY, "DN20", boiler_out, t1, "SR1"),
        _segment("E9", SUPPLY, "DN20", t1, t2, "SR1"),
        _segment("E10", SUPPLY, "DN15", t1, (2.05, 0.1, 0.25), "SR1"),
        _segment("E11", SUPPLY, "DN15", t2, (7.05, 0.1, 0.25), "SR2"),
        _segment("E12", RETURN, "DN15", (2.95, 0.1, 0.25), t3, "SR1"),
        _segment("E13", RETURN, "DN15", (7.95, 0.1, 0.25), t4, "SR2"),
        _segment("E14", RETURN, "DN20", t4, t3, "SR1"),
        _segment("E15", RETURN, "DN20", t3, boiler_in, "SR1"),
    ]
    joins = [
        ("E1.p1", "E8.p1"),
        ("E8.p2", "E4.p1"),
        ("E4.p2", "E9.p1"),
        ("E4.p3", "E10.p1"),
        ("E10.p2", "E2.p1"),
        ("E9.p2", "E5.p1"),
        ("E5.p2", "E11.p1"),
        ("E11.p2", "E3.p1"),
        ("E2.p2", "E12.p1"),
        ("E12.p2", "E6.p1"),
        ("E3.p2", "E13.p1"),
        ("E13.p2", "E7.p1"),
        ("E7.p2", "E14.p1"),
        ("E14.p2", "E6.p2"),
        ("E6.p3", "E15.p1"),
        ("E15.p2", "E1.p2"),
    ]
    return ServicesModel.model_validate(
        {
            "source": {"kind": "ifc", "sha256": "f" * 64, "schema": "IFC4"},
            "connectivity": {"state": "connected"},
            "storeys": [
                {"id": "L1", "name": "Level 1", "elevation_m": 0.0, "frame_m": [-2, -2, 12, 6]}
            ],
            "elements": elements,
            "connections": [{"a": a, "b": b, "state": "stated"} for a, b in joins],
            "rooms": [
                {
                    "id": "SR1",
                    "ref": {"guid": "guid-SR1"},
                    "name": "1 Living",
                    "storey": "L1",
                    "polygon": _square(0, 0, 5, 4),
                },
                {
                    "id": "SR2",
                    "ref": {"guid": "guid-SR2"},
                    "name": "2 Bedroom",
                    "storey": "L1",
                    "polygon": _square(5, 0, 10, 4),
                },
            ],
            "walls": [
                _wall("SW1", _square(-0.1, -0.1, 10.1, 0), ["SR1", "SR2"]),
                _wall("SW2", _square(-0.1, 4, 10.1, 4.1), ["SR1", "SR2"]),
                _wall("SW3", _square(-0.1, 0, 0, 4), ["SR1"]),
                _wall("SW4", _square(10, 0, 10.1, 4), ["SR2"]),
                _wall("SW5", _square(4.95, 0, 5.05, 4), ["SR1", "SR2"]),
            ],
            "openings": [
                {
                    "id": "SO1",
                    "ref": {"guid": "guid-SO1"},
                    "kind": "door",
                    "storey": "L1",
                    "wall": "SW5",
                    "segment": [[5.0, 1.5], [5.0, 2.4]],
                    "sill_m": 0.0,
                    "head_m": 2.1,
                },
            ],
        }
    )


def _wall(wid: str, polygon: list[list[float]], rooms: list[str]) -> dict:
    return {"id": wid, "ref": {"guid": f"guid-{wid}"}, "storey": "L1", "polygon": polygon,
            "rooms": rooms}  # fmt: skip

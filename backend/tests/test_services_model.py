"""The stored services model's schema (docs/specs/backend/services-model.md section 1)."""

import json
import math

import pytest
from pydantic import ValidationError

from app.core.services.stored import ServicesModel, fraction
from tests.services_fixtures import two_rooms


def test_sv1_the_fixture_round_trips_through_its_json() -> None:
    model = two_rooms()
    text = model.model_dump_json()
    assert ServicesModel.model_validate_json(text) == model
    stored = json.loads(text)
    assert stored["version"] == 1 and stored["source"]["schema"] == "IFC4"  # the spec's names
    assert {e["kind"] for e in stored["elements"]} >= {"boiler", "space_heater", "pipe_segment"}


def test_sv1_every_port_and_connection_names_an_element_of_the_model() -> None:
    model = two_rooms()
    ports = {p.id for e in model.elements for p in e.ports}
    assert all(p.id.startswith(f"{e.id}.p") for e in model.elements for p in e.ports)
    assert all(c.a in ports and c.b in ports for c in model.connections)
    assert all(len(e.path or ()) >= 2 for e in model.elements if e.group == "flow_segment")


def test_sv2_ids_have_their_prefixes() -> None:
    model = two_rooms()
    prefixes = [
        ("E", [e.id for e in model.elements]),
        ("L", [s.id for s in model.storeys]),
        ("SR", [r.id for r in model.rooms]),
        ("SW", [w.id for w in model.walls]),
        ("SO", [o.id for o in model.openings]),
    ]
    for prefix, ids in prefixes:
        assert ids and all(i.startswith(prefix) and i[len(prefix) :].isdigit() for i in ids)
        assert len(set(ids)) == len(ids)


def test_sv2_an_unknown_field_is_refused() -> None:
    stored = json.loads(two_rooms().model_dump_json())
    stored["elements"][0]["colour"] = "red"
    with pytest.raises(ValidationError):
        ServicesModel.model_validate(stored)


def test_sv6_page_fractions_come_from_the_storey_frame() -> None:
    storey = two_rooms().storeys[0]
    x0, y0, x1, y1 = storey.frame_m
    assert fraction(storey, (x0, y1)) == (0.0, 0.0)  # top left
    assert fraction(storey, (x1, y0, 3.0)) == (1.0, 1.0)  # z is ignored
    assert fraction(storey, ((x0 + x1) / 2, (y0 + y1) / 2)) == (0.5, 0.5)


def test_sv7_a_model_from_a_picture_has_no_ports_and_no_network() -> None:
    model = ServicesModel.model_validate(
        {
            "source": {"kind": "picture", "sha256": "0" * 64},
            "connectivity": {
                "state": "none",
                "reason": "a picture does not show which runs are joined",
            },
            "storeys": [{"id": "L1", "name": "1", "elevation_m": 0.0, "frame_m": [0, 0, 10, 8]}],
            "elements": [
                {
                    "id": "E1",
                    "ref": {"page": 1, "box": [0.1, 0.1, 0.2, 0.2], "reader": "vlm"},
                    "kind": "space_heater",
                    "group": "flow_terminal",
                    "type": "Radiator",
                    "label": "Radiator",
                    "discipline": "heating",
                    "storey": "L1",
                    "at": [2.0, 3.0],
                },
                {
                    "id": "E2",
                    "ref": {"page": 1, "box": [0.1, 0.3, 0.6, 0.32], "reader": "mask"},
                    "kind": "pipe_segment",
                    "group": "flow_segment",
                    "type": "heating pipe",
                    "label": "heating pipe",
                    "discipline": "heating",
                    "storey": "L1",
                    "length_m": 4.0,
                    "path": [[1.0, 1.0], [5.0, 1.0]],
                },
            ],
        }
    )
    assert model.connections == () and all(e.ports == () for e in model.elements)
    assert model.rooms == model.walls == model.openings == ()


def test_sv4_the_fixture_is_one_connected_network() -> None:
    model = two_rooms()
    owner = {p.id: e.id for e in model.elements for p in e.ports}
    near: dict[str, set[str]] = {e.id: set() for e in model.elements}
    for c in model.connections:
        near[owner[c.a]].add(owner[c.b])
        near[owner[c.b]].add(owner[c.a])
    seen, todo = {"E1"}, ["E1"]
    while todo:
        for n in near[todo.pop()] - seen:
            seen.add(n)
            todo.append(n)
    assert seen == set(near) and model.connectivity.state == "connected"
    for e in model.elements:
        if e.path:
            assert e.length_m == pytest.approx(math.dist(e.path[0], e.path[-1]), abs=1e-3)

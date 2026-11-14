"""The services-question generator and scorer (research slice 5) on a hand-written graph whose
answers are traced by hand in the comments."""

from typing import Any

import pytest

from stoa_eval import services
from stoa_eval.services import Net, ServicesAnswer, ServicesGraph, generate, score


def _node(guid: str, kind: str, group: str, type_name: str, storey: str, **kw: Any) -> dict:
    return {
        "guid": guid, "step": 1, "name": type_name, "type_name": type_name, "kind": kind,
        "group": group, "category": kw.pop("category", None), "storey": storey,
        "length_m": kw.pop("length_m", None), "size": None, "ports": kw.pop("ports", 2),
        "connected": kw.pop("connected", 2), "panel": kw.pop("panel", None),
        "circuit": kw.pop("circuit", None), "systems": kw.pop("systems", ["SA1"]),
    }  # fmt: skip


SEG, FIT, TERM, CTL = "flow_segment", "flow_fitting", "flow_terminal", "flow_controller"


def _graph(edges: bool = True, panel: str | None = "P1") -> ServicesGraph:
    """ahu -d1(2 m)- f1 -dmp- d2(3 m) - t1 (L1)        L2 is the top floor (3 m up)
                     f1 -d3(1 m)- t2 (L2)
                     f1 -open(1.5 m, one port free)
    fan: equipment, ports but none connected. d4 - t3: a network with no equipment.
    lamp: on panel P1 circuit 3."""
    nodes = [
        _node("ahu", "unitary_equipment", "energy_conversion_device", "AHU:Big:101", "L2"),
        _node("d1", "duct_segment", SEG, "Duct:Rect:102", "L2", length_m=2.0,
              systems=["SA1", "MIX"]),
        _node("f1", "duct_fitting", FIT, "Tee:T:103", "L2", ports=4, connected=4),
        _node("dmp", "damper", CTL, "Damper:FD:104", "L2"),
        _node("d2", "duct_segment", SEG, "Duct:Rect:105", "L1", length_m=3.0,
              systems=["SA1", "MIX"]),
        _node("t1", "air_terminal", TERM, "Grille:G:106", "L1", ports=1, connected=1),
        _node("d3", "duct_segment", SEG, "Duct:Rect:107", "L2", length_m=1.0),
        _node("t2", "air_terminal", TERM, "Grille:G:108", "L2", ports=1, connected=1),
        _node("open", "duct_segment", SEG, "Duct:Rect:110", "L2", length_m=1.5, connected=1),
        _node("fan", "fan", "flow_moving_device", "Fan:F:109", "L1", connected=0, systems=[]),
        _node("d4", "duct_segment", SEG, "Duct:Round:111", "L1", length_m=0.5, systems=["EA9"]),
        _node("t3", "air_terminal", TERM, "Valve:V:112", "L1", ports=1, connected=1,
              systems=["EA9"]),
        _node("lamp", "light_fixture", TERM, "Lamp:L:113", "L1", ports=0, connected=0,
              panel=panel, circuit=panel and "3", systems=[]),
    ]  # fmt: skip
    pairs = [("ahu", "d1"), ("d1", "f1"), ("f1", "dmp"), ("dmp", "d2"), ("d2", "t1"),
             ("f1", "d3"), ("d3", "t2"), ("f1", "open"), ("d4", "t3")]  # fmt: skip
    return ServicesGraph.model_validate({
        "schema": "services_graph_v1", "model": "tower_ventilation",
        "storeys": [{"name": "L1", "elevation": 0.0}, {"name": "L2", "elevation": 3.0}],
        "nodes": nodes, "edges": pairs if edges else [],
        "system_types": {
            "SA1": "Supply Air", "EA9": "Exhaust Air", "MIX": "Supply Air,Exhaust Air"
        },
    })  # fmt: skip


def _g(net: Net, rid: int) -> str:
    return next(guid for guid in net.nodes if net.rid(guid) == rid)


def test_the_truth_operations_match_the_hand_trace() -> None:
    net = Net(_graph())
    assert net.trace("ahu") == 8  # everything on the ahu's network but itself
    assert net.terminals_served("ahu") == 2
    assert net.run_length("ahu") == 7.5  # 2 + 3 + 1 + 1.5
    assert net.run_length(system="SA1") == 7.5
    # weights: half of each end's length; t1 at 1 + 1 + 0 + 1.5 + 1.5 = 5.0, t2 at 3.0
    assert net.farthest_terminal("ahu") == 106
    assert net.feeds("t1") == (101, 1)
    assert net.controllers_between("t1", "t2") == ([104], 5, True)
    assert net.cut_off("dmp", "ahu") == 2  # d2 and t1
    assert net.dead_ends("SA1") == 1  # open
    assert net.unconnected("fan", "L1") == 1
    assert net.unconnected("fan", "L2") == 0
    assert net.system_storeys("SA1") == 2
    # MIX (both types, on L1 and L2) counts for each of its types; a part of a word never matches
    assert net.systems_crossing_storeys("supply air") == 2
    assert net.systems_crossing_storeys("Exhaust Air") == 1
    assert net.systems_crossing_storeys("Supply") == 0
    assert net.circuit_of("lamp") == "P1/3"
    assert net.circuit_of("t1") is None
    assert _g(net, 109) == "fan"


def test_descriptive_anchors_resolve_to_exactly_one_element() -> None:
    net = Net(_graph())
    assert net.describe("ahu") == ("AHU on the top floor", {"family": "AHU", "top": True})
    assert net.describe("fan") == ("Fan on L1", {"family": "Fan", "storey": "L1"})
    # two Duct families on L2: no storey description; the system names no single one either
    assert net.describe("d1") is None
    for guid in net.nodes:
        described = net.describe(guid)
        if described is not None:
            assert net.resolve(described[1]) == [guid]


def test_the_generator_asks_every_answerable_template_with_its_truth() -> None:
    rows = generate(_graph(), "dev")
    assert len({r.id for r in rows}) == len(rows)
    first = {(r.template, r.anchor): r for r in rows if r.answerable and r.phrasing_set == "s1"}
    assert first["terminals_served", "id"].truth == 2
    assert (
        first["terminals_served", "id"].text
        == "How many terminals does the AHU (Revit id 101) serve?"
    )
    assert first["terminals_served", "descriptive"].text == (
        "How many terminals does the AHU on the top floor serve?"
    )
    assert first["farthest_terminal", "id"].truth == 106
    assert first["controllers_between", "id"].truth == [104]
    assert ("cut_off", "id") not in first  # no meter in this graph
    assert first["run_length_system", "none"].truth in (7.5, 0.5, 5.0)
    assert first["circuit_of", "id"].truth == "P1/3"
    per_question: dict[str, set[str]] = {}
    for r in rows:
        per_question.setdefault(r.id.rsplit("-", 1)[0], set()).add(r.phrasing_set)
    assert all(sets == {"s1", "s2", "h1", "h2"} for sets in per_question.values())
    assert all(r.split == "dev" and r.building == "tower" for r in rows)


def test_broken_connectivity_and_missing_data_become_refusals_with_a_reason() -> None:
    rows = [r for r in generate(_graph(), "dev") if not r.answerable]
    reasons = {(r.template, r.reason) for r in rows}
    assert ("terminals_served", "unconnected") in reasons  # the fan: ports, none connected
    assert ("feeds", "no_source") in reasons  # t3: its network holds no equipment
    assert all(r.truth is None for r in rows)
    bare = {(r.template, r.reason) for r in generate(_graph(edges=False, panel=None), "dev")
            if not r.answerable}  # fmt: skip
    assert ("terminals_served", "no_connectivity") in bare
    assert ("feeds", "no_connectivity") in bare
    assert ("circuit_of", "no_circuit_data") in bare


def test_the_building_and_its_split_come_from_the_manifest() -> None:
    manifest = {"dev": ["tower"], "heldout": ["hub"]}
    assert services.building_of("tower_ventilation") == "tower"
    assert services.building_of("north_wing_heating") == "north_wing"
    assert services.split_of("tower_ventilation", manifest) == "dev"
    with pytest.raises(ValueError, match="manifest"):
        services.split_of("other_mep", manifest)


def _oracle(rows: list[services.ServicesQuestion]) -> list[ServicesAnswer]:
    return [
        ServicesAnswer(id=r.id, value=r.truth, refused=not r.answerable, reason=r.reason)
        for r in rows
    ]


def test_the_oracle_scores_everything_and_the_report_holds_no_names() -> None:
    rows = generate(_graph(), "dev")
    report = score(rows, _oracle(rows))
    assert report["overall"]["right"] == report["overall"]["n"] == len(rows)
    assert report["refusal"]["reason_right"] == report["refusal"]["refused"]
    assert set(report["by"]) == {"template", "anchor", "phrasing", "hops", "answerable"}
    assert "tower" not in str(report) and "AHU" not in str(report)


def test_a_wrong_value_a_false_refusal_and_a_missing_answer_are_wrong() -> None:
    rows = [r for r in generate(_graph(), "dev") if r.phrasing_set == "s1"]
    length = next(r for r in rows if r.template == "run_length_source" and r.anchor == "id")
    served = next(r for r in rows if r.template == "terminals_served" and r.anchor == "id")
    refuse = next(r for r in rows if not r.answerable)
    answers = [
        ServicesAnswer(id=length.id, value=7.6),  # within 2 %
        ServicesAnswer(id=served.id, refused=True, reason="unconnected"),  # false refusal
        ServicesAnswer(id=refuse.id, refused=True, reason="something_else"),
    ]
    report = score([length, served, refuse], answers)
    assert report["overall"] == {"n": 3, "right": 2, "rate": 2 / 3}
    assert report["refusal"] == {
        "unanswerable": 1, "refused": 1, "reason_right": 0, "false_refusals": 1
    }  # fmt: skip
    assert score([length], [])["overall"]["right"] == 0
    assert score([length], [ServicesAnswer(id=length.id, value="7.5 m")])["overall"]["right"] == 0
    assert score([served], [ServicesAnswer(id=served.id, value="2")])["overall"]["right"] == 1

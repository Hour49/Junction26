"""The services-question generator and scorer (research slice 5) on a hand-written graph whose
answers are traced by hand in the comments."""

from typing import Any

import pytest

from stoa_eval import services
from stoa_eval.services import Net, ServicesAnswer, ServicesGraph, generate, score


def _node(guid: str, kind: str, group: str, type_name: str, storey: str, **kw: Any) -> dict:
    ports = kw.pop("ports", 2)
    return {
        "guid": guid, "step": 1, "name": type_name, "type_name": type_name, "kind": kind,
        "group": group, "category": kw.pop("category", None), "storey": storey,
        "length_m": kw.pop("length_m", None), "size": None, "ports": ports,
        "connected": kw.pop("connected", ports), "directed": kw.pop("directed", ports),
        "sinks": kw.pop("sinks", 1 if ports else 0),
        "panel": kw.pop("panel", None), "circuit": kw.pop("circuit", None),
        "systems": kw.pop("systems", ["SA1"]),
    }  # fmt: skip


SEG, FIT, TERM, CTL = "flow_segment", "flow_fitting", "flow_terminal", "flow_controller"
HEAT, MOVE, STORE = "energy_conversion_device", "flow_moving_device", "flow_storage_device"


def _graph(edges: bool = True, panel: str | None = "P1") -> ServicesGraph:
    """SA1, flow stated on 22 of its 24 ports, L2 the top floor (3 m up):
        ahu -> d1(2 m) -> bst (inline fan) -> f1 -> dmp -> d2(3 m) -> t1 (L1)
                                              f1 -> d3(1 m) -> v3 - t2 (v3's outlet and t2's
                                                                       port state no direction)
                                              f1 -> v2 -> open(1.5 m, its outlet open)
    HW1: blr - pmp (touching: one unit) - s5(2 m) - rad.
    DHW1: cyl (hot-water cylinder) - s6(1 m) - cp (pump) - s7(1 m) - tap.
    CW1: ctank (cold tank) - s8(1 m) - p3 (pump) - s9(1 m) - wc: no heat source.
    EA9, no flow stated: d4 - v9 (valve) - t3, a network with no equipment.
    fan: equipment with ports, none connected. lamp: panel P1 circuit 3; sw: "<unnamed>"."""
    nodes = [
        _node("ahu", "unitary_equipment", HEAT, "AHU:Big:101", "L2"),
        _node("d1", "duct_segment", SEG, "Duct:Rect:102", "L2", length_m=2.0,
              systems=["SA1", "MIX"]),
        _node("bst", "fan", MOVE, "Booster:B:114", "L2"),
        _node("f1", "duct_fitting", FIT, "Tee:T:103", "L2", ports=4),
        _node("dmp", "damper", CTL, "Damper:FD:104", "L2"),
        _node("d2", "duct_segment", SEG, "Duct:Rect:105", "L1", length_m=3.0,
              systems=["SA1", "MIX"]),
        _node("t1", "air_terminal", TERM, "Grille:G:106", "L1", ports=1),
        _node("d3", "duct_segment", SEG, "Duct:Rect:107", "L2", length_m=1.0),
        _node("v3", "valve", CTL, "Valve:Term:118", "L2", directed=1),
        _node("t2", "air_terminal", TERM, "Grille:G:108", "L2", ports=1, directed=0, sinks=0),
        _node("v2", "valve", CTL, "Valve:Branch:117", "L2"),
        _node("open", "duct_segment", SEG, "Duct:Rect:110", "L2", length_m=1.5, connected=1),
        _node("fan", "fan", MOVE, "Fan:F:109", "L1", connected=0, systems=[]),
        _node("blr", "boiler", HEAT, "Boiler:B:120", "L1", systems=["HW1"]),
        _node("pmp", "pump", MOVE, "Pump:P:121", "L1", systems=["HW1"]),
        _node("s5", "pipe_segment", SEG, "Pipe:Cu:122", "L1", length_m=2.0, systems=["HW1"]),
        _node("rad", "space_heater", TERM, "Radiator:R:123", "L1", ports=1, systems=["HW1"]),
        _node("cyl", "tank", STORE, "Hot Water Heater:Cyl:130", "L1", ports=1,
              systems=["DHW1"]),
        _node("s6", "pipe_segment", SEG, "Pipe:Cu:131", "L1", length_m=1.0, systems=["DHW1"]),
        _node("cp", "pump", MOVE, "Pump:Circ:132", "L1", systems=["DHW1"]),
        _node("s7", "pipe_segment", SEG, "Pipe:Cu:133", "L1", length_m=1.0, systems=["DHW1"]),
        _node("tap", "sanitary_terminal", TERM, "Tap:T:134", "L1", ports=1, systems=["DHW1"]),
        _node("ctank", "tank", STORE, "Cold Tank:T:135", "L1", ports=1, systems=["CW1"]),
        _node("s8", "pipe_segment", SEG, "Pipe:PVC:136", "L1", length_m=1.0, systems=["CW1"]),
        _node("p3", "pump", MOVE, "Pump:Boost:138", "L1", systems=["CW1"]),
        _node("s9", "pipe_segment", SEG, "Pipe:PVC:139", "L1", length_m=1.0, systems=["CW1"]),
        _node("wc", "sanitary_terminal", TERM, "WC:W:137", "L1", ports=1, systems=["CW1"]),
        _node("d4", "duct_segment", SEG, "Duct:Round:111", "L1", length_m=0.5, directed=0,
              systems=["EA9"]),
        _node("v9", "valve", CTL, "Valve:Shut:115", "L1", directed=0, systems=["EA9"]),
        _node("t3", "air_terminal", TERM, "Valve:V:112", "L1", ports=1, directed=0,
              systems=["EA9"]),
        _node("lamp", "light_fixture", TERM, "Lamp:L:113", "L1", ports=0, panel=panel,
              circuit=panel and "3", systems=[]),
        _node("sw", "switching_device", TERM, "Switch:S:116", "L1", ports=0,
              circuit="<unnamed>", systems=[]),
    ]  # fmt: skip
    flow = [("ahu", "d1"), ("d1", "bst"), ("bst", "f1"), ("f1", "dmp"), ("dmp", "d2"),
            ("d2", "t1"), ("f1", "d3"), ("d3", "v3"), ("f1", "v2"), ("v2", "open")]  # fmt: skip
    pairs = [*flow, ("v3", "t2"), ("blr", "pmp"), ("pmp", "s5"), ("s5", "rad"), ("cyl", "s6"),
             ("s6", "cp"), ("cp", "s7"), ("s7", "tap"), ("ctank", "s8"), ("s8", "p3"), ("p3", "s9"),
             ("s9", "wc"), ("d4", "v9"), ("v9", "t3")]  # fmt: skip
    return ServicesGraph.model_validate({
        "schema": "services_graph_v3", "model": "tower_ventilation",
        "storeys": [{"name": "L1", "elevation": 0.0}, {"name": "L2", "elevation": 3.0}],
        "nodes": nodes, "edges": pairs if edges else [], "flow": flow if edges else [],
        "system_types": {
            "SA1": "Supply Air", "EA9": "Exhaust Air", "MIX": "Supply Air,Exhaust Air",
            "HW1": "Heating", "DHW1": "Domestic Hot Water", "CW1": "Domestic Cold Water",
        },
    })  # fmt: skip


def _g(net: Net, rid: int) -> str:
    return next(guid for guid in net.nodes if net.rid(guid) == rid)


def test_the_truth_operations_match_the_hand_trace() -> None:
    net = Net(_graph())
    # the walk passes the inline booster fan and counts it: d1 bst f1 dmp d2 t1 d3 v3 t2 v2 open
    assert net.trace("ahu") == 11
    assert net.terminals_served("ahu") == 2
    assert net.run_length("ahu") == 7.5  # 2 + 3 + 1 + 1.5
    assert net.run_length(system="SA1") == 7.5
    # from the booster: the ahu is reached and counted, not passed
    assert net.trace("bst") == 11
    # metres entered on the way: t1 at 2 + 3 = 5.0, t2 at 2 + 1 = 3.0
    assert net.farthest_terminal("ahu") == 106
    assert net.controllers_between("t1", "t2") == ([104, 118], 6, True)  # t1 d2 dmp f1 d3 v3 t2
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
    assert net.circuit_of("sw") is None  # no panel, a placeholder circuit
    assert _g(net, 109) == "fan"


def test_feeds_is_the_set_of_units_reached_with_heat_or_air_sources_first() -> None:
    net = Net(_graph())
    assert net.feeds("t1") == [101]  # the booster fan is passed; the ahu is an air source
    assert net.feeds("rad") == [120, 121]  # boiler and pump touch: one unit, both pieces
    assert net.trace("pmp") == 2 and net.terminals_served("blr") == 1  # the unit walks as one
    assert net.feeds("tap") == [130]  # the cylinder heats, so the circulation pump drops out
    assert net.feeds("wc") == [135, 138]  # no heat source: every unit reached
    assert net.heats("cyl") and not net.heats("ctank") and not net.heats("cp")
    assert net.feeds("t3") is None  # its network has no equipment


def test_cut_off_follows_the_stated_flow_and_needs_it_on_90_percent_of_ports() -> None:
    net = Net(_graph())
    assert net.flow_stated("dmp")  # SA1: 22 of 24 ports state a direction, 92 %
    assert net.cut_off("dmp") == (2, None)  # d2 and t1, every outlet feeding a stated inlet
    assert net.cut_off("v9") == (None, "no_flow")  # EA9 states no direction
    # v2's branch ends in an open outlet; v3's outlet to t2 states no direction: neither the
    # model nor the truth can say what lies beyond
    assert net.cut_off("v2") == (None, "downstream_unknown")
    assert net.cut_off("v3") == (None, "downstream_unknown")


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
    asked = {
        (r.template, r.anchor, next(iter(r.args.values()))): r
        for r in rows
        if r.answerable and r.phrasing_set == "s1"
    }
    assert asked["terminals_served", "id", 101].truth == 2
    assert asked["terminals_served", "id", 101].text == (
        "How many terminals does the AHU (Revit id 101) serve?"
    )
    assert asked["terminals_served", "descriptive", 101].text == (
        "How many terminals does the AHU on the top floor serve?"
    )
    assert asked["farthest_terminal", "id", 101].truth == 106
    assert asked["feeds", "id", 123].truth == [120, 121]
    assert asked["feeds", "id", 137].truth == [135, 138]
    net = Net(_graph())
    for r in rows:
        if r.template == "controllers_between" and r.answerable:
            pair = (_g(net, r.args["a"]), _g(net, r.args["b"]))
            assert r.truth == net.controllers_between(*pair)[0]
    assert asked["cut_off", "id", 104].truth == 2
    assert asked["run_length_system", "none", "SA1"].truth == 7.5
    assert asked["circuit_of", "id", 113].truth == "P1/3"
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
    assert ("cut_off", "no_flow") in reasons  # v9: EA9 states no flow direction
    assert ("cut_off", "downstream_unknown") in reasons  # v2, v3
    assert ("circuit_of", "no_circuit_data") in reasons  # sw: "<unnamed>" and no panel
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

"""SV-10, SV-11, SV-4: the graph operations over a stored services model, each answer traced
by hand on this model (L1 below L2):

    E1 boiler = E2 pump -> E3 main (4 m DN20) -> E4 tee -> E5 pipe (2 m DN15) -> E6 radiator
                           |                      `-> E7 valve -> E8 pipe (3 m DN15, L2)
                           |                                         -> E9 radiator (L2)
                           `-> E12 stub (1 m DN20, open end)
    E10 radiator (L2), E14 board: ports, none connected; E13 socket on circuit DB1/3.
"""

from typing import Any

import pytest

from app.core.services import derive, ops
from app.core.services.ops import ask
from tests.services_fixtures import two_rooms

Doc = dict[str, Any]


def el(id_: str, kind: str, group: str, storey: str = "L1", ports: int = 2, **more: Any) -> Doc:
    return {
        "id": id_,
        "kind": kind,
        "group": group,
        "type": kind,
        "category": None,
        "typed": True,
        "systems": ["Heating 1"] if group != "electrical" else [],
        "storey": storey,
        "length_m": None,
        "size": None,
        "discipline": "heating",
        "ports": [{"id": f"{id_}.p{k}", "flow": None} for k in range(1, ports + 1)],
    } | more


def model(flows: bool = True, state: str = "connected", reason: str | None = None) -> Doc:
    elements = [
        el("E1", "boiler", "energy_conversion_device"),
        el("E2", "pump", "flow_moving_device"),
        el("E3", "pipe_segment", "flow_segment", ports=3, length_m=4.0, size="DN20"),
        el("E4", "pipe_fitting", "flow_fitting", ports=3),
        el("E5", "pipe_segment", "flow_segment", length_m=2.0, size="DN15"),
        el("E6", "space_heater", "flow_terminal"),
        el("E7", "valve", "flow_controller"),
        el("E8", "pipe_segment", "flow_segment", "L2", length_m=3.0, size="DN15"),
        el("E9", "space_heater", "flow_terminal", "L2", ports=3),
        el("E10", "space_heater", "flow_terminal", "L2", systems=[]),
        el("E12", "pipe_segment", "flow_segment", length_m=1.0, size="DN20"),
        el(
            "E13",
            "outlet",
            "flow_terminal",
            ports=0,
            systems=[],
            circuit="DB1/3",  # as the builder stores it: "<panel>/<circuit>"
        ),
        el("E14", "electric_distribution_board", "flow_controller", ports=9, systems=[]),
    ]
    pairs = [
        ("E1.p2", "E2.p1"),
        ("E2.p2", "E3.p1"),
        ("E3.p2", "E4.p1"),
        ("E3.p3", "E12.p1"),
        ("E4.p2", "E5.p1"),
        ("E5.p2", "E6.p1"),
        ("E4.p3", "E7.p1"),
        ("E7.p2", "E8.p1"),
        ("E8.p2", "E9.p1"),
    ]
    flow = {}
    for a, b in pairs:
        flow[a], flow[b] = "source", "sink"
    for e in elements:
        for p in e["ports"]:
            p["flow"] = flow.get(p["id"], "sink") if flows else None  # open ports state it too
    return {
        "version": 1,
        "connectivity": {"state": state, "reason": reason},
        "storeys": [{"id": "L1", "name": "Ground"}, {"id": "L2", "name": "Upper"}],
        "elements": elements,
        "connections": [{"a": a, "b": b, "state": "stated"} for a, b in pairs],
    }


def run(op: str, doc: Doc | None = None, **args: Any) -> dict[str, Any]:
    said = ask(derive.graph(doc or model()), op, **args)
    assert said["status"] == "ok", said
    return said


def test_sv10_a_junction_is_any_element_with_three_or_more_ports() -> None:
    assert derive.graph(model()).junctions() == ["E3", "E4", "E9", "E14"]


def test_sv10_terminals_served_from_the_equipment_unit() -> None:
    said = run("terminals_served", element_id="E1")
    assert (said["value"], said["elements"]) == (2, ["E6", "E9"])


def test_sv10_trace_and_run_lengths() -> None:
    said = run("trace", element_id="E1")
    assert said["value"] == 8 and said["terminals"] == 2 and said["run_m"] == 10.0
    said = run("run_length", system="Heating 1")
    assert (said["value"], said["by_size"]) == (10.0, {"DN20": 5.0, "DN15": 5.0})
    assert run("run_length", element_id="E1", size="DN15")["value"] == 5.0


def test_sv10_farthest_terminal_by_metres_of_run() -> None:
    said = run("farthest_terminal", element_id="E1")
    assert (said["value"], said["run_m"]) == ("E9", 7.0)


def test_sv10_controllers_between_two_elements() -> None:
    assert run("controllers_between", element_id="E6", to_element_id="E9")["value"] == ["E7"]


def test_sv10_cut_off_follows_the_stated_flow() -> None:
    said = run("cut_off", element_id="E7")
    assert (said["value"], said["elements"], said["terminals"]) == (2, ["E8", "E9"], 1)


def test_sv10_storeys_systems_open_ends_unconnected_circuit_info() -> None:
    assert run("system_storeys", system="Heating 1")["value"] == 2
    assert run("systems_crossing_storeys")["value"] == 1
    assert run("open_ends")["elements"] == ["E12"]
    assert run("unconnected", kind="space_heater")["elements"] == ["E10"]
    assert run("circuit_of", element_id="E13")["value"] == "DB1/3"
    info = run("system_info", system="Heating 1")
    assert (info["value"], info["equipment"], info["connected"]) == (10, ["E1", "E2"], True)


def test_sv11_what_feeds_is_the_equipment_reached_one_unit_for_adjacent_pieces() -> None:
    said = run("feeds", element_id="E9")
    assert said["value"] == ["E1", "E2"]  # boiler and pump touch: one unit


def test_sv11_what_feeds_prefers_a_heat_source_over_a_pump() -> None:
    doc = model()
    doc["elements"].append(el("E15", "pipe_segment", "flow_segment", length_m=0.5))
    doc["connections"][0] = {"a": "E1.p2", "b": "E15.p1", "state": "stated"}
    doc["connections"].append({"a": "E15.p2", "b": "E2.p1", "state": "stated"})
    said = run("feeds", doc, element_id="E9")
    assert said["value"] == ["E1"] and said["also"] == [["E2"]]


def test_sv11_cut_off_refuses_without_a_stated_flow_on_nine_ports_in_ten() -> None:
    said = ask(derive.graph(model(flows=False)), "cut_off", element_id="E7")
    assert said == {
        "status": "unknown",
        "reason": "this model does not say which way the water flows here",
    }


def test_sv4_no_connections_refuses_network_questions_with_the_reason() -> None:
    doc = model(state="none", reason="the file has no port connections")
    said = ask(derive.graph(doc), "feeds", element_id="E9")
    assert said == {"status": "unknown", "reason": "the file has no port connections"}
    assert ask(derive.graph(doc), "unconnected")["status"] == "ok"  # not a network question


def test_sv4_partial_refuses_only_for_the_loose_part() -> None:
    doc = model(state="partial", reason="1 radiator has no connected port")
    assert ask(derive.graph(doc), "feeds", element_id="E9")["status"] == "ok"
    said = ask(derive.graph(doc), "feeds", element_id="E10")
    assert said == {"status": "unknown", "reason": "1 radiator has no connected port"}


@pytest.mark.parametrize(
    ("op", "args", "reason"),
    [
        ("feeds", {"element_id": "E99"}, "no element E99 in this model"),
        ("teleport", {}, "no operation 'teleport'"),
        ("circuit_of", {"element_id": "E6"}, "the model states no panel or circuit for E6"),
        ("system_info", {"system": "Nope"}, "no system 'Nope' in this model"),
    ],
)
def test_sv10_what_cannot_be_answered_is_unknown_with_a_reason(
    op: str, args: dict[str, str], reason: str
) -> None:
    assert ask(derive.graph(model()), op, **args) == {"status": "unknown", "reason": reason}


def test_sv10_on_the_stored_model_a_radiator_is_fed_by_the_boiler() -> None:
    g = derive.graph(two_rooms())
    assert ask(g, "feeds", element_id="E2")["value"] == ["E1"]
    served = ask(g, "terminals_served", element_id="E1")
    assert (served["value"], served["elements"]) == (2, ["E2", "E3"])
    assert ask(g, "farthest_terminal", element_id="E1")["value"] == "E3"
    assert (
        ask(g, "run_length", system="Heating Supply", size="DN15")["value"] == 0.361
    )  # 2 x sqrt(0.15² + 0.10²)


def test_sv12_a_full_rederive_after_an_edit_sees_the_change() -> None:
    model = two_rooms()
    gone = {"E3", "E11", "E13"}  # the radiator and its two branches
    edited = model.model_copy(
        update={
            "elements": tuple(e for e in model.elements if e.id not in gone),
            "connections": tuple(
                c
                for c in model.connections
                if c.a.split(".")[0] not in gone and c.b.split(".")[0] not in gone
            ),
        }
    )
    assert ask(derive.graph(edited), "terminals_served", element_id="E1")["value"] == 1
    heaters = [
        f for f in derive.facts(edited) if f.topic == "space_heater.count" and f.subject == "all"
    ]
    assert [f.value for f in heaters if f.storey is None and f.system is None] == [1]
    assert (
        ask(derive.graph(model), "terminals_served", element_id="E1")["value"] == 2
    )  # source kept


def test_sv10_a_circuit_is_read_from_the_stored_panel_slash_circuit_text() -> None:
    said = run("circuit_of", element_id="E13")
    assert (said["value"], said["panel"], said["circuit"]) == ("DB1/3", "DB1", "3")
    doc = model()
    doc["elements"][11]["circuit"] = "DB2"  # a panel with no circuit number
    said = run("circuit_of", doc, element_id="E13")
    assert (said["value"], said["panel"], said["circuit"]) == ("DB2", "DB2", None)


def test_sv24_ask_never_raises_an_unexpected_error_becomes_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(g: object, **args: object) -> dict[str, object]:
        raise AttributeError("'str' object has no attribute 'get'")

    monkeypatch.setitem(ops.OPERATIONS, "trace", broken)
    said = ask(derive.graph(model()), "trace", element_id="E1")
    assert said["status"] == "unknown" and "trace" in said["reason"]


def test_sv10_systems_crossing_storeys_match_the_systems_own_type_or_one_part_of_it() -> None:
    doc = model()
    doc["systems"] = [
        {"name": "Heating 1", "type": "Domestic Hot Water,Heating", "element_count": 10}
    ]
    for e in doc["elements"]:
        e["system_type"] = "Other"  # a member's property is not the system's type
    assert run("systems_crossing_storeys", doc, system_type="Heating")["value"] == 1
    assert run("systems_crossing_storeys", doc, system_type="domestic hot water")["value"] == 1
    assert run("systems_crossing_storeys", doc, system_type="Heat")["value"] == 0  # not a part
    assert run("systems_crossing_storeys", doc, system_type="Other")["value"] == 0


def apart(first: dict[str, Any]) -> Doc:
    """The model with E1 replaced by `first` and a pipe E15 between it and the pump E2."""
    doc = model()
    doc["elements"][0] = el("E1", **first)
    doc["elements"].append(el("E15", "pipe_segment", "flow_segment", length_m=0.5))
    doc["connections"][0] = {"a": "E1.p2", "b": "E15.p1", "state": "stated"}
    doc["connections"].append({"a": "E15.p2", "b": "E2.p1", "state": "stated"})
    return doc


def test_sv11_a_storage_water_heater_is_a_heat_source_preferred_over_the_pump() -> None:
    heater = {"kind": "tank", "group": "flow_storage_device", "predefined": "PRESSUREVESSEL"}
    said = run("feeds", apart(heater), element_id="E9")
    assert said["value"] == ["E1"] and said["also"] == [["E2"]]


def test_sv11_with_no_source_feeds_is_the_set_of_equipment_reached() -> None:
    expansion = {"kind": "tank", "group": "flow_storage_device", "predefined": "EXPANSION"}
    said = run("feeds", apart(expansion), element_id="E9")
    assert said["value"] == ["E1", "E2"] and said["also"] == []


def test_sv11_feeds_refuses_when_the_network_reaches_no_equipment() -> None:
    doc = model()
    doc["elements"] += [
        el("E16", "pipe_segment", "flow_segment", length_m=1.0),
        el("E17", "space_heater", "flow_terminal"),
    ]
    doc["connections"].append({"a": "E16.p2", "b": "E17.p1", "state": "stated"})
    said = ask(derive.graph(doc), "feeds", element_id="E17")
    assert said == {"status": "unknown", "reason": "its network reaches no equipment"}

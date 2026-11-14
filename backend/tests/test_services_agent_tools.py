"""SV-22..SV-27: the services tools of the agent chat (app/adapters/services_agent_tools.py), on
the two-room fixture as drawing "d1": radiators E2 (SR1) and E3 (SR2) on the south wall SW1."""

import json
from typing import Any

import pytest

from app.adapters.services_agent_tools import (
    SERVICES_TOOLS,
    ServicesToolStore,
    resolve_selection,
    run_services_tool,
)
from app.core.plan_edit.model import Selection
from app.core.services.stored import Connectivity, ServicesModel, fraction
from tests.services_fixtures import SUPPLY, two_rooms

LIMIT = 4000


def _never() -> Any:
    raise AssertionError("a services proposal carries its change")


def _store(model: ServicesModel | None = None, **selections: Selection) -> ServicesToolStore:
    return ServicesToolStore(models={"d1": model or two_rooms()}, selections=selections)


def _run(store: ServicesToolStore, name: str, **arguments: Any) -> dict[str, Any]:
    text = run_services_tool(store, name, json.dumps(arguments))
    assert len(text) < LIMIT
    return json.loads(text)


def _region(x: float, y: float, half: float = 0.2) -> Selection:
    storey = two_rooms().storeys[0]
    (fx0, fy0), (fx1, fy1) = (
        fraction(storey, (x - half, y + half)),
        fraction(storey, (x + half, y - half)),
    )
    return Selection(id="sel_1", kind="region", drawing_id="d1", page=1, box=(fx0, fy0, fx1, fy1))


# --- SV-23 list_services -------------------------------------------------------------------------


def test_sv23_list_services_gives_storeys_systems_and_terminals_with_places() -> None:
    found = _run(_store(), "list_services", drawing_id="d1")
    assert found["connectivity"]["state"] == "connected"
    assert found["storeys"] == [{"id": "L1", "name": "Level 1", "page": 1}]
    supply = next(s for s in found["systems"] if s["name"] == SUPPLY)
    assert supply["discipline"] == "heating" and supply["length_m"] > 0
    items = {i["id"]: i for i in found["items"]}
    assert set(items) == {"E1", "E2", "E3"}  # the boiler and the two radiators
    assert items["E2"]["room"] == "SR1" and items["E2"]["page"] == 1
    x0, y0, x1, y1 = items["E2"]["box"]
    assert 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1
    assert found["drawing_id"] == "d1"


def test_sv23_list_services_of_a_room_gives_its_walls_and_whether_a_main_is_in_reach() -> None:
    found = _run(_store(), "list_services", drawing_id="d1", room_id="SR1")
    walls = {w["id"]: w for w in found["walls"]}
    assert set(walls) == {"SW1", "SW2", "SW3", "SW5"}
    assert walls["SW1"]["mounted"] == ["E2"] and walls["SW5"]["openings"] == ["door"]
    assert walls["SW5"]["free_m"] < walls["SW5"]["length_m"] == pytest.approx(4.0)
    assert found["main_in_reach"] is True
    assert {i["id"] for i in found["items"]} == {"E1", "E2"}


def test_sv23_list_services_filters_and_stays_short_with_a_more_count() -> None:
    model = two_rooms()
    doc = model.model_dump(mode="json", by_alias=True)
    radiator = next(e for e in doc["elements"] if e["id"] == "E3")
    many = [
        {**radiator, "id": f"E{100 + i}", "ref": {"guid": f"g{i}"}, "ports": []} for i in range(300)
    ]
    big = ServicesModel.model_validate({**doc, "elements": [*doc["elements"], *many]})
    found = _run(_store(big), "list_services", drawing_id="d1", kind="space_heater")
    assert len(found["items"]) <= 60 and found["more"] == 302 - len(found["items"])
    assert all(i["kind"] == "space_heater" for i in found["items"])


def test_sv22_sv26_list_services_narrows_to_the_room_of_a_selection() -> None:
    store = _store(sel_1=_region(7.5, 2.0))  # inside SR2
    found = _run(store, "list_services", drawing_id="d1", selection_id="sel_1")
    assert found["room"]["id"] == "SR2" and {i["id"] for i in found["items"]} == {"E3"}
    outside = _store(sel_1=_region(-1.5, 2.0))  # off every room, still on the storey (page 1)
    found = _run(outside, "list_services", drawing_id="d1", selection_id="sel_1")
    assert "room" not in found and {i["id"] for i in found["items"]} == {"E1", "E2", "E3"}
    assert "error" in _run(_store(), "list_services", drawing_id="d1", selection_id="sel_1")
    other = _region(7.5, 2.0).model_copy(update={"drawing_id": "d2"})
    assert "error" in _run(_store(sel_1=other), "list_services", drawing_id="d1",
                           selection_id="sel_1")  # fmt: skip


def test_sv23_list_services_bad_ids_say_so() -> None:
    assert "error" in _run(_store(), "list_services", drawing_id="nope")
    assert "error" in _run(_store(), "list_services", drawing_id="d1", room_id="SR9")


# --- SV-24 ask_services --------------------------------------------------------------------------


def test_sv24_ask_services_answers_with_the_elements_and_their_boxes() -> None:
    found = _run(_store(), "ask_services", drawing_id="d1", op="feeds", element_id="E2")
    assert found["status"] == "ok" and found["value"]
    assert found["elements"] and {"id", "page", "box"} <= set(found["elements"][0])


def test_sv24_ask_services_bad_element_is_unknown_and_a_bad_op_is_an_error() -> None:
    found = _run(_store(), "ask_services", drawing_id="d1", op="feeds", element_id="E99")
    assert found["status"] == "unknown" and found["reason"]
    assert "error" in _run(_store(), "ask_services", drawing_id="d1", op="explode")


# --- SV-25 proposals -----------------------------------------------------------------------------


def test_sv25_propose_move_terminal_ok_with_the_change() -> None:
    store = _store()
    found = _run(store, "propose_move_terminal", drawing_id="d1", element_id="E2", wall_id="SW2")
    assert found["status"] == "ok"
    proposal = found["proposal"]
    assert proposal["proposal_id"] == "p1" and proposal["drawing_id"] == "d1"
    assert proposal["page"] == 1 and proposal["op"] == "move_terminal"
    assert all(c["ok"] for c in proposal["checks"])
    assert any(f["code"] == "not_sized" for f in proposal["flags"])
    assert len(store.proposals) == 1
    assert (store.proposals[0].services_change or _never()).patch.moved


def test_sv25_one_proposal_per_turn() -> None:
    store = _store()
    _run(store, "propose_move_terminal", drawing_id="d1", element_id="E2", wall_id="SW2")
    second = _run(store, "propose_remove_element", drawing_id="d1", element_id="E3")
    assert second["status"] == "refused"


def test_sv25_a_refusal_carries_the_rule_s_words() -> None:
    found = _run(_store(), "propose_move_terminal", drawing_id="d1", element_id="E2", wall_id="SW1")
    assert found == {"status": "refused", "reason": "It is already on that wall."}
    found = _run(
        _store(), "propose_move_terminal", drawing_id="d1", element_id="E99", wall_id="SW2"
    )
    assert found == {"status": "refused", "reason": "This is not a terminal."}


def test_sv25_a_model_without_rooms_or_connections_cannot_be_edited() -> None:
    model = two_rooms().model_copy(update={"rooms": ()})
    found = _run(
        _store(model), "propose_move_terminal", drawing_id="d1", element_id="E2", wall_id="SW2"
    )
    assert found["status"] == "cannot_edit" and "no rooms" in found["reason"]
    model = two_rooms().model_copy(
        update={"connections": (), "connectivity": Connectivity(state="none")}
    )
    found = _run(_store(model), "propose_remove_element", drawing_id="d1", element_id="E2")
    assert found["status"] == "cannot_edit"


def test_sv25_remove_add_and_resize() -> None:
    assert (
        _run(_store(), "propose_remove_element", drawing_id="d1", element_id="E2")["status"] == "ok"
    )
    assert (
        _run(_store(), "propose_remove_element", drawing_id="d1", element_id="E9")["status"]
        == "refused"
    )
    added = _run(
        _store(), "propose_add_terminal", drawing_id="d1", like_element_id="E2", wall_id="SW2"
    )
    assert added["status"] == "ok" and added["proposal"]["op"] == "add_terminal"
    resized = _run(_store(), "propose_resize", drawing_id="d1", element_id="E10", size="DN20")
    assert resized["status"] == "ok"
    refused = _run(_store(), "propose_resize", drawing_id="d1", element_id="E10", size="DN50")
    assert refused["status"] == "refused"


# --- SV-22 selections ----------------------------------------------------------------------------


def test_sv22_a_region_resolves_to_its_room_the_nearest_wall_and_a_point() -> None:
    found = resolve_selection(two_rooms(), _region(2.5, 3.8))
    assert found is not None
    assert (found.room_id, found.wall_id) == ("SR1", "SW2")
    assert found.point == pytest.approx((2.5, 3.8))


def test_sv22_a_region_in_no_room_or_on_another_page_resolves_to_nothing() -> None:
    assert resolve_selection(two_rooms(), _region(-1.5, 5.5)) is None
    other = _region(2.5, 3.8).model_copy(update={"page": 2})
    assert resolve_selection(two_rooms(), other) is None


def test_sv22_a_move_to_a_selection() -> None:
    store = _store(sel_1=_region(2.5, 3.8))
    found = _run(
        store, "propose_move_terminal", drawing_id="d1", element_id="E2", selection_id="sel_1"
    )
    assert found["status"] == "ok"
    moved = (store.proposals[0].services_change or _never()).moved[0]
    assert moved.to_m is not None and moved.to_m[0] == pytest.approx(2.5, abs=0.3)
    found = _run(
        _store(), "propose_move_terminal", drawing_id="d1", element_id="E2", selection_id="sel_7"
    )
    assert "error" in found


# --- SV-27 size, robustness ----------------------------------------------------------------------


def test_sv27_the_six_schemas_stay_under_1500_tokens() -> None:
    names = [t["function"]["name"] for t in SERVICES_TOOLS]
    assert names == [
        "list_services", "ask_services", "propose_move_terminal", "propose_add_terminal",
        "propose_remove_element", "propose_resize",
    ]  # fmt: skip
    assert len(json.dumps(SERVICES_TOOLS)) < 1500 * 4  # about 4 characters a token


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("list_services", "not json"),
        ("list_services", "[1, 2]"),
        ("list_services", json.dumps({"drawing_id": "d1", "colour": "red"})),
        ("ask_services", json.dumps({"drawing_id": "d1", "op": "feeds", "element_id": 7})),
        ("propose_move_terminal", json.dumps({"drawing_id": "d1"})),
        (
            "propose_resize",
            json.dumps({"drawing_id": "d1", "element_id": "E10", "size": "x" * 999}),
        ),
        ("explode", "{}"),
    ],
)
def test_sv25_never_raises_on_garbage(name: str, arguments: str) -> None:
    text = run_services_tool(_store(), name, arguments)
    assert "error" in json.loads(text) and len(text) < LIMIT

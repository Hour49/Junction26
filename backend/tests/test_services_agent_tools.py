"""SV-22..SV-27: the services tools of the agent chat (app/adapters/services_agent_tools.py), on
the two-room fixture as drawing "d1": radiators E2 (SR1) and E3 (SR2) on the south wall SW1."""

import json
from types import SimpleNamespace
from typing import Any

import pytest

from app.adapters.services_agent_tools import (
    SERVICES_TOOLS,
    ServicesToolStore,
    _ProjectModels,  # pyright: ignore[reportPrivateUsage]
    resolve_selection,
    run_services_tool,
)
from app.adapters.services_store import ServicesStore
from app.core.ingest.model import FileStatus, ProjectStatus
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


def test_sv23_a_count_question_gets_the_total_not_the_part_listed() -> None:
    """Live (#430): "How many radiators are there?" → "14 ... and 49 more"; the total first."""
    model = two_rooms()
    doc = model.model_dump(mode="json", by_alias=True)
    radiator = next(e for e in doc["elements"] if e["id"] == "E3")
    many = [{**radiator, "id": f"E{100 + i}", "ref": {"guid": f"g{i}"}} for i in range(61)]
    big = ServicesModel.model_validate({**doc, "elements": [*doc["elements"], *many]})
    found = _run(_store(big), "list_services", drawing_id="d1", kind="space_heater")
    assert found["count"] == 63 and len(found["items"]) < 63
    listing = next(t for t in SERVICES_TOOLS if t["function"]["name"] == "list_services")
    assert "count" in listing["function"]["description"]


def test_sv23_a_heating_system_named_h_underscore_is_called_heating() -> None:
    """Live (#430): German exports name heating systems H_* (Vorlauf/Rücklauf) and their pipes
    read as plumbing; the system's own name says heating."""
    doc = two_rooms().model_dump(mode="json", by_alias=True)
    names = {SUPPLY: "H_Transport_VL_1", "Heating Return": "H_Transport_RL_0"}
    for e in doc["elements"]:
        e["systems"] = [names.get(s, s) for s in e["systems"]]
        e["discipline"] = "plumbing"  # what the words of a pipe give
    found = _run(_store(ServicesModel.model_validate(doc)), "list_services", drawing_id="d1")
    assert {s["name"]: s["discipline"] for s in found["systems"]} == {
        "H_Transport_RL_0": "heating",
        "H_Transport_VL_1": "heating",
    }


def test_sv23_a_system_s_own_words_name_its_discipline_before_its_members() -> None:
    doc = two_rooms().model_dump(mode="json", by_alias=True)
    for e in doc["elements"]:
        e["systems"] = ["Domestic Cold Water" if s == SUPPLY else "Lüftung 1" for s in e["systems"]]
        e["discipline"] = "heating"
    found = _run(_store(ServicesModel.model_validate(doc)), "list_services", drawing_id="d1")
    # "Lüftung" says nothing to the table: the members' majority stays
    assert {s["name"]: s["discipline"] for s in found["systems"]} == {
        "Domestic Cold Water": "plumbing",
        "Lüftung 1": "heating",
    }


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


NOT_READ = (
    "none of this project's IFC files has been read into a services model yet, so its pipes, "
    "ducts and cables cannot be followed"
)


def test_sv23_a_project_with_no_services_model_read_says_so_in_words() -> None:
    """QA: an IFC upload has no services model until one is built; the error says that, with
    no drawing id and no "models: none" (it is what a person reads in the chat)."""
    store = ServicesToolStore(models={})
    assert _run(store, "list_services", drawing_id="78b0f2d7c0284c60") == {"error": NOT_READ}
    assert _run(store, "list_services") == {"error": NOT_READ}
    assert _run(store, "ask_services", drawing_id="d1", op="feeds", element_id="E2") == {
        "error": NOT_READ
    }
    # a project that has models still names them, so the chat can pick one
    named = _run(_store(), "list_services", drawing_id="x")["error"]
    assert "the project's services models: d1" in named


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


def test_sv25_listing_the_project_s_models_loads_none_of_them(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review nit (#397): the names come from which stored files exist, not from reading them."""
    files = tuple(
        FileStatus(id=f"f{n}", path=f"m/{n}.ifc", size=1, sha256=c * 64, kind="ifc",
                   state="ready", route="bim", drawing_id=f"d{n}")
        for n, c in ((1, "a"), (2, "b"))
    )  # fmt: skip
    status = ProjectStatus(id="p", name="p", state="done", created_at="2026-11-15T00:00:00Z",
                           files=files)  # fmt: skip
    pipeline = SimpleNamespace(project_id="p", ingest=SimpleNamespace(status=lambda _: status))
    store = ServicesStore(tmp_path)
    store.path("a" * 64).write_bytes(b"stored")  # only d1 has a stored model
    monkeypatch.setattr(ServicesStore, "load", lambda *_: _never())
    models = _ProjectModels(pipeline, store, [])  # pyright: ignore[reportArgumentType]
    assert list(models) == ["d1"] and len(models) == 1


# --- room names (QA #430 c6886540832: a room's name never reached the services model's room) ---


def test_listed_items_carry_their_rooms_name() -> None:
    items = {i["id"]: i for i in _run(_store(), "list_services", drawing_id="d1")["items"]}
    assert items["E2"]["room"] == "SR1" and items["E2"]["room_name"] == "1 Living"
    assert items["E3"]["room_name"] == "2 Bedroom"


@pytest.mark.parametrize("named", ["1 Living", "living 1", "LIVING", "SR1", "sr1"])
def test_the_room_argument_takes_a_name_in_any_case_and_word_order(named: str) -> None:
    found = _run(_store(), "list_services", drawing_id="d1", room_id=named)
    assert found["room"] == {"id": "SR1", "name": "1 Living"}
    assert {i["id"] for i in found["items"]} == {"E1", "E2"}


def test_a_name_two_rooms_hold_lists_them_and_an_unknown_one_says_so() -> None:
    model = two_rooms()
    renamed = model.model_copy(
        update={"rooms": (model.rooms[0], model.rooms[1].model_copy(update={"name": "2 Living"}))}
    )
    both = _run(_store(renamed), "list_services", drawing_id="d1", room_id="living")
    assert "SR1 '1 Living'" in both["error"] and "SR2 '2 Living'" in both["error"]
    unknown = _run(_store(), "list_services", drawing_id="d1", room_id="Küche 1-3")
    assert "no room named 'Küche 1-3'" in unknown["error"] and "1 Living" in unknown["error"]


# --- breakdowns (#430 c6886940069 R2: "of each type", "per room" refused when the list was cut) ---


def _many(count: int, types: int) -> ServicesModel:
    """The fixture with `count` more radiators in turns of the two rooms, of `types` type names."""
    doc = two_rooms().model_dump(mode="json", by_alias=True)
    radiator = next(e for e in doc["elements"] if e["id"] == "E3")
    many = [
        {**radiator, "id": f"E{100 + i}", "ref": {"guid": f"g{i}"}, "ports": [],
         "type": f"Radiator type {i % types}", "room": ("SR1", "SR2")[i % 2]}
        for i in range(count)
    ]  # fmt: skip
    return ServicesModel.model_validate({**doc, "elements": [*doc["elements"], *many]})


def test_a_cut_list_still_counts_every_match_by_type_and_by_room() -> None:
    found = _run(_store(_many(300, 3)), "list_services", drawing_id="d1", kind="space_heater")
    assert found["more"] > 0  # the items are cut, the groups are not
    assert found["by_type"] == {
        "Radiator type 0": 100, "Radiator type 1": 100, "Radiator type 2": 100,
        "Radiator 22-600": 2,
    }  # fmt: skip
    assert found["by_room"] == {"SR1 1 Living": 151, "SR2 2 Bedroom": 151}


def test_too_many_groups_keep_the_largest_and_count_the_rest() -> None:
    found = _run(_store(_many(300, 300)), "list_services", drawing_id="d1", kind="space_heater")
    rest = [k for k in found["by_type"] if k.startswith("and ")]
    assert len(rest) == 1 and rest[0].endswith(" more groups")
    assert sum(found["by_type"].values()) == found["count"] == 302
    assert found["by_type"]["Radiator 22-600"] == 2  # the largest group is kept


def test_the_list_tool_says_breakdowns_come_from_the_groups() -> None:
    listing = next(t for t in SERVICES_TOOLS if t["function"]["name"] == "list_services")
    said = listing["function"]["description"]
    assert "by_type" in said and "by_room" in said

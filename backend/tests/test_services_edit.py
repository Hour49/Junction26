"""SV-13..SV-21: the edit operations on the stored services model (app/core/services/edit.py), on
the two-room fixture (tests/services_fixtures.py: radiators E2 in SR1 and E3 in SR2 on the south
wall SW1, mains along it, a door SO1 in the wall SW5 between the rooms)."""

import hashlib
import math
from typing import Any

import pytest
from services_fixtures import two_rooms

from app.core.services import edit
from app.core.services.edit import (
    EditRefusedError,
    Patch,
    add_terminal,
    apply,
    move_terminal,
    remove_element,
    resize,
)
from app.core.services.stored import ServicesModel


def _hash(model: ServicesModel) -> str:
    return hashlib.sha256(model.model_dump_json().encode()).hexdigest()


def _with(model: ServicesModel, **elements: dict[str, Any]) -> ServicesModel:
    """The model with some elements' fields changed (by id), or new elements (unknown id)."""
    doc = model.model_dump(mode="json", by_alias=True)
    ids = {e["id"] for e in doc["elements"]}
    doc["elements"] = [{**e, **elements.get(e["id"], {})} for e in doc["elements"]]
    doc["elements"] += [{"id": i, **fields} for i, fields in elements.items() if i not in ids]
    return ServicesModel.model_validate(doc)


def _doc_with(model: ServicesModel, **fields: Any) -> ServicesModel:
    return ServicesModel.model_validate({**model.model_dump(mode="json", by_alias=True), **fields})


def _pipe_m(model: ServicesModel) -> float:
    return sum(e.length_m or 0 for e in model.elements if e.group == "flow_segment")


def _check(change: edit.ServicesChange, code: str) -> bool:
    return next(c.ok for c in change.checks if c.code == code)


# --- SV-13 patches -------------------------------------------------------------------------------


def test_sv13_apply_is_pure_and_gives_the_edited_model() -> None:
    model = two_rooms()
    before = _hash(model)
    change = move_terminal(model, "E2", "SW2", "centre")
    after = apply(model, change.patch)
    assert _hash(model) == before
    moved = next(e for e in after.elements if e.id == "E2")
    assert moved.at is not None and moved.at[1] == pytest.approx(3.9)
    assert {e.id for e in after.elements} >= {e.id for e in change.patch.added}
    assert not {e.id for e in after.elements} & set(change.patch.removed)


def test_sv13_an_empty_patch_changes_nothing() -> None:
    model = two_rooms()
    assert apply(model, Patch()) == model


def test_sv13_a_second_edit_runs_on_the_source_plus_the_accepted_patch() -> None:
    model = two_rooms()
    first = apply(model, move_terminal(model, "E2", "SW2", "centre").patch)
    second = remove_element(first, "E2")
    after = apply(first, second.patch)
    assert "E2" not in {e.id for e in after.elements}
    added_first = {e.id for e in first.elements} - {e.id for e in model.elements}
    added_second = {e.id for e in second.patch.added}
    assert not added_first & added_second  # new ids never collide with accepted ones


# --- SV-14 move ----------------------------------------------------------------------------------


def test_sv14_move_puts_the_radiator_on_the_wall_at_its_distance_and_height_rotated() -> None:
    model = two_rooms()
    change = move_terminal(model, "E2", "SW2", "centre")
    after = apply(model, change.patch)
    radiator = next(e for e in after.elements if e.id == "E2")
    assert radiator.at == pytest.approx((2.5, 3.9, 0.5))
    # turned 180 degrees: the supply port (was x 2.05) is now on the east side
    supply = next(p for p in radiator.ports if p.flow == "sink")
    assert supply.at == pytest.approx((2.95, 3.9, 0.25))
    assert change.op == "move_terminal" and change.storey == "L1"
    assert change.moved[0].id == "E2"


def test_sv14_facts_before_and_after_equal_the_geometry() -> None:
    model = two_rooms()
    change = move_terminal(model, "E2", "SW2", "centre")
    after = apply(model, change.patch)
    removed = sum(
        e.length_m or 0
        for e in model.elements
        if e.id in change.patch.removed and e.group == "flow_segment"
    )
    added = sum(math.dist(*e.path) for e in change.patch.added if e.path)  # type: ignore[arg-type]
    assert _pipe_m(after) == pytest.approx(_pipe_m(model) - removed + added, abs=1e-6)
    by_size = {(f.system, f.size): f for f in change.facts if f.what == "pipe length"}
    dn15 = sum(f.after - f.before for (_, size), f in by_size.items() if size == "DN15")
    assert dn15 == pytest.approx(added - removed, abs=0.01)


def test_sv14_the_new_runs_stay_in_the_room_and_pass_no_door() -> None:
    model = two_rooms()
    change = move_terminal(model, "E2", "SW2", "centre")
    for run in change.patch.added:
        if run.path:
            assert all(-0.01 <= p[0] <= 5.0 and -0.01 <= p[1] <= 4.0 for p in run.path)
    assert _check(change, "no_door")


def test_sv14_a_position_word_picks_the_place_along_the_wall() -> None:
    model = two_rooms()
    start = move_terminal(model, "E2", "SW2", "start")
    end = move_terminal(model, "E2", "SW2", "end")
    xs = sorted((c.moved[0].to_m or (0.0,))[0] for c in (start, end))
    assert xs[0] == pytest.approx(0.6) and xs[1] == pytest.approx(4.4)


def test_sv14_a_terminal_placed_at_one_end_is_centred_on_the_wall_by_its_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real = edit.reroute  # this pair crosses at the mains; only the placement is tested here
    monkeypatch.setattr(edit, "reroute", lambda *a, **k: real(*a, **k, cross_at_ports_m=99))
    # IFC radiators are placed at one end of the body, their ports at the other
    ends = {
        "at": (3.0, 0.1, 0.02),
        "ports": [
            {"id": "E2.p1", "at": (2.0, 0.15, 0.1), "flow": "sink"},
            {"id": "E2.p2", "at": (2.0, 0.1, 0.1), "flow": "source"},
        ],
    }
    model = _with(two_rooms(), E2=ends)
    change = move_terminal(model, "E2", "SW2", "centre")
    moved = next(e for e in apply(model, change.patch).elements if e.id == "E2")
    assert moved.at is not None
    xs = [moved.at[0], *(p.at[0] for p in moved.ports if p.at)]
    assert (min(xs) + max(xs)) / 2 == pytest.approx(2.5, abs=0.01)


# --- SV-15 remove --------------------------------------------------------------------------------


def test_sv15_remove_takes_the_radiator_and_its_branches_and_closes_the_tees() -> None:
    model = two_rooms()
    change = remove_element(model, "E2")
    assert set(change.patch.removed) >= {"E2", "E10", "E12"}
    after = apply(model, change.patch)
    assert {"E4", "E6"} & {e.id for e in after.elements} == set()  # tees closed
    assert all(c.ok for c in change.checks)
    branches = sum(e.length_m or 0 for e in model.elements if e.id in ("E10", "E12"))
    assert _pipe_m(after) == pytest.approx(_pipe_m(model) - branches)  # the tees leave no gap


def _without_port_places(model: ServicesModel) -> ServicesModel:
    """The model as an IFC2X3 export gives it: connected ports, none with a position."""
    doc = model.model_dump(mode="json", by_alias=True)
    for e in doc["elements"]:
        e["ports"] = [{**p, "at": None} for p in e["ports"]]
    return ServicesModel.model_validate(doc)


def test_edits_that_draw_runs_are_refused_when_the_ports_have_no_positions() -> None:
    model = _without_port_places(two_rooms())
    words = r"^The file gives no positions for the pipe and duct ends"
    with pytest.raises(EditRefusedError, match=words):
        move_terminal(model, "E2", "SW2", "centre")
    with pytest.raises(EditRefusedError, match=words):
        add_terminal(model, "E2", "SW2", "centre")
    with pytest.raises(EditRefusedError, match=words):
        remove_element(model, "E2")  # closing its tees draws a straight piece between two ends
    assert resize(model, "E10", "DN20").patch  # a resize draws nothing


# --- SV-16 add ----------------------------------------------------------------------------------


def test_sv16_add_copies_the_type_onto_the_wall_and_connects_it_to_the_mains() -> None:
    model = two_rooms()
    change = add_terminal(model, "E2", "SW2", "centre")
    after = apply(model, change.patch)
    (new,) = [e for e in change.patch.added if e.group == "flow_terminal"]
    assert new.id.startswith("N") and new.type == "Radiator 22-600" and new.room == "SR1"
    assert new.at == pytest.approx((2.5, 3.9, 0.5))
    assert all(c.ok for c in change.checks)
    count = next(f for f in change.facts if f.what == "space_heater count")
    assert (count.before, count.after) == (2, 3)
    linked = {x for c in after.connections for x in (c.a, c.b)}
    assert all(p.id in linked for p in new.ports)
    assert any(f.code == "not_sized" for f in change.flags)
    assert change.op == "add_terminal" and change.moved[0].id == new.id


def test_sv16_add_into_the_other_room_of_a_shared_wall_names_the_room() -> None:
    change = add_terminal(two_rooms(), "E2", "SW2", "centre", room_id="SR2")
    (new,) = [e for e in change.patch.added if e.group == "flow_terminal"]
    assert new.room == "SR2"


def test_sv16_add_is_refused_with_the_move_words() -> None:
    model = _with(two_rooms(), E2={"body_m": (4.0, 0.06, 0.6)})
    with pytest.raises(EditRefusedError, match=r"^This wall is too short for it\.$"):
        add_terminal(model, "E2", "SW3", "centre")
    with pytest.raises(EditRefusedError, match=r"^This is not a terminal\.$"):
        add_terminal(two_rooms(), "E9", "SW2", "centre")


# --- SV-17 resize --------------------------------------------------------------------------------


def test_sv17_resize_to_a_size_of_the_system_moves_the_length_between_sizes() -> None:
    model = two_rooms()
    change = resize(model, "E10", "DN20")
    after = apply(model, change.patch)
    assert next(e for e in after.elements if e.id == "E10").size == "DN20"
    assert any(f.code == "not_sized" for f in change.flags)
    assert "Flow and pressure are not checked." in [f.text for f in change.flags]


def test_sv17_resize_to_a_size_the_system_does_not_have_is_refused() -> None:
    with pytest.raises(EditRefusedError):
        resize(two_rooms(), "E10", "DN50")


# --- SV-19 refusals, word for word ---------------------------------------------------------------


def _refusal(model: ServicesModel, *args: Any) -> str:
    with pytest.raises(EditRefusedError) as refused:
        move_terminal(model, *args)
    return str(refused.value)


def test_sv19_not_a_terminal() -> None:
    assert _refusal(two_rooms(), "E9", "SW2", "centre") == "This is not a terminal."
    with pytest.raises(EditRefusedError, match=r"^This is not a terminal\.$"):
        remove_element(two_rooms(), "E9")


def test_sv19_in_no_room() -> None:
    model = _with(two_rooms(), E2={"room": None})
    assert _refusal(model, "E2", "SW2", "centre") == "This element is in no room of the model."


def test_sv19_already_on_that_wall() -> None:
    assert _refusal(two_rooms(), "E2", "SW1", "centre") == "It is already on that wall."


def test_sv19_wall_too_short() -> None:
    model = _with(two_rooms(), E2={"body_m": (4.0, 0.06, 0.6)})
    assert _refusal(model, "E2", "SW3", "centre") == "This wall is too short for it."


def test_sv19_no_free_place() -> None:
    model = _with(two_rooms(), E2={"body_m": (2.5, 0.06, 0.6)})
    assert _refusal(model, "E2", "SW5", "centre") == (
        "No free place on this wall: a door or another terminal is in the way."
    )


def test_sv19_another_terminal_already_there() -> None:
    model = two_rooms()
    other = next(e for e in model.elements if e.id == "E3").model_dump(mode="json")
    other.update(id="E16", ref={"guid": "guid-E16"}, room="SR1", at=(2.5, 3.9, 0.5),
                 ports=[{"id": "E16.p1", "at": (2.0, 3.9, 0.25), "flow": "sink"}])  # fmt: skip
    model = _with(model, E16={k: v for k, v in other.items() if k != "id"})
    assert _refusal(model, "E2", "SW2", (2.5, 3.9)) == "Another terminal is already there."
    assert move_terminal(model, "E2", "SW2", "centre").moved  # the slide finds a free place


def test_sv19_both_ways_round_pass_a_door() -> None:
    model = two_rooms()
    doc = model.model_dump(mode="json", by_alias=True)
    door = {**doc["openings"][0], "id": "SO2", "ref": {"guid": "guid-SO2"}, "wall": "SW4",
            "segment": [[10.0, 1.5], [10.0, 2.4]]}  # fmt: skip
    model = _doc_with(model, openings=[*doc["openings"], door])
    assert _refusal(model, "E3", "SW2", "centre") == "Both ways round this room pass a door."


def test_sv19_no_pipe_of_this_circuit_in_or_next_to_the_room() -> None:
    model = two_rooms()
    doc = model.model_dump(mode="json", by_alias=True)
    rooms = [{**doc["rooms"][0], "polygon": [[0, 1.5], [5, 1.5], [5, 4], [0, 4]]}, doc["rooms"][1]]
    model = _doc_with(model, rooms=rooms)
    assert (
        _refusal(model, "E2", "SW2", "centre") == "No pipe of this circuit in or next to this room."
    )


def test_sv19_the_branch_does_not_end_at_a_junction() -> None:
    model = _with(two_rooms(), E4={"kind": "valve", "group": "flow_controller"})
    assert _refusal(model, "E2", "SW2", "centre") == (
        "Its branch does not end at a junction: a valve or equipment is in the way."
    )


def test_sv19_supply_and_return_would_cross(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(edit, "reroute", lambda *a, **k: "cross")  # geometry: test_services_route
    assert _refusal(two_rooms(), "E2", "SW2", "centre") == "Supply and return would cross."


# --- SV-20 flags, SV-21 checks -------------------------------------------------------------------


def test_sv20_every_move_says_sizes_are_copied_and_a_long_reroute_is_flagged() -> None:
    change = move_terminal(two_rooms(), "E2", "SW2", "centre")
    codes = {f.code for f in change.flags}
    assert "not_sized" in codes and "long_reroute" in codes
    long = next(f.text for f in change.flags if f.code == "long_reroute")
    assert long.startswith("Long reroute: ") and " m of new pipe replaces " in long


def test_sv21_a_move_passes_every_check() -> None:
    change = move_terminal(two_rooms(), "E2", "SW2", "centre")
    assert {c.code for c in change.checks} >= {
        "connected", "same_equipment", "others_unchanged", "no_orphans", "open_ports",
        "no_cross", "no_door",
    }  # fmt: skip
    assert all(c.ok for c in change.checks), [c for c in change.checks if not c.ok]


def test_sv21_a_change_that_would_disconnect_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(edit, "_connect", lambda work, a, b: None)  # the new runs stay loose
    with pytest.raises(EditRefusedError, match=r"^The reroute would disconnect"):
        move_terminal(two_rooms(), "E2", "SW2", "centre")

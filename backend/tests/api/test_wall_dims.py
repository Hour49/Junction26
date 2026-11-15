"""A wall's length and thickness as drawn (big QA R1 edits rows 1a/23/38, pic-sync, 2026-11-15): the
sample's W1 card said "Removed: Wall W1, 2.5 m, 0.1 m thick" while the sheet draws the wall 3 m long
and 0.12 m thick with a 1 m door in it (the card's own +0.36 m² is 3 x 0.12). Its strip of wall
mass is two pieces (the door gap splits it) plus zero-area slivers, and one rectangle from the
whole strip's area and perimeter read 2.50 x 0.096. Each piece is measured alone and the door
opening along the wall counts in its length."""

import pytest
from fastapi.testclient import TestClient
from swiss_walls import walled_flat
from test_plan_tools import call, client, rooms_by_label, upload  # noqa: F401


def test_the_inside_wall_with_its_door_is_3_m_by_0_12(client: TestClient) -> None:  # noqa: F811
    store, drawing_id = upload(client, walled_flat())
    walls = call(store, "list_walls", drawing_id=drawing_id, page=1)
    inside = next(w for w in walls["walls"] if len(w["doors"]) == 1)
    assert inside["length_m"] == pytest.approx(3.0, abs=0.05), inside
    assert inside["thickness_m"] == pytest.approx(0.12, abs=0.005), inside
    labels = rooms_by_label(walls)
    found = call(
        store, "propose_remove_wall", drawing_id=drawing_id, page=1,
        room_a=labels["Bagno 1.01"], room_b=labels["Stanza 1.02"],
    )  # fmt: skip
    said = [item["label"] for item in found["proposal"]["removed"]]
    assert said[0] == "Wall W1, 3.0 m, 0.12 m thick", said


def test_a_wall_without_a_door_is_its_mass(client: TestClient) -> None:  # noqa: F811
    """The façade wall to the balcony: one piece, its 0.2 m drawn thickness (main: 0.19)."""
    store, drawing_id = upload(client, walled_flat())
    walls = call(store, "list_walls", drawing_id=drawing_id, page=1)
    by_rooms = {frozenset(r["label"] for r in w["rooms"]): w for w in walls["walls"]}
    bagno = by_rooms[frozenset({"Bagno 1.01", "Balcone 1.03"})]
    assert bagno["doors"] == [] and bagno["thickness_m"] == pytest.approx(0.2, abs=0.005), bagno
    assert bagno["length_m"] == pytest.approx(3.0, abs=0.05), bagno

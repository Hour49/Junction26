"""PLAN_TOOLS (spec agent-chat AC-12, AC-16..AC-21): walls with ids, proposals computed from the
drawing's geometry, and a bad call or an uneditable plan as JSON, never an exception."""

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from swiss_walls import walled_flat

from app.adapters.plan_tools import ONE_AT_A_TIME, PLAN_TOOLS, PlanStore, run_plan_tool
from app.composition import build_ingest
from app.core.plan_edit.model import Selection
from app.main import create_app
from app.settings import Settings

FLOOR = (
    Path(__file__).parents[3]
    / "data/stoa/full/junction-dataset/data/swiss_dwellings/site980_bldg2055_floor9178.pdf"
)


@pytest.fixture
def client(settings: Settings) -> TestClient:
    return TestClient(
        create_app(settings, build_ingest(settings, settings.projects_dir, background=False))
    )


def upload(client: TestClient, pdf: bytes, name: str = "flat.pdf") -> tuple[PlanStore, str]:
    pid = client.post("/api/projects", params={"name": name}, content=pdf).json()["id"]
    drawing_id = client.get(f"/api/projects/{pid}").json()["drawings"][0]["drawing_id"]
    return PlanStore.of_app(client.app, pid), drawing_id


def call(store: PlanStore, tool: str, **arguments: object) -> Any:
    return json.loads(run_plan_tool(store, tool, json.dumps(arguments)))


def rooms_by_label(found: dict[str, Any]) -> dict[str, str]:
    return {room["label"]: room["id"] for room in found["rooms"]}


def test_every_plan_tool_is_an_openai_function() -> None:
    names = [tool["function"]["name"] for tool in PLAN_TOOLS]
    assert names == ["list_walls", "propose_remove_wall", "propose_room"]
    for tool in PLAN_TOOLS:
        assert tool["type"] == "function"
        assert tool["function"]["parameters"]["additionalProperties"] is False


def test_ac16_list_walls_gives_the_inside_wall_its_rooms_and_its_door(client: TestClient) -> None:
    store, drawing_id = upload(client, walled_flat())
    found = call(store, "list_walls", drawing_id=drawing_id, page=1)
    assert found["status"] == "ok"
    labels = rooms_by_label(found)
    assert set(labels) == {"Bagno 1.01", "Stanza 1.02", "Balcone 1.03"}
    inside = next(
        w
        for w in found["walls"]
        if {r["label"] for r in w["rooms"]} == {"Bagno 1.01", "Stanza 1.02"}
    )
    assert inside["thickness_m"] == pytest.approx(0.12, abs=0.02)
    assert len(inside["doors"]) == 1 and inside["load_bearing"] == "unknown"
    assert inside["page"] == 1 and len(inside["box"]) == 4  # AC-5: the loop can mint evidence


def test_ac17_ac21_removing_the_wall_is_a_proposal_the_store_keeps(client: TestClient) -> None:
    store, drawing_id = upload(client, walled_flat())
    walls = call(store, "list_walls", drawing_id=drawing_id, page=1)
    labels = rooms_by_label(walls)
    found = call(
        store, "propose_remove_wall", drawing_id=drawing_id, page=1,
        room_a=labels["Bagno 1.01"], room_b=labels["Stanza 1.02"],
    )  # fmt: skip
    assert found["status"] == "ok"
    proposal = found["proposal"]
    assert proposal["proposal_id"] == "p1" and proposal["state"] == "proposed"
    (merged,) = proposal["rooms"]
    assert merged["label"] == "Bagno 1.01 + Stanza 1.02"
    assert merged["area_before_m2"] == pytest.approx(9 + 11.66, abs=0.05)
    assert merged["area_after_m2"] == pytest.approx(9 + 11.66 + 0.36, abs=0.05)
    assert [item["label"] for item in proposal["removed"]][-1] == "door, no longer needed"
    assert {flag["code"] for flag in proposal["flags"]} == {"structural", "wet_room"}
    assert [p.proposal_id for p in store.proposals] == ["p1"]
    wall = next(w["id"] for w in walls["walls"] if len(w["doors"]) == 1)
    by_id = {"drawing_id": drawing_id, "page": 1, "wall_id": wall}
    # edits-1: one proposal per turn; the next turn's store numbers on from the chat's
    assert call(store, "propose_remove_wall", **by_id) == {
        "status": "refused", "reason": ONE_AT_A_TIME
    }  # fmt: skip
    next_turn = PlanStore(store.pipeline, {}, list(store.proposals))
    again = call(next_turn, "propose_remove_wall", **by_id)
    assert again["proposal"]["rooms"] == proposal["rooms"]  # by its id, the same edit
    assert [p.proposal_id for p in next_turn.proposals] == ["p1", "p2"]


def test_ac17_the_façade_pair_is_refused(client: TestClient) -> None:
    store, drawing_id = upload(client, walled_flat())
    labels = rooms_by_label(call(store, "list_walls", drawing_id=drawing_id, page=1))
    found = call(
        store, "propose_remove_wall", drawing_id=drawing_id, page=1,
        room_a=labels["Bagno 1.01"], room_b=labels["Balcone 1.03"],
    )  # fmt: skip
    assert found["status"] == "refused" and "façade" in found["reason"]
    assert store.proposals == []


def test_ac18_ac12_a_room_in_the_drawn_area(client: TestClient) -> None:
    store, drawing_id = upload(client, walled_flat())
    page = call(store, "list_walls", drawing_id=drawing_id, page=1)
    stanza = next(r for r in page["rooms"] if r["label"] == "Stanza 1.02")
    x0, y0, x1, y1 = stanza["box"]
    region = (x0 + (x1 - x0) * 0.5, y0 + 0.002, x1 - 0.002, y0 + (y1 - y0) * 0.5)
    selection = Selection(id="sel_1", kind="region", drawing_id=drawing_id, page=1, box=region)
    store.selections[selection.id] = selection
    line = store.describe(selection)
    assert line.startswith("sel_1: region on ") and "overlaps Stanza 1.02 (100%)" in line
    found = call(store, "propose_room", selection_id="sel_1", name="Ripostiglio")
    assert found["status"] == "ok"
    new, shrunk = found["proposal"]["rooms"][:2]
    assert new["label"] == "Ripostiglio" and shrunk["label"] == "Stanza 1.02"
    assert shrunk["area_after_m2"] < shrunk["area_before_m2"] and found["proposal"]["added"]


def test_ac12_a_picked_room_is_described_with_its_area(client: TestClient) -> None:
    store, drawing_id = upload(client, walled_flat())
    labels = rooms_by_label(call(store, "list_walls", drawing_id=drawing_id, page=1))
    picked = Selection(
        id="sel_2", kind="room", drawing_id=drawing_id, page=1, ref=labels["Bagno 1.01"]
    )
    assert store.describe(picked).startswith(
        f"sel_2: room {labels['Bagno 1.01']} Bagno 1.01 (9.00 m²) on "
    )
    with_no_room = picked.model_copy(update={"drawing_id": "0" * 16})
    assert "does not have" in store.describe(with_no_room)


def test_ac16_a_plan_without_wall_fills_cannot_be_edited(client: TestClient) -> None:
    from test_vector_pdf import swiss_sheet  # rooms, but no grey wall fills

    store, drawing_id = upload(client, swiss_sheet().pdf())
    found = call(store, "list_walls", drawing_id=drawing_id, page=1)
    assert found == {
        "status": "cannot_edit",
        "reason": "no walls are drawn as geometry on this page",
    }


@pytest.mark.parametrize(
    ("name", "arguments", "says"),
    [
        ("nope", "{}", "unknown tool"),
        ("list_walls", "{not json", "not valid JSON"),
        ("list_walls", '{"drawing_id": "x", "page": 1}', "bad arguments"),
        (
            "list_walls",
            '{"drawing_id": "0000000000000000", "page": 1, "extra": 1}',
            "bad arguments",
        ),
        ("propose_remove_wall", '{"drawing_id": "0000000000000000", "page": 1}', "name the wall"),
        ("propose_room", '{"selection_id": "sel_9", "name": "Box"}', "no selection sel_9"),
    ],
)
def test_a_bad_call_is_an_error_not_an_exception(
    client: TestClient, name: str, arguments: str, says: str
) -> None:
    store, _ = upload(client, walled_flat())
    assert says in json.loads(run_plan_tool(store, name, arguments))["error"]


@pytest.fixture
def floor(client: TestClient) -> tuple[PlanStore, str, dict[str, Any]]:
    if not FLOOR.exists():
        pytest.skip("the dataset is not on this machine")
    store, drawing_id = upload(client, FLOOR.read_bytes(), FLOOR.name)
    return store, drawing_id, call(store, "list_walls", drawing_id=drawing_id, page=1)


def test_ac16_floor9178_the_bagno_stanza_wall_has_its_door(
    floor: tuple[PlanStore, str, dict[str, Any]],
) -> None:
    _, _, found = floor
    (wall,) = [
        w
        for w in found["walls"]
        if {r["label"] for r in w["rooms"]} == {"Bagno 1.01", "Stanza 1.02"}
    ]
    assert wall["doors"] == ["e6"] and wall["thickness_m"] == pytest.approx(0.12, abs=0.01)
    assert wall["length_m"] == pytest.approx(3.6, abs=0.1)  # L-shaped round the shaft
    assert len(found["walls"]) == 12 and len(found["rooms"]) == 10


def test_ac17_floor9178_bagno_and_stanza_merge(
    floor: tuple[PlanStore, str, dict[str, Any]],
) -> None:
    store, drawing_id, walls = floor
    labels = rooms_by_label(walls)
    found = call(
        store, "propose_remove_wall", drawing_id=drawing_id, page=1,
        room_a=labels["Bagno 1.01"], room_b=labels["Stanza 1.02"],
    )  # fmt: skip
    (merged,) = found["proposal"]["rooms"]
    assert merged["area_before_m2"] == pytest.approx(24.04, abs=0.02)
    # the removed wall stops at the two rooms' faces (decision 0013: 24.56 m²)
    assert merged["area_after_m2"] == pytest.approx(24.56, abs=0.05)


def test_ac18_floor9178_a_storage_room_in_the_largest_room(
    floor: tuple[PlanStore, str, dict[str, Any]],
) -> None:
    store, drawing_id, walls = floor
    big = max(walls["rooms"], key=lambda r: r["area_m2"])
    assert big["label"] == "Stanza 1.07"
    x0, y0, x1, y1 = big["box"]
    region = (x0 + (x1 - x0) * 0.55, y0 + 0.002, x1 - 0.002, y0 + (y1 - y0) * 0.45)
    store.selections["sel_1"] = Selection(
        id="sel_1", kind="region", drawing_id=drawing_id, page=1, box=region
    )
    found = call(store, "propose_room", selection_id="sel_1", name="Ripostiglio")
    new, shrunk = found["proposal"]["rooms"]
    assert (new["label"], shrunk["label"]) == ("Ripostiglio", "Stanza 1.07")
    assert new["area_after_m2"] == pytest.approx(3.84, abs=0.05)
    assert shrunk["area_before_m2"] == pytest.approx(19.98, abs=0.02)
    assert shrunk["area_after_m2"] == pytest.approx(15.73, abs=0.05)
    assert len(found["proposal"]["added"]) == 1  # one L-shaped partition, 0.10 m thick
    taken = shrunk["area_before_m2"] - shrunk["area_after_m2"] - new["area_after_m2"]
    assert taken == pytest.approx(0.41, abs=0.03)


CANNOT = [
    ("scans/ground-floor.png", "cannot_edit", "this plan is a scan: its walls are not geometry"),
    ("photos/plan-photo.jpg", "cannot_edit", "this plan is a photo: its walls are not geometry"),
    ("plans/flat-a.pdf", "cannot_edit", "no walls are drawn as geometry on this page"),
    ("model/house.ifc", "cannot_edit", "this building model has no drawn plan to edit"),
]


def every_tool(store: PlanStore, drawing_id: str) -> list[Any]:
    """Each plan tool called on page 1 of the drawing."""
    store.selections["sel_1"] = Selection(
        id="sel_1", kind="region", drawing_id=drawing_id, page=1, box=(0.2, 0.2, 0.4, 0.4)
    )
    return [
        call(store, "list_walls", drawing_id=drawing_id, page=1),
        call(store, "propose_remove_wall", drawing_id=drawing_id, page=1, room_a="r1", room_b="r2"),
        call(store, "propose_room", selection_id="sel_1", name="Storage"),
    ]


@pytest.mark.parametrize(("file", "status", "reason"), CANNOT)
def test_ac16_a_plan_that_cannot_be_edited_says_why_in_every_tool(
    client: TestClient, file: str, status: str, reason: str
) -> None:
    project = client.get(client.post("/api/projects/sample").json()["url"]).json()
    store = PlanStore.of_app(client.app, project["id"])
    drawing_id = next(d["drawing_id"] for d in project["drawings"] if d["file"] == file)
    assert every_tool(store, drawing_id) == [{"status": status, "reason": reason}] * 3
    assert store.proposals == []


def test_spec_2_4_a_drawing_without_scale_is_unknown_in_every_tool(client: TestClient) -> None:
    store, drawing_id = upload(client, walled_flat(scale=False))
    unknown = {"status": "unknown", "reason": "this drawing has no scale"}
    assert every_tool(store, drawing_id) == [unknown] * 3


def test_ac12_a_room_click_without_ref_is_the_room_under_its_centre(client: TestClient) -> None:
    store, drawing_id = upload(client, walled_flat())
    page = call(store, "list_walls", drawing_id=drawing_id, page=1)
    bagno = next(r for r in page["rooms"] if r["label"] == "Bagno 1.01")
    x0, y0, x1, y1 = bagno["box"]
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    click = Selection(
        id="sel_1", kind="room", drawing_id=drawing_id, page=1, box=(cx, cy, cx + 0.001, cy + 0.001)
    )
    assert store.describe(click).startswith(f"sel_1: room {bagno['id']} Bagno 1.01 (9.00 m²)")
    store.selections[click.id] = click
    found = call(store, "propose_room", selection_id="sel_1", name="Box")
    assert found["status"] == "refused" and f"sel_1 is {bagno['id']} Bagno 1.01" in found["reason"]
    outside = click.model_copy(update={"id": "sel_2", "box": (0.01, 0.01, 0.02, 0.02)})
    assert store.describe(outside).endswith("that is in no room")
    store.selections[outside.id] = outside
    found = call(store, "propose_room", selection_id="sel_2", name="Box")
    assert "sel_2 is a click in no room" in found["reason"]


def region(store: PlanStore, drawing_id: str, box: tuple[float, ...], page: int = 1) -> None:
    store.selections["sel_1"] = Selection.model_validate(
        {"id": "sel_1", "kind": "region", "drawing_id": drawing_id, "page": page, "box": box}
    )


def test_edits_1_a_second_proposal_in_one_turn_is_refused(client: TestClient) -> None:
    store, drawing_id = upload(client, walled_flat())
    stanza = rooms_by_box(call(store, "list_walls", drawing_id=drawing_id, page=1))["Stanza 1.02"]
    x0, y0, x1, y1 = stanza
    region(store, drawing_id, (x0 + (x1 - x0) / 2, y0, x1, y0 + (y1 - y0) / 2))
    assert call(store, "propose_room", selection_id="sel_1", name="Box")["status"] == "ok"
    second = call(store, "propose_room", selection_id="sel_1", name="Box")
    assert second == {"status": "refused", "reason": ONE_AT_A_TIME}
    assert len(store.proposals) == 1


def rooms_by_box(found: dict[str, Any]) -> dict[str, tuple[float, ...]]:
    return {room["label"]: tuple(room["box"]) for room in found["rooms"]}


def test_robust_1_a_sideways_drag_is_a_line_not_an_area(client: TestClient) -> None:
    store, drawing_id = upload(client, walled_flat())
    x0, y0, x1, y1 = rooms_by_box(call(store, "list_walls", drawing_id=drawing_id, page=1))[
        "Stanza 1.02"
    ]  # fmt: skip
    region(store, drawing_id, (x0, (y0 + y1) / 2, x1, (y0 + y1) / 2))
    assert store.describe(store.selections["sel_1"]).endswith("page 1, not an area")
    found = call(store, "propose_room", selection_id="sel_1", name="Box")
    assert found["status"] == "refused" and "a line, not an area" in found["reason"]


def test_edits_4_a_small_area_is_too_small_not_outside(client: TestClient) -> None:
    store, drawing_id = upload(client, walled_flat())
    x0, y0, x1, y1 = rooms_by_box(call(store, "list_walls", drawing_id=drawing_id, page=1))[
        "Stanza 1.02"
    ]  # fmt: skip
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    region(store, drawing_id, (cx, cy, cx + 0.01, cy + 0.01))  # about 0.2 x 0.1 m
    found = call(store, "propose_room", selection_id="sel_1", name="Box")
    assert found == {
        "status": "refused",
        "reason": "the area is too small for a room (under 0.5 m²): draw a larger area",
    }


def test_edits_7_refusals_name_no_raw_ids(client: TestClient) -> None:
    store, drawing_id = upload(client, walled_flat())
    region(store, drawing_id, (0.3, 0.3, 0.4, 0.4), page=2)
    on_page_2 = call(store, "propose_room", selection_id="sel_1", name="Box")
    assert on_page_2 == {"error": "Drawn plan 1 has no page 2"}
    region(store, "f" * 16, (0.3, 0.3, 0.4, 0.4))
    elsewhere = call(store, "propose_room", selection_id="sel_1", name="Box")
    assert elsewhere == {
        "error": "this project has no such drawing: it may have been uploaded again"
    }
    assert "f" * 16 not in store.describe(store.selections["sel_1"])


def test_list_walls_between_two_rooms_gives_only_the_walls_they_share(client: TestClient) -> None:
    """A filtered query (chat-eval 2026-11-14): on a big plan the cut list may not hold it."""
    store, drawing_id = upload(client, walled_flat())
    whole = call(store, "list_walls", drawing_id=drawing_id, page=1)
    labels = rooms_by_label(whole)
    bagno, stanza = labels["Bagno 1.01"], labels["Stanza 1.02"]
    found = call(store, "list_walls", drawing_id=drawing_id, page=1, room_a=bagno, room_b=stanza)
    assert [{r["id"] for r in w["rooms"]} for w in found["walls"]] == [{bagno, stanza}]
    assert found["rooms"] == whole["rooms"]
    one = call(store, "list_walls", drawing_id=drawing_id, page=1, room_a=bagno)
    assert one["walls"] and all(bagno in {r["id"] for r in w["rooms"]} for w in one["walls"])
    unknown = call(store, "list_walls", drawing_id=drawing_id, page=1, room_a="R99")
    assert "R99" in unknown["error"]

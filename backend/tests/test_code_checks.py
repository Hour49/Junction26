"""Building-code pre-checks (decision 0009): the pack loader refuses a rule nobody can trace to a
clause, and each op gives pass, fail or cannot tell, never a guess. On the TEST pack
(tests/fixtures/rules/test.json): its rules are made up, its clauses point nowhere real."""

import json
from pathlib import Path
from typing import Any

import pytest

from app.adapters.rule_packs import load_packs
from app.core.checks import check as engine
from app.core.checks.check import overall
from app.core.checks.model import AppliesTo, CodeRule, RuleCheck, RulePack
from app.core.drawing.model import (
    Conflict,
    Drawing,
    MeasuredValue,
    Page,
    Scale,
    ScaleStatus,
    Subject,
)
from app.core.errors import InvalidInputError
from app.core.pipeline.model import Route
from app.settings import Settings

RULES = Path(__file__).parent / "fixtures" / "rules"
PACK = load_packs(RULES)[0]
# A 10 m x 10 m page at 1 cm per unit: a fraction 0.1 is 1 m.
PAGE = Page(page=1, width=1000, height=1000, unit="pt")
SCALED = Scale(status="scaled", m_per_unit=0.01)


def check_rule(*args: Any, route: Route | None = "vector", **more: Any) -> RuleCheck:
    """The engine's check_rule on a drawing read off its lines unless `route` says otherwise:
    the engine takes an unknown route as a picture (S2)."""
    return engine.check_rule(*args, route=route, **more)


def check_drawing(*args: Any, route: Route | None = "vector", **more: Any) -> tuple[RuleCheck, ...]:
    return engine.check_drawing(*args, route=route, **more)


def rule(rule_id: str) -> CodeRule:
    return next(found for found in PACK.rules if found.id == f"test-{rule_id}")


def drawing(*, scale: Scale = SCALED, **items: Any) -> Drawing:
    return Drawing.model_validate(
        {"file": "data/x/plan.pdf", "pages": [PAGE], "scale": scale, **items}
    )


def room(n: int, kind: str = "bedroom", box: tuple[float, ...] = (0.1, 0.1, 0.4, 0.4), **more: Any):
    return {"id": f"r{n}", "type": kind, "page": 1, "box": box, "label": f"MH {n}", **more}


def element(n: int, cls: str, box: tuple[float, ...], **more: Any) -> dict[str, Any]:
    return {"id": f"e{n}", "class": cls, "page": 1, "box": box, **more}


def statuses(found: Any) -> list[str]:
    return [result.status for result in found.results]


# --- the loader -----------------------------------------------------------------------------


def pack_json(**rule_changes: Any) -> dict[str, Any]:
    body = json.loads((RULES / "test.json").read_text())
    body["rules"][0].update(rule_changes)
    return body


def write(folder: Path, body: dict[str, Any], name: str = "test") -> Path:
    (folder / f"{name}.json").write_text(json.dumps(body))
    return folder


def test_the_test_pack_loads_with_its_four_ops() -> None:
    assert PACK.id == "test"
    assert [found.op for found in PACK.rules] == [
        "room_area",
        "room_windows",
        "door_width",
        "takeoff",
    ]


@pytest.mark.parametrize("field", ["quote", "url", "ref"])
def test_a_rule_without_its_clause_stops_the_load(tmp_path: Path, field: str) -> None:
    body = pack_json()
    del body["rules"][0]["clause"][field]
    with pytest.raises(InvalidInputError, match=rf"(?s)test\.json.*clause\.{field}"):
        load_packs(write(tmp_path, body))


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"clause": {"ref": "x", "url": "http://example.org", "quote": "q"}}, "url"),
        ({"clause": {"ref": "x", "url": "https://example.org", "quote": ""}}, "quote"),
        ({"op": "stair_width"}, "op"),
        ({"applies_to": {"room_types": []}}, "room_types only"),
        (
            {"applies_to": {"room_types": ["bedroom"], "element_classes": ["door"]}},
            "room_types only",
        ),
        ({"applies_to": {"room_types": ["dungeon"]}}, "room_types"),
        ({"unit": "m"}, "room_area  is in m2"),
        ({"comparison": "=="}, "comparison"),
        ({"key": "door"}, "a key is for the takeoff op"),
    ],
)
def test_a_rule_that_does_not_fit_its_op_stops_the_load(
    tmp_path: Path, change: dict[str, Any], message: str
) -> None:
    with pytest.raises(InvalidInputError, match=message):
        load_packs(write(tmp_path, pack_json(**change)))


def test_a_takeoff_rule_needs_its_keys_unit_and_door_width_a_minimum() -> None:
    clause = {"ref": "x", "url": "https://example.org", "quote": "q"}
    base = {"id": "r", "title": "t", "comparison": ">=", "limit": 1, "clause": clause}
    with pytest.raises(ValueError, match="is in m2"):
        CodeRule.model_validate(
            {**base, "op": "takeoff", "key": "area:room|indoor", "unit": "count"}
        )
    with pytest.raises(ValueError, match="a key is for the takeoff op"):
        CodeRule.model_validate({**base, "op": "takeoff", "unit": "count"})
    doors = {"element_classes": ["door"]}
    with pytest.raises(ValueError, match="minimum"):
        CodeRule.model_validate(
            {**base, "op": "door_width", "unit": "m", "comparison": "<=", "applies_to": doors}
        )
    for wrong in ({}, {"element_classes": ["window"]}, {"room_types": ["wc"]}):
        with pytest.raises(ValueError, match=r"element_classes \[door\]"):
            CodeRule.model_validate({**base, "op": "door_width", "unit": "m", "applies_to": wrong})
    found = CodeRule.model_validate(
        {**base, "op": "takeoff", "key": "area:room|indoor", "unit": "m2"}
    )
    assert found.unit == "m2"


def test_repeated_rule_ids_and_a_misnamed_file_stop_the_load(tmp_path: Path) -> None:
    body = pack_json()
    body["rules"][1]["id"] = body["rules"][0]["id"]
    with pytest.raises(InvalidInputError, match="repeat"):
        load_packs(write(tmp_path, body))
    other = tmp_path / "other"
    other.mkdir()
    with pytest.raises(InvalidInputError, match="its id is 'test'"):
        load_packs(write(other, pack_json(), name="fi"))


def test_no_folder_has_no_packs(tmp_path: Path) -> None:
    assert load_packs(tmp_path / "missing") == ()


def test_every_pack_shipped_loads() -> None:
    """The packs the app serves (RULE_PACKS_DIR's default) all validate."""
    for pack in load_packs(Settings.model_fields["rule_packs_dir"].default):
        assert isinstance(pack, RulePack)


# --- room_area ------------------------------------------------------------------------------


def test_room_area_passes_and_fails_per_room_with_its_mark() -> None:
    found = check_rule(
        drawing(rooms=[room(1, area_m2=9.5), room(2, "living", area_m2=6.1), room(3, "kitchen")]),
        rule("bedroom-area"),
    )
    assert statuses(found) == ["pass", "fail"]  # the kitchen is not checked
    assert found.status == "fail"
    failed = found.results[1]
    assert failed.id == "test-bedroom-area:r2"
    assert failed.value == 6.1
    assert failed.why == 'The living room "MH 2" is 6.1 m2; the rule asks at least 7 m2.'
    assert [(mark.ref, mark.role, mark.box) for mark in failed.marks] == [
        ("r2", "subject", (0.1, 0.1, 0.4, 0.4))
    ]
    # its takeoff row is its own area by name, and it is that row's only mark
    assert (failed.quantity, failed.marks[0].quantity) == ("area:room|name=mh 2",) * 2
    assert failed.marks[0].mark_id == "m1"
    assert (failed.comparison, failed.comparison_text) == (">=", "at least")
    assert found.why == "Of 2 checked: 1 fail, 1 pass."


def test_a_dining_nook_typed_living_is_skipped_by_its_label() -> None:
    """Guard 1: CubiCasa types dining areas `living` (labels R, RT, RUOK...); they are not rooms
    of their own. The pack lists the labels; case and spaces don't matter."""
    dining = rule("bedroom-area").model_copy(
        update={
            "applies_to": AppliesTo(room_types=("bedroom", "living"), skip_labels=("RT", "Essen"))
        }
    )
    nook = room(1, "living", area_m2=5.0, label=" rt ")
    essen = room(2, "living", area_m2=4.0, label="ESSEN")
    lounge = room(3, "living", area_m2=5.0, label="OH")
    found = check_rule(drawing(rooms=[nook, essen, lounge]), dining)
    assert [(result.subject.ref, result.status) for result in found.results] == [("r3", "fail")]


def test_a_room_without_an_area_cannot_tell() -> None:
    found = check_rule(drawing(rooms=[room(1)]), rule("bedroom-area"))
    assert statuses(found) == ["cannot_tell"]
    assert found.results[0].value is None
    assert "has no area" in found.results[0].why


@pytest.mark.parametrize(
    ("area", "spread", "status"),
    [
        (6.5, 0.10, "cannot_tell"),
        (7.5, 0.10, "cannot_tell"),
        (9.0, 0.10, "pass"),
        (5.0, 0.10, "cannot_tell"),  # clear of the band, but an estimate never fails
    ],
)
def test_an_estimated_area_passes_only_clear_of_its_band_and_never_fails(
    area: float, spread: float, status: str
) -> None:
    estimated = room(1, area_m2=area, area_status="estimated", area_uncertainty=spread)
    found = check_rule(drawing(rooms=[estimated]), rule("bedroom-area"))
    assert statuses(found) == [status]
    assert found.results[0].value == area
    assert "±10%" in found.results[0].why or "its area is an estimate" in found.results[0].why


@pytest.mark.parametrize(
    ("source", "area", "status"),
    [(None, 5.0, "cannot_tell"), ("geometry_x_scale", 5.0, "cannot_tell"),
     ("printed", 5.0, "fail"), (None, 9.0, "pass")],
)  # fmt: skip
def test_off_a_picture_only_a_printed_area_fails(
    source: str | None, area: float, status: str
) -> None:
    """Reliable inputs only (orchestrator 12:51): on the raster route none of 9 dev area fails
    from read outlines was real; a printed area still decides, a pass still stands."""
    read = room(1, area_m2=area, area_source=source)
    found = check_rule(drawing(rooms=[read]), rule("bedroom-area"), route="raster")
    assert statuses(found) == [status]
    if status == "cannot_tell":
        assert found.results[0].why == (
            'The bedroom "MH 1" is about 5 m2 and the rule asks at least 7 m2, but its area was '
            "read off a picture, not printed, so a fail cannot be told."
        )
    # the same room on a drawn (vector) sheet fails on its outline
    if area < 7:
        assert statuses(check_rule(drawing(rooms=[read]), rule("bedroom-area"))) == ["fail"]


def test_an_estimated_area_with_no_stated_error_cannot_tell() -> None:
    estimated = room(1, area_m2=20.0, area_status="estimated")
    assert statuses(check_rule(drawing(rooms=[estimated]), rule("bedroom-area"))) == ["cannot_tell"]


def test_no_room_of_the_types_is_not_applicable_with_no_results() -> None:
    found = check_rule(
        drawing(rooms=[room(1, "kitchen", area_m2=3.0), room(2, area_m2=3.0, outdoor=True)]),
        rule("bedroom-area"),
    )
    assert (found.status, found.results) == ("not_applicable", ())
    assert found.why == "The drawing shows no bedroom or living room, so there is nothing to check."


def test_rooms_not_read_cannot_tell() -> None:
    found = check_rule(drawing(read=["door", "window"]), rule("bedroom-area"))
    assert (found.status, found.results) == ("cannot_tell", ())
    assert found.why == "No rooms were read on this drawing, so it cannot be checked."


def test_a_drawing_that_reads_nothing_cannot_tell_any_rule() -> None:
    found = check_drawing(drawing(scale=Scale(status="no_scale"), read=[]), PACK)
    assert [check.status for check in found] == ["cannot_tell"] * 4


def test_a_drawing_of_totals_only_cannot_tell_a_room_rule() -> None:
    found = check_rule(drawing(counts={"room:bedroom": 2}), rule("bedroom-area"))
    assert found.why.startswith("The drawing gives totals only")


# --- room_windows ---------------------------------------------------------------------------

# Bedroom r1 is x 1-4 m, y 1-4 m. A window in its outer wall at x = 1 m sits just outside it.
ON_WALL = (0.08, 0.2, 0.1, 0.3)  # centre 0.1 m left of the outline
FAR = (0.6, 0.6, 0.62, 0.7)  # 2 m from it


def test_a_window_on_the_rooms_outline_counts_and_one_far_off_does_not() -> None:
    plan = drawing(
        rooms=[room(1), room(2, box=(0.5, 0.5, 0.9, 0.9))],
        elements=[element(1, "window", ON_WALL), element(2, "window", FAR)],
    )
    found = check_rule(plan, rule("bedroom-window"))
    assert statuses(found) == ["pass", "pass"]
    first = found.results[0]
    assert first.value == 1
    assert [(mark.ref, mark.role) for mark in first.marks] == [("r1", "subject"), ("e1", "counted")]
    assert first.why == 'The bedroom "MH 1" has 1 window on its outline; the rule asks at least 1.'


def test_a_bedroom_with_no_window_fails() -> None:
    to_hall = element(3, "door", (0.2, 0.38, 0.27, 0.42))
    plan = drawing(rooms=[room(1), HALL], elements=[element(2, "window", FAR), to_hall])
    found = check_rule(plan, rule("bedroom-window"))
    assert statuses(found) == ["fail"]
    assert found.results[0].why.startswith('The bedroom "MH 1" has no window')


def test_a_window_follows_the_rooms_polygon_not_its_box() -> None:
    """An L-shaped room: a window by the box's empty corner is 1.5 m from the outline."""
    l_shape = room(
        1, polygon=[(0.1, 0.1), (0.4, 0.1), (0.4, 0.25), (0.25, 0.25), (0.25, 0.4), (0.1, 0.4)]
    )
    corner = element(1, "window", (0.38, 0.38, 0.4, 0.4))
    found = check_rule(drawing(rooms=[l_shape], elements=[corner]), rule("bedroom-window"))
    assert statuses(found) == ["fail"]


def test_a_window_on_another_page_does_not_count() -> None:
    page2 = Page(page=2, width=1000, height=1000, unit="pt")
    other = {**element(1, "window", ON_WALL), "page": 2}
    plan = drawing(rooms=[room(1)], elements=[other]).model_copy(update={"pages": (PAGE, page2)})
    assert statuses(check_rule(plan, rule("bedroom-window"))) == ["fail"]


def test_without_a_scale_the_slack_is_a_share_of_the_page() -> None:
    """1% of the long side: a window 0.5% off the outline counts, one 2% off does not."""
    near, off = (0.085, 0.2, 0.095, 0.3), (0.07, 0.2, 0.08, 0.3)
    for box, status in ((near, "pass"), (off, "fail")):
        plan = drawing(
            scale=Scale(status="no_scale"), rooms=[room(1)], elements=[element(1, "window", box)]
        )
        assert statuses(check_rule(plan, rule("bedroom-window"))) == [status]


def test_a_window_with_no_position_turns_a_fail_into_cannot_tell() -> None:
    unplaced = element(1, "window", (0.0, 0.0, 1.0, 1.0), attrs={"located": False})
    found = check_rule(drawing(rooms=[room(1)], elements=[unplaced]), rule("bedroom-window"))
    assert statuses(found) == ["cannot_tell"]
    assert found.results[0].value == 0
    assert "no position" in found.results[0].why


BALCONY = room(7, "balcony", box=(0.1, 0.4, 0.4, 0.5))  # below bedroom r1


def test_a_room_lit_only_through_a_balcony_door_cannot_tell() -> None:
    """Guard 4: Swiss plans draw glazed balcony doors as doors; a door that meets the room and a
    balcony may light it. A door to the hall does not."""
    to_balcony = element(1, "door", (0.2, 0.38, 0.27, 0.42))
    found = check_rule(
        drawing(rooms=[room(1), BALCONY], elements=[to_balcony]), rule("bedroom-window")
    )
    assert statuses(found) == ["cannot_tell"]
    assert "balcony" in found.results[0].why
    to_hall = drawing(rooms=[room(1), HALL], elements=[to_balcony])
    assert statuses(check_rule(to_hall, rule("bedroom-window"))) == ["fail"]


def test_a_room_with_a_door_straight_outside_cannot_tell() -> None:
    """Rule point 4 (13802: a glazed double door to the outside, no balcony room drawn): a door
    that meets the room and no other room opens to the outside."""
    out = element(1, "door", ON_WALL)
    found = check_rule(drawing(rooms=[room(1)], elements=[out]), rule("bedroom-window"))
    assert statuses(found) == ["cannot_tell"]
    assert "straight to the outside" in found.results[0].why


def test_off_a_picture_a_missing_window_cannot_tell_and_a_found_one_passes() -> None:
    to_hall = element(3, "door", (0.2, 0.38, 0.27, 0.42))
    bare = drawing(rooms=[room(1), HALL], elements=[to_hall])
    found = check_rule(bare, rule("bedroom-window"), route="raster")
    assert statuses(found) == ["cannot_tell"]
    assert found.results[0].why.endswith("but windows read from a picture can be missed.")
    lit = drawing(rooms=[room(1)], elements=[element(1, "window", ON_WALL)])
    assert statuses(check_rule(lit, rule("bedroom-window"), route="raster")) == ["pass"]


def test_window_fails_on_a_building_models_sheet_are_held() -> None:
    model = [{"id": "m1", "class": "space", "element": "r1"}]
    found = check_rule(drawing(rooms=[room(1)], model_objects=model), rule("bedroom-window"))
    assert statuses(found) == ["cannot_tell"]
    assert "building model" in found.results[0].why


@pytest.mark.parametrize(("windows", "status"), [(2, "pass"), (0, "fail")])
def test_a_building_models_window_count_decides(windows: int, status: str) -> None:
    """The model's count of a space's windows (attrs.windows, from the IFC adapter) decides; the
    marks are the windows drawn on the sheet, which may be fewer."""
    model = [{"id": "m1", "class": "space", "element": "r1", "attrs": {"windows": windows}}]
    plan = drawing(rooms=[room(1)], elements=[element(1, "window", ON_WALL)], model_objects=model)
    found = check_rule(plan, rule("bedroom-window"))
    assert statuses(found) == [status]
    result = found.results[0]
    assert result.value == windows
    assert [mark.ref for mark in result.marks] == ["r1", "e1"]
    assert f"the building model gives it {'2 windows' if windows else 'no window'}, 1 drawn" in (
        result.why
    )


@pytest.mark.parametrize(("doors", "status"), [([], "fail"), ([ON_WALL], "cannot_tell")])
def test_a_building_models_windowless_room_with_a_door_outside_cannot_tell(
    doors: list[tuple[float, float, float, float]], status: str
) -> None:
    """The model's 0 is held as a drawn 0 is (decision 0009, D511): tuwien's "Zimmer" rooms have
    no IfcWindow but a 2.36 m door straight to the outside, which may be glazed."""
    model = [{"id": "m1", "class": "space", "element": "r1", "attrs": {"windows": 0}}]
    out = [element(1, "door", box) for box in doors]
    plan = drawing(rooms=[room(1)], elements=out, model_objects=model)
    found = check_rule(plan, rule("bedroom-window"))
    assert statuses(found) == [status]
    assert found.results[0].value == 0
    if status == "cannot_tell":
        assert found.results[0].why.endswith(
            "the building model gives it no window, but a door opens from it straight to the "
            "outside, and that door may be glazed."
        )


def test_windows_link_to_their_marks_in_the_window_row() -> None:
    plan = drawing(
        rooms=[room(1)],
        elements=[element(1, "window", FAR), element(2, "window", ON_WALL)],
    )
    window = check_rule(plan, rule("bedroom-window")).results[0].marks[1]
    assert (window.ref, window.quantity, window.mark_id) == ("e2", "window", "m2")


def test_windows_not_read_cannot_tell() -> None:
    found = check_rule(drawing(rooms=[room(1)], read=["room", "door"]), rule("bedroom-window"))
    assert (found.status, found.why) == (
        "cannot_tell",
        "No windows were read on this drawing, so it cannot be checked.",
    )


# --- door_width -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("side_m", "status"),
    [
        (1.0, "pass"),
        (0.95, "cannot_tell"),
        (0.85, "cannot_tell"),
        (0.83, "cannot_tell"),
        (0.8, "fail"),
    ],
)
def test_a_door_symbol_bounds_its_clear_width_from_above(side_m: float, status: str) -> None:
    """The symbol measures the leaf: the clear opening is up to 10 cm less, and the box may be
    3 cm off: more than 3 cm below the limit fails, 13 cm above it passes."""
    door = element(1, "door", (0.5, 0.5, 0.5 + side_m / 10, 0.5 + side_m / 20))
    found = check_rule(drawing(elements=[door]), rule("door-width"))
    assert statuses(found) == [status]
    assert found.results[0].value == pytest.approx(side_m)
    assert found.results[0].id == "test-door-width:e1"


def test_a_door_on_an_estimated_scale_cannot_tell() -> None:
    """Guard 2: the raster route estimates the scale from the doors, so a door measured at it
    measures what the estimate assumed. Even a door far over the limit cannot tell."""
    door = element(1, "door", (0.5, 0.5, 0.65, 0.55))  # 1.5 m
    scale = Scale(status="estimated", m_per_unit=0.01, uncertainty=0.05)
    found = check_rule(drawing(elements=[door], scale=scale), rule("door-width"))
    assert statuses(found) == ["cannot_tell"]
    assert found.results[0].why.endswith("the scale was estimated from the doors.")


# Guard 3: a door counts only when it meets a habitable room and no closet, sauna, WC or bath.
SCOPED = rule("door-width").model_copy(
    update={
        "applies_to": AppliesTo(
            element_classes=("door",),
            room_types=("bedroom", "living", "kitchen"),
            not_room_types=("sauna", "storage", "shaft", "other", "wc", "bathroom"),
        )
    }
)
HALL = room(9, "hall", box=(0.1, 0.4, 0.4, 0.6))  # below bedroom r1 (y 0.1-0.4)
CLOSET = room(8, "storage", box=(0.4, 0.1, 0.5, 0.4))  # right of it


def test_only_doors_into_a_habitable_room_and_no_closet_are_checked() -> None:
    into_bedroom = element(1, "door", (0.2, 0.38, 0.27, 0.42))  # on the bedroom/hall wall: 0.7 m
    into_closet = element(2, "door", (0.38, 0.2, 0.42, 0.26))  # on the bedroom/closet wall
    hall_only = element(3, "door", (0.2, 0.55, 0.27, 0.6))  # inside the hall, far from both
    plan = drawing(rooms=[room(1), HALL, CLOSET], elements=[into_bedroom, into_closet, hall_only])
    found = check_rule(plan, SCOPED)
    assert [result.subject.ref for result in found.results] == ["e1"]
    assert statuses(found) == ["fail"]
    # unscoped (the TEST pack's rule), every door is checked
    assert len(check_rule(plan, rule("door-width")).results) == 3


def test_a_door_to_a_balcony_or_outdoors_is_not_checked() -> None:
    """Rule point 2: 20 of 26 Swiss door fails were balcony door leaves (a two-leaf door read
    as two). The pack lists balcony and outdoor in not_room_types; an outdoor flag counts too."""
    skips = SCOPED.model_copy(
        update={
            "applies_to": SCOPED.applies_to.model_copy(
                update={"not_room_types": ("balcony", "outdoor")}
            )
        }
    )
    leaf = element(1, "door", (0.2, 0.38, 0.27, 0.42))  # 0.7 m, bedroom to the room below
    for below in (room(7, "balcony", box=HALL["box"]), {**HALL, "outdoor": True}):
        found = check_rule(drawing(rooms=[room(1), below], elements=[leaf]), skips)
        assert (found.status, found.results) == ("not_applicable", ())
    assert statuses(check_rule(drawing(rooms=[room(1), HALL], elements=[leaf]), skips)) == ["fail"]


def test_off_a_picture_a_narrow_door_cannot_tell() -> None:
    narrow = element(1, "door", (0.5, 0.5, 0.57, 0.55))  # 0.7 m
    found = check_rule(drawing(elements=[narrow]), rule("door-width"), route="raster")
    assert statuses(found) == ["cannot_tell"]
    assert "read off a picture" in found.results[0].why


def test_no_door_into_a_habitable_room_is_not_applicable() -> None:
    to_closet = element(2, "door", (0.38, 0.2, 0.42, 0.26))
    found = check_rule(drawing(rooms=[room(1), CLOSET], elements=[to_closet]), SCOPED)
    assert (found.status, found.why) == (
        "not_applicable",
        "The drawing shows no door to a bedroom or living room or kitchen, so there is nothing "
        "to check.",
    )


def test_a_scoped_door_rule_without_rooms_read_cannot_tell() -> None:
    door = element(1, "door", (0.2, 0.38, 0.27, 0.42))
    found = check_rule(drawing(elements=[door], read=["door", "window"]), SCOPED)
    assert (found.status, found.results) == ("cannot_tell", ())


@pytest.mark.parametrize("status", ["no_scale", "not_to_scale"])
def test_a_door_without_a_scale_cannot_tell(status: ScaleStatus) -> None:
    door = element(1, "door", (0.5, 0.5, 0.6, 0.55))
    found = check_rule(drawing(elements=[door], scale=Scale(status=status)), rule("door-width"))
    assert statuses(found) == ["cannot_tell"]
    assert found.results[0].value is None
    assert "no scale" in found.results[0].why


def test_a_building_models_door_width_needs_no_scale() -> None:
    door = element(1, "door", (0.5, 0.5, 0.51, 0.51))
    model = [{"id": "m1", "class": "door", "element": "e1", "quantities": {"width_m": 0.7}}]
    plan = drawing(elements=[door], model_objects=model, scale=Scale(status="no_scale"))
    found = check_rule(plan, rule("door-width"))
    assert statuses(found) == ["fail"]
    assert "the building model gives 0.7 m" in found.results[0].why


def test_no_door_is_not_applicable() -> None:
    found = check_rule(drawing(), rule("door-width"))
    assert (found.status, found.why) == (
        "not_applicable",
        "The drawing shows no door, so there is nothing to check.",
    )


def test_a_door_counted_with_no_position_cannot_tell() -> None:
    """A second reader's door with the plan's box (attrs.located false) is not a 10 m door."""
    door = element(1, "door", (0.0, 0.0, 1.0, 1.0), attrs={"located": False})
    found = check_rule(drawing(elements=[door]), rule("door-width"))
    assert statuses(found) == ["cannot_tell"]
    assert found.results[0].value is None


def test_a_door_links_to_its_mark_in_the_door_row() -> None:
    doors = [element(1, "door", (0.2, 0.2, 0.3, 0.25)), element(2, "door", (0.5, 0.5, 0.6, 0.55))]
    second = check_rule(drawing(elements=doors), rule("door-width")).results[1]
    assert (second.quantity, second.marks[0].quantity, second.marks[0].mark_id) == (
        "door",
        "door",
        "m2",
    )


# --- takeoff --------------------------------------------------------------------------------


def test_a_takeoff_quantity_passes_or_fails_with_its_marks() -> None:
    passed = check_rule(drawing(rooms=[room(1, "wc")]), rule("wc-count"))
    assert statuses(passed) == ["pass"]
    assert passed.results[0].id == "test-wc-count:sheet"
    assert [(mark.role, mark.mark_id) for mark in passed.results[0].marks] == [("counted", "m1")]
    assert passed.results[0].quantity == "room:wc"
    failed = check_rule(drawing(rooms=[room(1)]), rule("wc-count"))
    assert (statuses(failed), failed.results[0].value) == (["fail"], 0)


def test_a_takeoff_quantity_the_drawing_lacks_cannot_tell() -> None:
    found = check_rule(drawing(read=["door"]), rule("wc-count"))  # rooms not read: no key
    assert statuses(found) == ["cannot_tell"]
    assert (
        found.results[0].why
        == "The drawing does not give the room wc count, so it cannot be checked."
    )


def test_a_takeoff_quantity_two_methods_dispute_cannot_tell() -> None:
    conflict = Conflict(
        id="c1",
        quantity="element_count",
        subject=Subject(kind="class", ref="room:wc"),
        status="conflict",
        tolerance=0,
        values=(
            MeasuredValue(value=0, method="parser"),
            MeasuredValue(value=1, method="detector"),
        ),
    )
    found = check_rule(drawing(rooms=[], conflicts=[conflict]), rule("wc-count"))
    assert statuses(found) == ["cannot_tell"]
    assert "no rule decides" in found.results[0].why


# --- together -------------------------------------------------------------------------------


def test_the_packs_fail_sentence_follows_each_fail_only() -> None:
    pack = PACK.model_copy(
        update={"fail_means": "It would not meet today's rule for a new building."}
    )
    plan = drawing(rooms=[room(1, area_m2=5.0), room(2, area_m2=9.0)])
    area = check_drawing(plan, pack)[0]
    assert area.results[0].why == (
        'The bedroom "MH 1" is 5 m2; the rule asks at least 7 m2. '
        "It would not meet today's rule for a new building."
    )
    assert area.results[1].why.endswith("at least 7 m2.")


def test_overall_status() -> None:
    assert overall(["pass", "cannot_tell", "fail"]) == "fail"
    assert overall(["pass", "cannot_tell"]) == "cannot_tell"
    assert overall(["pass"]) == "pass"
    assert overall(["not_applicable", "pass"]) == "pass"
    assert overall(["not_applicable"]) == "not_applicable"
    assert overall([]) == "not_applicable"


def test_a_drawing_is_checked_against_every_rule_and_the_same_way_twice() -> None:
    plan = drawing(
        rooms=[room(1, area_m2=10.0), room(2, "wc", box=(0.5, 0.1, 0.6, 0.2))],
        elements=[element(1, "window", ON_WALL), element(2, "door", (0.4, 0.2, 0.5, 0.25))],
    )
    first = check_drawing(plan, PACK)
    assert [(check.rule_id, check.status) for check in first] == [
        ("test-bedroom-area", "pass"),
        ("test-bedroom-window", "pass"),
        ("test-door-width", "pass"),
        ("test-wc-count", "pass"),
    ]
    assert check_drawing(plan, PACK) == first


# --- qa-a's review of #150 (S1-S3, N1-N3; orchestrator's decisions, 2026-11-14) -----------------


def test_rooms_of_a_kind_we_could_not_tell_make_a_room_rule_cannot_tell() -> None:
    """S1: vitoria's HAB1/SAL rooms are typed other; "no bedroom" would be a wrong statement.
    Rooms of a known kind the rule does not name (a store, a hall) stay not applicable."""
    unknown = [room(1, "other"), room(2, "other", box=(0.5, 0.1, 0.8, 0.4)), HALL]
    for rule_id in ("bedroom-area", "bedroom-window"):
        found = check_rule(drawing(rooms=unknown), rule(rule_id))
        assert (found.status, found.results) == ("cannot_tell", ())
        assert "but 2 rooms are of a kind we could not tell, so they cannot be checked." in (
            found.why
        )
        known = check_rule(drawing(rooms=[CLOSET, HALL]), rule(rule_id))
        assert known.status == "not_applicable"


def test_a_scoped_door_rule_on_rooms_of_no_kind_we_tell_cannot_tell() -> None:
    """S1 for doors: with no room of the kinds it names but one we could not tell, the door
    rule cannot say there is no door to a bedroom; with a bedroom there, it can."""
    door = element(1, "door", (0.2, 0.38, 0.27, 0.42))
    unknown = check_rule(drawing(rooms=[room(1, "other"), HALL], elements=[door]), SCOPED)
    assert unknown.status == "cannot_tell"
    assert unknown.why.endswith(
        "but 1 room is of a kind we could not tell, so it cannot be checked."
    )
    to_closet = element(2, "door", (0.38, 0.2, 0.42, 0.26))
    plan = drawing(rooms=[room(1), CLOSET, room(3, "other", box=(0.6, 0.6, 0.9, 0.9))])
    with_bedroom = check_rule(plan.model_copy(update={"elements": ()}), SCOPED)
    assert with_bedroom.status == "not_applicable"
    assert check_rule(drawing(rooms=[room(1), CLOSET], elements=[to_closet]), SCOPED).status == (
        "not_applicable"
    )


def test_a_drawing_read_by_a_route_not_known_is_taken_as_a_picture() -> None:
    """S2: DrawingInfo.route may be None; an outline area under the limit fails only when the
    route read the drawing's own lines."""
    small = room(1, area_m2=6.0, area_source="geometry_x_scale")
    plan = drawing(rooms=[small])
    assert statuses(check_rule(plan, rule("bedroom-area"), route="vector")) == ["fail"]
    for route in (None, "raster"):
        found = check_rule(plan, rule("bedroom-area"), route=route)
        assert statuses(found) == ["cannot_tell"]
        assert "read off a picture" in found.results[0].why


def test_off_a_picture_a_wide_door_cannot_tell_either() -> None:
    """S3: a detector's door box is not a measurement in either direction, at any scale."""
    wide = element(1, "door", (0.5, 0.5, 0.65, 0.55))  # 1.5 m at a printed scale
    assert statuses(check_rule(drawing(elements=[wide]), rule("door-width"))) == ["pass"]
    found = check_rule(drawing(elements=[wide]), rule("door-width"), route="raster")
    assert statuses(found) == ["cannot_tell"]
    assert found.results[0].value == pytest.approx(1.5)
    assert found.results[0].why == (
        "The door at the marked place: its symbol measures 1.5 m and the rule asks at least "
        "0.85 m, but it was read off a picture, whose door boxes are not measurements, so it "
        "cannot be told."
    )


def test_a_rooms_number_is_not_said_twice() -> None:
    """N1: Warmond's label already holds its number ("Bedroom 414B-1-001-011")."""
    held = room(1, label="Bedroom 414B-1-001-011", attrs={"number": "414B-1-001-011"})
    other = room(2, label="Schlafzimmer", attrs={"number": "4.02"}, box=(0.5, 0.1, 0.8, 0.4))
    found = check_rule(drawing(rooms=[held, other]), rule("bedroom-area"))
    assert [result.subject.label for result in found.results] == [
        "Bedroom 414B-1-001-011",
        "Schlafzimmer 4.02",
    ]


def test_a_door_by_three_rooms_or_none_is_named_by_them_or_its_place() -> None:
    """N2: never by its element id."""
    corner = element(1, "door", (0.38, 0.38, 0.42, 0.42))  # where r1, the hall and the closet meet
    plan = drawing(rooms=[room(1), HALL, CLOSET], elements=[corner])
    (result,) = check_rule(plan, rule("door-width")).results
    assert result.subject.label == (
        'the door by the bedroom "MH 1", the hall "MH 9" and the storage room "MH 8"'
    )
    lone = check_rule(
        drawing(elements=[element(2, "door", (0.5, 0.5, 0.6, 0.55))]), rule("door-width")
    )
    assert lone.results[0].subject.label == "the door at the marked place"
    assert "e2" not in lone.results[0].why


def test_a_building_model_checked_on_its_sheets_is_not_applicable() -> None:
    """N3: a model file whose sheets are in the project is checked there; one without stays
    cannot tell, as there is nothing to check it on."""
    space = {"id": "m1", "class": "space", "attrs": {"windows": 0}}
    model = drawing(pages=[], model_objects=[space])
    alone = check_drawing(model, PACK, route="bim")
    assert {check.status for check in alone} == {"cannot_tell"}
    sheets = check_drawing(model, PACK, route="bim", on_sheets=True)
    assert {(check.status, check.why) for check in sheets} == {
        ("not_applicable", "The building model is checked on its sheets in this project.")
    }

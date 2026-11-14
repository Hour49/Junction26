"""A plan edit followed through the services (spec services-follow, SF-1..SF-12) on a synthetic
10 x 10 m page: office A | a 0.2 m wall | office B, storey heights 0..3 m. Elements are given in
the page's metres, as the tools place them."""

import pytest
from shapely.geometry import Point, Polygon, box

from app.core.plan_edit.edit import place_room, remove_wall
from app.core.plan_edit.model import Proposal, Ring
from app.core.plan_edit.walls import Opening, PlanPage, PlanRoom
from app.core.services.follow import follow
from app.core.services.model import (
    DisciplineFollow,
    Lane,
    Point3,
    ServiceElement,
    fit_frame,
)

A, B = box(0, 0, 3, 3), box(3.2, 0, 7, 3)
WALL = box(3, 0, 3.2, 3)
MASS = box(-0.2, -0.2, 7.2, 3.2).difference(A).difference(B)
HEIGHTS = (0.0, 3.0)


def ring(shape: Polygon) -> Ring:
    return tuple((x / 10, y / 10) for x, y in list(shape.exterior.coords)[:-1])


def page() -> PlanPage:
    assert isinstance(MASS, Polygon)
    return PlanPage(
        drawing_id="d" * 16,
        page=1,
        width_m=10,
        height_m=10,
        rooms=(
            PlanRoom("r1", "Office 1", "office", ring(A)),
            PlanRoom("r2", "Office 2", "office", ring(B)),
        ),
        mass=(
            (
                ring(MASS),
                tuple(tuple((x / 10, y / 10) for x, y in h.coords[:-1]) for h in MASS.interiors),
            ),
        ),
        openings=(Opening("e1", "door", (0.1, -0.02, 0.2, 0.0)),),  # A's door, in the top wall
    )


def removal() -> Proposal:
    return remove_wall(page(), "p1", rooms=("r1", "r2"))


def run(
    guid: str,
    a: Point3,
    b: Point3,
    system: str,
    *neighbours: str,
    kind: str = "pipe_segment",
    lane: str = "heating",
) -> ServiceElement:
    return ServiceElement(
        guid=guid,
        lane=lane,  # pyright: ignore[reportArgumentType]
        kind=kind,
        group="flow_segment",
        predefined=None,
        type_name=kind,
        size="DN15",
        systems=(system,),
        storey=None,
        at=a,
        ports=(a, b),
        neighbours=neighbours,
    )


def terminal(
    guid: str,
    at: Point3,
    systems: tuple[str, ...],
    *neighbours: str,
    kind: str = "space_heater",
    predefined: str | None = "RADIATOR",
    ports: tuple[Point3, ...] = (),
) -> ServiceElement:
    return ServiceElement(
        guid=guid,
        lane="heating",
        kind=kind,
        group="flow_terminal",
        predefined=predefined,
        type_name=kind,
        size=None,
        systems=systems,
        storey=None,
        at=at,
        ports=ports,
        neighbours=neighbours,
    )


def followed(*elements: ServiceElement, proposal: Proposal | None = None) -> DisciplineFollow:
    lane = Lane("heating", "checked", "Heating model", elements=elements)
    return follow(page(), proposal or removal(), [lane], HEIGHTS).disciplines[0]


def codes(found: DisciplineFollow) -> list[tuple[str, str]]:
    return [(a.code, a.status) for a in found.actions]


# --- the frame ------------------------------------------------------------------------------------


def test_sf1_the_frame_is_fitted_from_the_rooms_and_refuses_a_sheet_that_is_not_the_model() -> None:
    model = [(10.0, 20.0), (14.0, 20.0), (10.0, 26.0), (17.0, 23.0)]
    on_page = [(x - 8.0, 30.0 - y) for x, y in model]  # shifted, y down
    frame = fit_frame(list(zip(model, on_page, strict=True)))
    assert not isinstance(frame, str)
    assert frame.at(12.0, 22.0) == pytest.approx((4.0, 8.0), abs=1e-6)
    assert frame.residual_m < 0.001 and frame.rooms == 4

    assert "3 are needed" in str(fit_frame(list(zip(model[:2], on_page[:2], strict=True))))
    in_line = [((float(n), 0.0), (float(n), 5.0)) for n in range(4)]
    assert "one line" in str(fit_frame(in_line))
    half = [(m, (p[0] / 2, p[1] / 2)) for m, p in zip(model, on_page, strict=True)]
    assert "scale" in str(fit_frame(half))
    grid = [(float(x), float(y)) for x in range(0, 40, 10) for y in range(0, 30, 10)]
    shown = [(x + 2.0, 50.0 - y) for x, y in grid]
    shown[5] = (shown[5][0] + 0.4, shown[5][1])  # one room of twelve drawn 0.4 m off
    assert "miss" in str(fit_frame(list(zip(grid, shown, strict=True))))


def test_sf1_a_placed_element_keeps_its_height() -> None:
    frame = fit_frame(
        [((0.0, 0.0), (0.0, 9.0)), ((1.0, 0.0), (1.0, 9.0)), ((0.0, 1.0), (0.0, 8.0))]
    )
    assert not isinstance(frame, str)
    placed = frame.placed(run("s", (2.0, 3.0, 1.5), (2.0, 4.0, 2.5), "S"))
    assert placed.ports == (pytest.approx((2.0, 6.0, 1.5)), pytest.approx((2.0, 5.0, 2.5)))


# --- a removed wall -------------------------------------------------------------------------------


def test_sf2_a_radiator_on_the_removed_wall_is_reseated_on_a_free_kept_wall_face() -> None:
    feed = run("feed", (1.0, 2.9, 0.2), (2.9, 2.9, 0.2), "H_flow", "stub")
    stub = run("stub", (2.9, 2.9, 0.2), (3.05, 2.9, 0.2), "H_flow", "feed", "rad")
    radiator = terminal("rad", (2.95, 1.5, 0.5), ("H_flow",), "stub")
    found = followed(feed, stub, radiator)
    (reseat,) = [a for a in found.actions if a.code == "reseat"]
    assert reseat.status == "follows"
    assert "radiator in Office 1" in reseat.label and "H_flow" in reseat.label
    assert reseat.moved_to is not None
    merged = page().shape(removal().rooms[0].polygon)
    spot = Point(reseat.moved_to[0] * 10, reseat.moved_to[1] * 10)
    assert merged.exterior.distance(spot) < 0.01  # on a wall face of the merged room
    assert WALL.distance(spot) > 0  # not on the wall that goes
    (path,) = reseat.paths  # from the kept feed pipe, at right angles
    assert Point(path[0][0] * 10, path[0][1] * 10).distance(Point(2.9, 2.9)) < 1.5
    assert path[-1] == reseat.moved_to
    assert found.summary.follows == 1 and found.summary.new_run_m > 0
    assert codes(found).count(("cut_off", "cut_off")) == 0  # the moved radiator is not "cut off"


def test_sf2_two_terminals_on_the_wall_get_places_apart_and_never_a_door() -> None:
    first = terminal("r1", (2.95, 0.2, 0.5), ())
    second = terminal("r2", (2.95, 0.4, 0.5), ())
    found = followed(first, second)
    spots = [Point(a.moved_to[0] * 10, a.moved_to[1] * 10) for a in found.actions if a.moved_to]
    assert len(spots) == 2 and spots[0].distance(spots[1]) >= 0.5
    door = box(1, -0.2, 2, 0)
    assert all(door.distance(spot) >= 0.15 for spot in spots)


def test_sf3_a_fixture_that_drains_is_offered_a_place_but_left_to_a_person() -> None:
    toilet = terminal(
        "wc", (2.7, 1.5, 0.4), ("Waste water",), kind="sanitary_terminal", predefined="TOILETPAN",
        ports=((2.98, 1.5, 0.2),),
    )  # fmt: skip
    found = followed(toilet)
    (reseat,) = [a for a in found.actions if a.code == "reseat"]
    assert reseat.status == "needs_decision" and reseat.moved_to is not None
    assert "toilet" in reseat.label and "fall and venting" in reseat.label
    assert found.summary.needs_decision == 1 and found.summary.follows == 0


def test_sf4_pipework_inside_the_wall_goes_and_what_it_fed_is_cut_off_per_system() -> None:
    # main ends in the wall; o1 and o2 are the rest of the system, which stays connected
    main = run("main", (0.5, 2.5, 0.2), (3.1, 2.5, 0.2), "Cold water", "inwall", "o1")
    inwall = run("inwall", (3.1, 2.5, 0.2), (3.1, 0.5, 0.2), "Cold water", "main", "out")
    out = run("out", (3.1, 0.5, 0.2), (5.0, 0.5, 0.2), "Cold water", "inwall", "basin")
    drain = run("drain", (5.0, 0.5, -0.4), (5.0, 2.9, -0.4), "Waste water", "basin")
    basin = terminal(
        "basin", (5.0, 0.3, 0.8), ("Cold water", "Waste water"), "out", "drain",
        kind="sanitary_terminal", predefined="WASHHANDBASIN",
    )  # fmt: skip
    o1 = run("o1", (0.5, 1.0, 0.2), (0.5, 2.5, 0.2), "Cold water", "main", "o2")
    o2 = run("o2", (0.5, 1.0, 0.2), (2.0, 1.0, 0.2), "Cold water", "o1")
    found = followed(main, inwall, out, drain, basin, o1, o2)
    (in_wall,) = [a for a in found.actions if a.code == "in_wall"]
    assert in_wall.status == "needs_decision" and in_wall.system == "Cold water"
    assert in_wall.label.startswith("1 pipe piece of Cold water (2.0 m of run) is inside")
    (cut,) = [a for a in found.actions if a.code == "cut_off"]
    assert cut.status == "cut_off" and cut.system == "Cold water"  # not from Waste water
    assert "1 washbasin in Office 2" in cut.label
    assert found.summary.cut_off == 1
    refs = {mark.ref: mark for mark in found.marks}
    assert [refs[ref].kind for ref in cut.refs] == ["washbasin"]


def test_sf5_a_run_through_the_wall_stays_and_cuts_nothing_off() -> None:
    a = run("a", (1.0, 1.5, 2.6), (2.5, 1.5, 2.6), "Supply air", "b", kind="duct_segment")
    b = run("b", (2.5, 1.5, 2.6), (4.0, 1.5, 2.6), "Supply air", "a", "c", kind="duct_segment")
    c = run("c", (4.0, 1.5, 2.6), (6.0, 1.5, 2.6), "Supply air", "b", kind="duct_segment")
    found = followed(a, b, c)
    assert codes(found) == [("through", "stays")]
    assert "1 duct of Supply air passes through" in found.actions[0].label
    assert found.summary == found.summary.model_copy(update={"stays": 1})
    assert found.line == "Heating: 1 system passing through."


def test_sf6_an_upright_run_in_the_wall_that_goes_on_to_another_storey_cannot_follow() -> None:
    low = run("low", (3.1, 1.0, -3.0), (3.1, 1.0, 0.1), "Waste water", "mid")
    mid = run("mid", (3.1, 1.0, 0.1), (3.1, 1.0, 2.9), "Waste water", "low")
    found = followed(low, mid)
    (riser,) = [a for a in found.actions if a.code == "riser"]
    assert riser.status == "needs_decision" and "goes on to another storey" in riser.label
    assert "5.9 m tall" in riser.label and "DN15" in riser.label
    assert not [a for a in found.actions if a.code == "in_wall"]  # a riser is not "goes with it"

    alone = followed(run("mid", (3.1, 1.0, 0.1), (3.1, 1.0, 2.9), "Waste water"))
    assert "stays within this storey" in alone.actions[0].label


def test_sf7_a_fire_damper_in_the_wall_says_the_wall_is_probably_a_fire_boundary() -> None:
    damper = ServiceElement(
        "fd", "heating", "damper", "flow_controller", "FIREDAMPER", "damper", None,
        ("Supply air",), None, (3.1, 1.5, 2.6), ((3.0, 1.5, 2.6), (3.2, 1.5, 2.6)), (),
    )  # fmt: skip
    found = followed(damper)
    assert ("fire_damper", "needs_decision") in codes(found)
    assert "fire compartment" in next(a for a in found.actions if a.code == "fire_damper").label


def test_sf8_what_is_under_the_floor_or_above_the_storey_does_not_meet_the_wall() -> None:
    under = run("u", (1.0, 1.5, -0.5), (6.0, 1.5, -0.5), "Waste water")
    above = terminal("t", (2.95, 1.5, 3.6), ())
    found = followed(under, above)
    assert found.actions == () and found.elements == 0
    assert found.line == "Heating: nothing of this model is on, in or through the changed walls."


def test_sf9_the_merged_room_counts_its_terminals_by_the_room_they_came_from() -> None:
    found = followed(
        terminal("a1", (1.0, 2.8, 0.5), ()),
        terminal("a2", (2.0, 2.8, 0.5), ()),
        terminal("b1", (5.0, 2.8, 0.5), ()),
    )
    (tally,) = found.actions
    assert tally.code == "tally" and tally.status == "stays"
    assert tally.label == "The merged room has 3 radiators (2 from Office 1 + 1 from Office 2)."


def test_sf10_every_lane_is_listed_and_one_without_a_model_says_so() -> None:
    lanes = [
        Lane("plumbing", "no_model"),
        Lane("ventilation", "not_aligned", "Air model", "its storeys are not this building's"),
        Lane("heating", "checked", "Heating model"),
        Lane("electrical", "no_model"),
    ]
    found = follow(page(), removal(), lanes, HEIGHTS, "Level 1", ["Model: MIT, RWTH"])
    assert [d.status for d in found.disciplines] == [
        "no_model",
        "not_aligned",
        "checked",
        "no_model",
    ]
    assert found.disciplines[0].line == (
        "Plumbing: not checked, this project has no plumbing model."
    )
    assert found.disciplines[1].line == (
        "Ventilation: not checked, its storeys are not this building's."
    )
    assert found.storey == "Level 1" and found.credits == ("Model: MIT, RWTH",)
    assert any("3D" in unknown for unknown in found.unknowns)
    nothing = follow(page(), removal(), [Lane("plumbing", "no_model")], HEIGHTS)
    assert nothing.unknowns == ()  # nothing was checked, so nothing to caveat


# --- an added partition ---------------------------------------------------------------------------


def test_sf11_a_new_wall_needs_openings_for_what_crosses_it_and_a_person_for_what_is_under_it() -> (
    None
):
    proposal = place_room(page(), "p1", (0.32, 0.0, 0.5, 0.3), "Store")  # a room in B: wall at x=5
    wall_x = max(x for item in proposal.added for x, _ in item.polygon) * 10 - 0.05
    duct = run("d", (4.0, 1.0, 2.6), (6.5, 1.0, 2.6), "Supply air", kind="duct_segment")
    far = run("f", (5.5, 2.0, 2.6), (6.5, 2.0, 2.6), "Supply air", kind="duct_segment")
    outlet = terminal("o", (wall_x, 2.0, 2.7), (), kind="air_terminal", predefined=None)
    found = followed(duct, far, outlet, proposal=proposal)
    assert codes(found) == [("opening", "follows"), ("under", "needs_decision")]
    assert "1 duct of Supply air (DN15) crosses the new wall: it needs" in found.actions[0].label
    assert "air terminal in Office 2 sits where the new wall goes" in found.actions[1].label


# --- the overlay ----------------------------------------------------------------------------------


def test_sf12_marks_are_what_is_near_the_edit_in_page_fractions_and_actions_point_at_them() -> None:
    near = run("near", (2.0, 1.5, 2.6), (4.0, 1.5, 2.6), "Supply air", kind="duct_segment")
    far = run("far", (6.6, 2.5, 2.6), (6.9, 2.5, 2.6), "Supply air", kind="duct_segment")
    radiator = terminal("rad", (5.0, 2.8, 0.5), ())
    found = followed(near, far, radiator)
    by_kind = {mark.kind: mark for mark in found.marks}
    assert set(by_kind) == {"duct", "radiator"}  # `far` is over 3 m from the wall
    assert by_kind["duct"].line == ((0.2, 0.15), (0.4, 0.15)) and by_kind["duct"].at is None
    assert by_kind["radiator"].at == (0.5, 0.28) and by_kind["radiator"].line == ()
    assert all(mark.ref.startswith("H") for mark in found.marks)
    # Each mark carries its element's GlobalId, so a 3D view can find the same element.
    assert by_kind["duct"].global_id == "near" and by_kind["radiator"].global_id == "rad"
    through = next(a for a in found.actions if a.code == "through")
    assert through.refs == (by_kind["duct"].ref,)


# --- a run that only crosses the wall, and the graph ----------------------------------------------


def test_sf5_a_duct_made_of_pieces_that_meet_inside_the_wall_still_only_passes_through() -> None:
    """A penetration modelled as two ducts and a damper between them inside the wall: it leaves
    the wall towards both rooms, so nothing goes with the wall and nothing is cut off."""
    a = run("a", (1.0, 1.5, 2.6), (3.05, 1.5, 2.6), "Supply air", "d", kind="duct_segment")
    damper = ServiceElement(
        "d", "heating", "damper", "flow_controller", None, "damper", None,
        ("Supply air",), None, (3.1, 1.5, 2.6), ((3.05, 1.5, 2.6), (3.15, 1.5, 2.6)), ("a", "b"),
    )  # fmt: skip
    b = run("b", (3.15, 1.5, 2.6), (6.0, 1.5, 2.6), "Supply air", "d", "out", kind="duct_segment")
    outlet = terminal(
        "out", (6.0, 1.5, 2.7), ("Supply air",), "b", kind="air_terminal", predefined=None
    )
    found = followed(a, damper, b, outlet)
    assert [c for c, _ in codes(found)] == ["through", "tally"]
    assert "2 ducts of Supply air pass through" in found.actions[0].label
    assert found.summary.cut_off == 0 and found.summary.needs_decision == 0


def test_sf4_pipework_that_enters_the_wall_from_one_side_only_goes_with_it() -> None:
    feed = run("feed", (1.0, 1.0, 0.2), (3.1, 1.0, 0.2), "Cold water", "up")  # ends in the wall
    up = run("up", (3.1, 1.0, 0.2), (3.1, 1.0, 0.9), "Cold water", "feed")  # a short upright piece
    found = followed(feed, up)
    assert codes(found) == [("in_wall", "needs_decision")]


def test_sf2_an_air_terminal_beside_the_wall_is_in_the_ceiling_and_stays() -> None:
    beside = terminal("c", (2.9, 1.5, 2.7), (), kind="air_terminal", predefined=None)
    in_wall = terminal("w", (3.1, 2.0, 2.2), (), kind="air_terminal", predefined=None)
    found = followed(beside, in_wall)
    reseated = [a for a in found.actions if a.code == "reseat"]
    assert len(reseated) == 1 and len(reseated[0].refs) == 1
    refs = {mark.ref: mark for mark in found.marks}
    assert refs[reseated[0].refs[0]].at == (0.31, 0.2)  # the one in the wall


def test_sf13_the_graph_answers_by_id_per_system() -> None:
    from app.core.services.graph import ServiceGraph

    main = run("main", (0, 0, 0), (1, 0, 0), "Cold", "branch", "basin")
    branch = run("branch", (1, 0, 0), (2, 0, 0), "Cold", "main")
    drain = run("drain", (0, 1, 0), (1, 1, 0), "Waste", "basin")
    basin = terminal(
        "basin", (0, 0, 1), ("Cold", "Waste"), "main", "drain", kind="sanitary_terminal"
    )
    lone = run("lone", (5, 5, 0), (6, 5, 0), "Cold")
    graph = ServiceGraph([main, branch, drain, basin, lone])
    assert graph.systems() == ("Cold", "Waste")
    assert graph.members("Waste") == {"drain", "basin"} and graph.members("None") == frozenset()
    assert graph.neighbours("basin") == ("main", "drain")
    assert graph.neighbours("basin", "Waste") == ("drain",)
    assert graph.part("branch", "Cold") == {"main", "branch", "basin"}  # not into Waste
    assert graph.part("branch") == {"main", "branch", "basin", "drain"}
    assert graph.part("branch", "Cold", without={"main"}) == {"branch"}
    assert graph.part("nobody") == frozenset() and graph.part("drain", "Cold") == frozenset()
    assert graph.largest("Cold") == {"main", "branch", "basin"}
    assert graph.largest("Cold", without={"main"}) == {"basin"}  # a tie: the lowest id's part
    assert graph.path("branch", "drain") == ("branch", "main", "basin", "drain")
    assert graph.path("branch", "drain", "Cold") == () and graph.path("branch", "lone") == ()
    assert [t.guid for t in graph.terminals(["main", "basin", "x"])] == ["basin"]


def test_sf5_a_damper_alone_in_the_wall_between_two_ducts_is_a_passage_not_pipework() -> None:
    """The ducts stop at the wall's faces and only the damper is in it: the run still crosses."""
    a = run("a", (1.0, 1.5, 2.6), (2.95, 1.5, 2.6), "Extract air", "d", kind="duct_segment")
    damper = ServiceElement(
        "d", "heating", "damper", "flow_controller", "FIREDAMPER", "damper", None,
        ("Extract air",), None, (3.1, 1.5, 2.6), ((3.0, 1.5, 2.6), (3.2, 1.5, 2.6)), ("a", "b"),
    )  # fmt: skip
    b = run("b", (3.25, 1.5, 2.6), (6.0, 1.5, 2.6), "Extract air", "d", "out", kind="duct_segment")
    outlet = terminal(
        "out", (6.0, 1.5, 2.7), ("Extract air",), "b", kind="air_terminal", predefined=None
    )
    found = followed(a, damper, b, outlet)
    assert sorted(c for c, _ in codes(found)) == ["fire_damper", "tally", "through"]
    assert found.summary.cut_off == 0
    through = next(action for action in found.actions if action.code == "through")
    assert through.label.startswith("1 fire damper of Extract air passes through")

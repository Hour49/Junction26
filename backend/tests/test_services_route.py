"""SV-18: the reroute rule's plan geometry (app/core/services/route.py), on plain shapes.

The room in most tests is 6 x 4 m, corners (0, 0) and (6, 4); edge 0 runs along y = 0."""

import pytest
from shapely.geometry import LineString, Polygon

from app.core.services.route import (
    Leg,
    Main,
    Opening,
    blocked_spans,
    door_zones,
    inset_ring,
    place,
    reroute,
    room_edges,
)

ROOM = [(0.0, 0.0), (6.0, 0.0), (6.0, 4.0), (0.0, 4.0)]
P = Polygon(ROOM)


def test_sv18_edges_have_inward_normals_whatever_the_winding() -> None:
    for points in (ROOM, ROOM[::-1]):
        for edge in room_edges(points):
            mid = edge.point(edge.length / 2, 0.1)
            assert P.contains(LineString([mid, mid]).centroid)


def test_sv18_place_takes_the_middle_of_a_free_wall() -> None:
    edge = room_edges(ROOM)[0]
    assert place(edge, 1.0, []) == pytest.approx(3.0)


def test_sv18_place_starts_near_a_given_spot_kept_off_the_ends() -> None:
    edge = room_edges(ROOM)[0]
    assert place(edge, 1.0, [], near=0.0) == pytest.approx(0.6)
    assert place(edge, 1.0, [], near=99.0) == pytest.approx(5.4)


def test_sv18_place_slides_in_quarter_metre_steps_past_a_door() -> None:
    edge = room_edges(ROOM)[0]
    door = Opening("door", ((2.6, 0.0), (3.6, 0.0)), sill_m=0.0, head_m=2.1)
    spans = blocked_spans(edge, [door], [], top_m=0.6, wall_distance=0.1)
    k = place(edge, 1.0, spans)
    assert k is not None
    assert (k - 3.0) % 0.25 == pytest.approx(0) or (k - 3.0) % 0.25 == pytest.approx(0.25)
    assert k + 0.5 <= 2.6 - 0.1 + 1e-9 or k - 0.5 >= 3.6 + 0.1 - 1e-9


def test_sv18_a_window_is_in_the_way_only_when_its_sill_is_low() -> None:
    edge = room_edges(ROOM)[0]
    window = ((2.0, 0.0), (4.0, 0.0))
    high = Opening("window", window, sill_m=0.9, head_m=2.1)
    low = Opening("window", window, sill_m=0.6, head_m=2.1)
    assert blocked_spans(edge, [high], [], top_m=0.6, wall_distance=0.1) == []
    assert blocked_spans(edge, [low], [], top_m=0.6, wall_distance=0.1) != []


def test_sv18_no_place_when_every_step_is_blocked() -> None:
    edge = room_edges(ROOM)[0]
    door = Opening("door", ((0.5, 0.0), (5.5, 0.0)), sill_m=0.0, head_m=2.1)
    spans = blocked_spans(edge, [door], [], top_m=0.6, wall_distance=0.1)
    assert place(edge, 1.0, spans) is None


def test_sv18_another_terminal_body_blocks_its_stretch_of_wall() -> None:
    edge = room_edges(ROOM)[0]
    body = [(2.5, 0.05), (3.5, 0.05), (3.5, 0.11), (2.5, 0.11)]
    spans = blocked_spans(edge, [], [body], top_m=0.6, wall_distance=0.1)
    k = place(edge, 1.0, spans)
    assert k is not None and abs(k - 3.0) >= 1.2 - 1e-9


def test_sv18_inset_ring_follows_the_walls_at_the_offset() -> None:
    ring = inset_ring(P, 0.1)
    assert ring is not None and ring.length == pytest.approx(2 * (5.8 + 3.8))
    assert inset_ring(Polygon([(0, 0), (0.1, 0), (0.1, 4), (0, 4)]), 0.1) is None


# A radiator on the top wall (y = 4), supply port at x = 4.5; a main along the bottom wall.
PORT_S, PORT_R = (4.5, 3.9), (4.7, 3.9)
MAIN_S = Main("M1", (0.0, 0.1), (6.0, 0.1))
MAIN_R = Main("M2", (0.0, 0.16), (6.0, 0.16))


def _leg(port: tuple[float, float], *mains: Main, junction=None, offset=0.1) -> Leg:
    return Leg(port=port, offset=offset, mains=mains, junction=junction)


def test_sv18_the_supply_taps_a_main_along_a_wall_and_runs_the_shorter_way_round() -> None:
    routed = reroute(P, [], _leg(PORT_S, MAIN_S), None, spacing=0.06)
    assert not isinstance(routed, str)
    (run,) = routed.runs
    assert run.tap.tier == "along" and run.tap.main == "M1"
    assert run.path[0] == pytest.approx(run.tap.at) and run.path[-1] == pytest.approx(PORT_S)
    line = LineString(run.path)
    assert P.contains(line)
    # right-hand way (via x = 5.9) is shorter than round the left wall
    assert max(x for x, _ in run.path) == pytest.approx(5.9)


def test_sv18_a_door_on_the_shorter_way_sends_the_run_the_other_way() -> None:
    door = Opening("door", ((6.0, 1.5), (6.0, 2.5)), sill_m=0.0, head_m=2.1)
    routed = reroute(P, door_zones([door]), _leg(PORT_S, MAIN_S), None, spacing=0.06)
    assert not isinstance(routed, str)
    assert min(x for x, _ in routed.runs[0].path) == pytest.approx(0.1)


def test_sv18_both_ways_past_a_door_is_refused() -> None:
    doors = door_zones(
        [
            Opening("door", ((6.0, 1.5), (6.0, 2.5)), sill_m=0.0, head_m=2.1),
            Opening("door", ((0.0, 1.5), (0.0, 2.5)), sill_m=0.0, head_m=2.1),
        ]
    )
    assert reroute(P, doors, _leg(PORT_S, MAIN_S), None, spacing=0.06) == "doors"


def test_sv18_connection_tiers_in_order() -> None:
    middle = Main("M9", (1.0, 2.0), (5.0, 2.0))
    outside = Main("M8", (0.0, -0.5), (6.0, -0.5))
    far = Main("M7", (0.0, -3.0), (6.0, -3.0))

    def tier(*mains: Main, junction=None) -> str:
        routed = reroute(P, [], _leg(PORT_S, *mains, junction=junction), None, spacing=0.06)
        assert not isinstance(routed, str)
        return routed.runs[0].tap.tier

    assert tier(MAIN_S, middle) == "along"
    assert tier(middle, outside) == "room"
    assert tier(outside, junction=(3.0, 3.5)) == "junction"
    assert tier(outside) == "outside"
    assert reroute(P, [], _leg(PORT_S, far), None, spacing=0.06) == "no_main"


def test_sv18_the_return_runs_beside_the_supply_on_the_room_side_and_does_not_cross() -> None:
    routed = reroute(P, [], _leg(PORT_S, MAIN_S), _leg(PORT_R, MAIN_R), spacing=0.06)
    assert not isinstance(routed, str)
    supply, ret = routed.runs
    assert ret.tap.main == "M2"
    assert not LineString(supply.path).crosses(LineString(ret.path))
    assert routed.crossover_m is None


# Ports in the other order than the mains (supply port left, its main on the wall side): two
# wall-following pipes must cross once, at the terminal's ports.
CROSSING = (
    _leg((4.3, 3.95), Main("M1", (0.0, 0.1), (6.0, 0.1))),
    _leg((4.5, 3.95), Main("M2", (0.0, 0.16), (6.0, 0.16))),
)


def test_sv18_a_pair_that_must_cross_is_refused_by_the_strict_rule() -> None:
    assert reroute(P, [], *CROSSING, spacing=0.06) == "cross"


def test_sv18_a_crossing_at_the_ports_is_allowed_and_measured_when_asked() -> None:
    routed = reroute(P, [], *CROSSING, spacing=0.06, cross_at_ports_m=0.15)
    assert not isinstance(routed, str)
    assert routed.crossover_m == pytest.approx(0.05, abs=0.01)


def test_sv18_a_clean_variant_is_preferred_to_an_allowed_crossing() -> None:
    supply = _leg((4.5, 3.7), Main("M1", (0.0, 0.1), (6.0, 0.1)))
    ret = _leg((4.3, 3.7), Main("M2", (0.0, 0.16), (6.0, 0.16)))
    strict = reroute(P, [], supply, ret, spacing=0.06)
    loose = reroute(P, [], supply, ret, spacing=0.06, cross_at_ports_m=0.15)
    assert not isinstance(strict, str) and not isinstance(loose, str)
    assert loose.crossover_m is None and loose.runs == strict.runs

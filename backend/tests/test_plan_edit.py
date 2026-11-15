"""Plan edits by geometry (spec agent-chat §2.4, AC-15..AC-20) on a synthetic 10 x 10 m page:
bathroom A | 0.12 m wall with a door | bedroom B, a balcony C past the façade, a hall D apart."""

import pytest
from shapely.geometry import Polygon, box

from app.core.plan_edit.edit import EditRefusedError, place_room, remove_wall
from app.core.plan_edit.model import Ring
from app.core.plan_edit.walls import Opening, PlanPage, PlanRoom, walls_of

A, B, C, D = box(0, 0, 3, 3), box(3.12, 0, 7, 3), box(0, 3.2, 7, 5), box(8, 0, 9, 3)
GAP = box(3, 1, 3.12, 2)  # the door opening: no wall mass there
MASS = box(-0.2, -0.2, 7.2, 3.2).difference(A).difference(B).difference(GAP)


def ring(shape: Polygon) -> Ring:
    return tuple((x / 10, y / 10) for x, y in list(shape.exterior.coords)[:-1])


def frac(*b: float) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = b
    return (x0 / 10, y0 / 10, x1 / 10, y1 / 10)


def page() -> PlanPage:
    assert isinstance(MASS, Polygon)
    return PlanPage(
        drawing_id="d" * 16,
        page=1,
        width_m=10,
        height_m=10,
        rooms=(
            PlanRoom("r1", "Bath 1.01", "bathroom", ring(A)),
            PlanRoom("r2", "Bedroom 1.02", "bedroom", ring(B)),
            PlanRoom("r3", "Balcony 1.03", "balcony", ring(C), outdoor=True),
            PlanRoom("r4", "Hall 1.04", "hall", ring(D)),
        ),
        mass=(
            (
                ring(MASS),
                tuple(tuple((x / 10, y / 10) for x, y in h.coords[:-1]) for h in MASS.interiors),
            ),
        ),
        openings=(
            Opening("e1", "door", frac(2.9, 1, 3.22, 2)),
            Opening("e2", "door", frac(5, 2.9, 6, 3.3)),
            Opening("e3", "window", frac(1, -0.2, 2, 0)),
        ),
    )


def test_ac15_a_wall_is_the_mass_between_two_rooms_with_its_door() -> None:
    walls = {w.rooms: w for w in walls_of(page())}
    inside = walls[("r1", "r2")]
    assert inside.thickness_m == pytest.approx(0.12, abs=0.02)
    assert inside.length_m >= 2  # 3 m, less the 1 m door gap
    assert inside.doors == ("e1",)
    assert [w.id for w in walls_of(page())] == [f"W{n}" for n in range(1, len(walls) + 1)]
    assert not any("r4" in rooms for rooms in walls)  # the hall stands apart


def test_ac17_removing_the_wall_merges_both_rooms_and_the_wall() -> None:
    found = remove_wall(page(), "p1", rooms=("r1", "r2"))
    (merged,) = found.rooms
    assert merged.label == "Bath 1.01 + Bedroom 1.02" and merged.was == ("r1", "r2")
    assert merged.area_before_m2 == pytest.approx(9 + 3.88 * 3, abs=0.01)
    assert merged.area_after_m2 == pytest.approx(9 + 3.88 * 3 + 0.12 * 3, abs=0.02)  # with the gap
    assert [i.id for i in found.removed] == ["W1", "e1"]
    assert found.removed[-1].label == "door, no longer needed"
    assert found.unknowns and "load-bearing" in found.unknowns[0]
    assert {f.code for f in found.flags} == {"structural", "wet_room"}  # AC-19
    assert all(0 <= x <= 1 and 0 <= y <= 1 for x, y in merged.polygon)  # AC-20 page fractions


def test_ac17_a_wall_by_its_id_is_the_same_edit() -> None:
    wall = next(w for w in walls_of(page()) if w.rooms == ("r1", "r2"))
    by_id = remove_wall(page(), "p2", wall_id=wall.id)
    assert by_id.rooms == remove_wall(page(), "p2", rooms=("r2", "r1")).rooms


@pytest.mark.parametrize(
    ("rooms", "why"),
    [
        (("r1", "r3"), "façade"),  # the balcony is outside
        (("r2", "r4"), "not on two sides"),  # no wall between them
        (("r1", "r9"), "no room r9"),
    ],
)
def test_ac17_a_pair_without_one_inside_wall_is_refused(rooms: tuple[str, str], why: str) -> None:
    with pytest.raises(EditRefusedError, match=why):
        remove_wall(page(), "p1", rooms=rooms)


def test_ac18_a_drawn_region_snaps_to_the_walls_and_the_room_shrinks() -> None:
    found = place_room(page(), "p1", frac(5.1, 0.08, 6.9, 1.5), "Storage")
    new, bedroom = found.rooms
    assert new.label == "Storage" and new.was == ("r2",) and bedroom.id == "r2"
    xs = [x * 10 for x, _ in new.polygon]
    ys = [y * 10 for _, y in new.polygon]
    assert min(ys) == pytest.approx(0, abs=1e-6) and max(xs) == pytest.approx(
        7, abs=1e-6
    )  # snapped
    assert min(xs) == pytest.approx(5.15, abs=0.01)  # 5.1 is no face: a new wall's half is taken
    walls = sum(Polygon([(x * 10, y * 10) for x, y in w.polygon]).area for w in found.added)
    assert len(found.added) >= 1 and walls == pytest.approx((1.5 + 1.9) * 0.1, abs=0.02)
    assert new.area_after_m2 + bedroom.area_after_m2 + walls == pytest.approx(
        bedroom.area_before_m2, abs=0.02
    )
    assert ("no_door", "Storage would have no door.") in {(f.code, f.text) for f in found.flags}


def test_ac18_a_region_outside_the_rooms_is_refused() -> None:
    with pytest.raises(EditRefusedError, match="outside the rooms"):
        place_room(page(), "p1", frac(9.3, 5.5, 9.9, 6.5), "Storage")


def test_ac18_a_region_across_a_wall_is_refused() -> None:
    with pytest.raises(EditRefusedError, match="crosses a wall"):
        place_room(page(), "p1", frac(1.5, 0.5, 4.5, 2.5), "Storage")


def test_qa_a_wall_thinner_than_the_gap_between_its_rooms_still_merges_them() -> None:
    """QA 2026-11-15 (DigitalHub ground floor, 11 of 43 walls): the room outlines stop 0.035 m
    short of the wall's faces, so the 0.08 m mass alone left the rooms apart and a listed wall
    was refused as 'not on two sides of one inside wall'."""
    a, b = box(0, 0, 3, 3), box(3.15, 0, 7, 3)
    mass = box(-0.2, -0.2, 7.2, 3.2).difference(a.buffer(0.035, join_style="mitre"))
    mass = mass.difference(b.buffer(0.035, join_style="mitre"))
    assert isinstance(mass, Polygon)
    thin = PlanPage(
        drawing_id="d" * 16,
        page=1,
        width_m=10,
        height_m=10,
        rooms=(
            PlanRoom("r1", "Office 1", "office", ring(a)),
            PlanRoom("r2", "Office 2", "office", ring(b)),
        ),
        mass=(
            (
                ring(mass),
                tuple(tuple((x / 10, y / 10) for x, y in h.coords[:-1]) for h in mass.interiors),
            ),
        ),
        openings=(),
    )
    (wall,) = walls_of(thin)
    assert wall.thickness_m == pytest.approx(0.08, abs=0.02)
    (merged,) = remove_wall(thin, "p1", wall_id=wall.id).rooms
    assert merged.area_after_m2 == pytest.approx(9 + 3.85 * 3 + 0.15 * 3, abs=0.05)

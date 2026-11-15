"""register: a services sheet's wall lines laid over the plan's (rotation, scale, shift)."""

import math
import time

import numpy as np

from app.core.services import register as register_module
from app.core.services.model import Point2
from app.core.services.register import Place, Refusal, Segment, register


def floor(seed: int) -> list[Segment]:
    """An outer 24 x 14 m box and random rooms' walls, axis-aligned (metres)."""
    rng = np.random.default_rng(seed)
    walls: list[tuple[Point2, Point2]] = [
        ((0, 0), (24, 0)),
        ((24, 0), (24, 14)),
        ((24, 14), (0, 14)),
        ((0, 14), (0, 0)),
    ]
    for _ in range(36):
        x, y = rng.uniform(1, 23), rng.uniform(1, 13)
        if rng.random() < 0.5:
            walls.append(((x, y), (min(24, x + rng.uniform(1.5, 7)), y)))
        else:
            walls.append(((x, y), (x, min(14, y + rng.uniform(1.5, 6)))))
    return [Segment(a=a, b=b) for a, b in walls]


def onto_sheet(walls, deg: float, scale: float, shift, seed: int = 1, drop: float = 0.3):
    """The plan's walls as a sheet draws them: q = R(-deg) (p - shift) / scale, 30% left out,
    a little jitter, and services lines that are no walls."""
    rng = np.random.default_rng(seed)
    t = math.radians(-deg)
    c, s = math.cos(t), math.sin(t)

    def q(p):
        x, y = p[0] - shift[0], p[1] - shift[1]
        j = rng.normal(0, 0.02, 2)
        return ((c * x - s * y) / scale + j[0], (s * x + c * y) / scale + j[1])

    kept = [w for w in walls if rng.random() >= drop]
    out = [Segment(a=q(w.a), b=q(w.b)) for w in kept]
    for _ in range(8):  # pipes and ducts
        a = q((rng.uniform(0, 24), rng.uniform(0, 14)))
        b = q((rng.uniform(0, 24), rng.uniform(0, 14)))
        out.append(Segment(a=a, b=b))
    return out


def test_a_known_rotation_scale_and_shift_is_recovered() -> None:
    plan = floor(7)
    sheet = onto_sheet(plan, deg=93.0, scale=0.02, shift=(5.0, -3.0))
    place = register(plan, sheet)
    assert isinstance(place, Place), place
    assert abs((place.rotation_deg - 93.0 + 180) % 360 - 180) < 0.5
    assert abs(place.scale / 0.02 - 1) < 0.01
    assert math.dist(place.shift, (5.0, -3.0)) < 0.1
    assert place.inliers >= 0.6 * place.of_total and place.rms_m < 0.1


def test_the_plan_s_own_walls_unturned_are_the_identity() -> None:
    plan = floor(3)
    place = register(plan, plan)
    assert isinstance(place, Place), place
    assert abs(place.rotation_deg) < 0.01 and abs(place.scale - 1) < 1e-3
    assert math.dist(place.shift, (0, 0)) < 0.01 and place.inliers == place.of_total


def test_another_floor_is_refused() -> None:
    sheet = onto_sheet(floor(11), deg=0.0, scale=1.0, shift=(0.0, 0.0))
    out = register(floor(7), sheet)
    assert isinstance(out, Refusal), out
    assert "wall lines match" in out.reason


def test_too_few_walls_are_refused() -> None:
    plan = floor(7)
    out = register(plan, plan[:3])
    assert isinstance(out, Refusal)
    assert out.reason == "only 3 wall lines on the services sheet (6 needed)"


def test_non_finite_lines_are_dropped_before_counting() -> None:
    plan = floor(7)
    bad = [Segment(a=(math.nan, 0.0), b=(1.0, 1.0)), Segment(a=(0.0, 0.0), b=(math.inf, 2.0))]
    out = register(plan, [*plan[:4], *bad])
    assert out == Refusal(reason="only 4 wall lines on the services sheet (6 needed)")
    place = register([*plan, *bad], [*onto_sheet(plan, 0.0, 1.0, (0.0, 0.0)), *bad])
    assert isinstance(place, Place), place


def test_a_far_stray_line_is_fast_and_harmless() -> None:
    plan = floor(7)
    stray = Segment(a=(10_000.0, 10_000.0), b=(10_003.0, 10_000.0))
    sheet = onto_sheet(plan, deg=93.0, scale=0.02, shift=(5.0, -3.0))
    start = time.perf_counter()
    place = register([*plan, Segment(a=(100.0, 100.0), b=(103.0, 100.0))], [*sheet, stray])
    assert time.perf_counter() - start < 30.0  # only the old blow-up (243 s, GBs); work: below
    assert isinstance(place, Place), place
    assert abs(place.scale / 0.02 - 1) < 0.01


def test_many_walls_and_a_10_km_stray_keep_the_work_bounded(monkeypatch) -> None:
    """Deterministic: the work (lines kept, points against walls, vote cells) is capped by
    LONGEST, whatever the count and spread of the input; a 30 s bound only catches a blow-up."""
    rng = np.random.default_rng(5)
    plan = floor(7) + [
        Segment(a=(x, y), b=(x + 1.0, y)) for x, y in rng.uniform(0, 14, (200, 2)).tolist()
    ]
    sheet = [*plan, Segment(a=(10_000.0, 0.0), b=(10_001.0, 0.0))]
    sizes: list[tuple[int, int]] = []
    votes: list[int] = []
    nearest, unique = register_module._nearest, np.unique

    def counted_nearest(points, walls):
        sizes.append((len(points), len(walls)))
        return nearest(points, walls)

    def counted_unique(keys, **kw):
        votes.append(len(keys))
        return unique(keys, **kw)

    monkeypatch.setattr(register_module, "_nearest", counted_nearest)
    monkeypatch.setattr(register_module.np, "unique", counted_unique)
    start = time.perf_counter()
    register(plan, sheet)
    assert time.perf_counter() - start < 30.0
    most = 120  # lines per side; the cost grows with their product
    assert max(w for _, w in sizes) <= most
    assert max(p for p, _ in sizes) <= most * register_module.SAMPLES
    runs = 4 * register_module.POSES + len(register_module.NUDGES) + 3  # + polish, 2 half turns
    assert len(sizes) <= runs * (register_module.ICP_STEPS + 1) + 8
    assert max(votes) <= (2 * most) ** 2


def test_a_refined_scale_stays_in_the_searched_range() -> None:
    """ICP left alone shrinks a pose on lines that match nothing (0.48x here) toward a point,
    where every line would count as on a wall."""
    rng = np.random.default_rng(4)
    sheet = rng.uniform(0, 30, (12, 2, 2))
    plan = np.array([[w.a, w.b] for w in floor(7)])
    _, scale, _ = register_module._icp(plan, sheet, 0.0, 1.0, np.zeros(2), (0.9, 1.1))
    assert 0.9 <= scale <= 1.1


def dense(seed: int) -> list[Segment]:
    """An architect's plan: the floor and 100 short stubs (closets, door jambs), axis-aligned."""
    rng = np.random.default_rng(seed)
    out = floor(seed)
    for _ in range(100):
        x, y, n = rng.uniform(0.5, 23.5), rng.uniform(0.5, 13.5), rng.uniform(0.4, 1.5)
        out.append(Segment(a=(x, y), b=(x + n, y) if rng.random() < 0.5 else (x, y + n)))
    return out


def sparse(plan, seed: int, walls: int = 12, junk: int = 30, scale: float = 0.0105):
    """A services sheet of `plan` (px, unturned, scale m/px): only `walls` of its 40 longest
    walls are drawn, and `junk` short lines that are no walls (radiators, pipe stubs, text)."""
    rng = np.random.default_rng(seed)

    def q(p):
        return ((p[0] - 2.0) / scale, (p[1] - 1.0) / scale)

    longest = sorted(plan, key=lambda w: -math.dist(w.a, w.b))[:40]
    out = [Segment(a=q(longest[i].a), b=q(longest[i].b)) for i in rng.choice(40, walls, False)]
    for _ in range(junk):
        x, y, n = rng.uniform(0, 24), rng.uniform(0, 14), rng.uniform(0.3, 1.2)
        out.append(Segment(a=q((x, y)), b=q((x + n, y) if rng.random() < 0.5 else (x, y + n))))
    return out


def test_a_sparse_services_sheet_is_placed_right_or_refused_never_wrong() -> None:
    """A dev building's kind: a dense plan, a sheet with a few long walls and many short lines.
    Line counts let a wrong pose through (seeds 6, 8, 11, 16, 23; seed 16 at 0.56x and a
    quarter turn, like the real pair). Within 5%: axis-aligned walls slide along themselves,
    so on this sheet a pose 2-4% off scores more wall length than the truth."""
    for seed in (6, 8, 11, 16, 23, 0, 1, 10, 25):
        out = register(dense(seed), sparse(dense(seed), seed))
        if isinstance(out, Place):
            assert abs(out.rotation_deg) < 2 and abs(out.scale / 0.0105 - 1) < 0.05, (seed, out)


def test_a_plan_alike_turned_half_round_is_refused_or_placed_right() -> None:
    """A floor that looks the same turned 180 deg: its twin pose scores as well."""
    half = [((0, 0), (24, 0)), ((24, 0), (24, 14)), ((24, 14), (0, 14)), ((0, 14), (0, 0))]
    for x in (4.0, 8.0, 12.0):
        half += [((x, 0), (x, 5)), ((24 - x, 14), (24 - x, 9))]
    half += [((0, 7), (6, 7)), ((24, 7), (18, 7))]
    plan = [Segment(a=a, b=b) for a, b in half]
    out = register(plan, onto_sheet(plan, deg=0.0, scale=0.02, shift=(1.0, 1.0), drop=0.0))
    if isinstance(out, Place):
        assert abs(out.rotation_deg) < 0.5, out


def test_another_building_s_services_sheet_is_refused() -> None:
    """The services sheet of another, similar building (as a dev pair was)."""
    for seed in range(3):
        out = register(dense(seed), sparse(dense(seed + 100), seed, walls=40, junk=80))
        assert isinstance(out, Refusal), (seed, out)


def test_an_expected_scale_narrows_the_search() -> None:
    plan = dense(6)
    sheet = sparse(plan, 6, walls=30)
    out = register(plan, sheet, expected_scale=0.0105)
    assert isinstance(out, Place) and abs(out.scale / 0.0105 - 1) < 0.02, out
    wrong = register(plan, sheet, expected_scale=0.0105 * 2)  # a misread printed scale
    assert isinstance(wrong, Refusal), wrong


def test_a_lay_off_the_wall_directions_quarter_turns_is_refused(monkeypatch) -> None:
    """The fitted turn must agree (mod 90) with the direction histograms' peak; a fit that ends
    further off was forced (on rendered dev pairs: wrong lays 7-26 deg off). Here the
    peak is made to read 2 deg, ICP still finds the true 0 deg, and the gate is 1 deg."""
    plan = floor(7)
    monkeypatch.setattr(register_module, "_rotation", lambda plan, sheet: 2.0)
    monkeypatch.setattr(register_module, "TURN_DEG", 1.0)
    out = register(plan, plan)
    assert isinstance(out, Refusal), out
    assert out.reason.startswith("the fitted turn is 2.0 deg off"), out


def test_sheet_lines_of_no_length_are_refused_and_mixed_ones_still_work() -> None:
    plan = floor(7)
    dots = [Segment(a=(float(x), 1.0), b=(float(x), 1.0)) for x in range(10)]
    out = register(plan, dots)
    assert out == Refusal(reason="the services sheet's wall lines have no length")
    sheet = onto_sheet(plan, deg=93.0, scale=0.02, shift=(5.0, -3.0))
    place = register(plan, [*sheet, *dots])
    assert isinstance(place, Place) and abs(place.scale / 0.02 - 1) < 0.01, place


def test_an_expected_scale_that_is_no_positive_number_is_refused() -> None:
    plan = floor(7)
    for bad in (0.0, -1.0, math.nan, math.inf):
        out = register(plan, plan, expected_scale=bad)
        assert out == Refusal(reason=f"the expected scale {bad} is not a positive number"), bad


def symmetric() -> list[Segment]:
    """A floor that is the same turned 180 deg about its middle (12, 7)."""
    walls = [((0, 0), (24, 0)), ((24, 0), (24, 14)), ((24, 14), (0, 14)), ((0, 14), (0, 0))]
    for x in (4.0, 9.0, 15.0):
        walls += [((x, 0), (x, 5)), ((24 - x, 14), (24 - x, 9))]
    walls += [((0, 7), (7, 7)), ((24, 7), (17, 7)), ((10, 5), (10, 9)), ((14, 9), (14, 5))]
    return [Segment(a=a, b=b) for a, b in walls]


def search_misses_the_half_turn(monkeypatch) -> None:
    """The bench's flips (#538): the quarter-turn search tries no shift near the turned-round
    pose, so the margin between quarter turns never sees it. Here: every guess at a turn near
    180 deg is moved 30 m off."""
    guesses = register_module._guesses

    def missing(plan, sheet, deg, expected=None):
        found, searched = guesses(plan, sheet, deg, expected)
        if abs((deg + 180.0) % 360.0 - 180.0) > 90.0:
            found = [(scale, shift + 30.0) for scale, shift in found]
        return found, searched

    monkeypatch.setattr(register_module, "_guesses", missing)


def test_a_symmetric_floor_is_refused_when_the_search_misses_its_half_turn(monkeypatch) -> None:
    search_misses_the_half_turn(monkeypatch)
    plan = symmetric()
    sheet = onto_sheet(plan, deg=180.0, scale=0.02, shift=(24.0, 14.0), drop=0.0)
    out = register(plan, sheet)
    assert isinstance(out, Refusal), out
    assert "turned half round" in out.reason


def test_an_asymmetric_floor_is_placed_when_the_search_misses_its_half_turn(monkeypatch) -> None:
    search_misses_the_half_turn(monkeypatch)
    plan = floor(7)
    out = register(plan, onto_sheet(plan, deg=0.0, scale=0.02, shift=(5.0, -3.0)))
    assert isinstance(out, Place), out
    assert abs(out.rotation_deg) < 0.5 and math.dist(out.shift, (5.0, -3.0)) < 0.1


def test_an_expected_rotation_settles_a_symmetric_floor() -> None:
    """Both lays fit a symmetric floor; the caller's turn (north arrows) picks one."""
    plan = symmetric()
    sheet = onto_sheet(plan, deg=180.0, scale=0.02, shift=(24.0, 14.0), drop=0.0)
    assert isinstance(register(plan, sheet), Refusal)
    for expected in (175.0, -5.0):
        out = register(plan, sheet, expected_rotation_deg=expected)
        assert isinstance(out, Place), (expected, out)
        assert abs((out.rotation_deg - expected + 180) % 360 - 180) < 6, (expected, out)
    out = register(plan, sheet, expected_rotation_deg=float("nan"))
    assert isinstance(out, Refusal) and "expected rotation" in out.reason

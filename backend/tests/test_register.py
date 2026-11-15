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
    assert len(sizes) <= 4 * register_module.POSES * (register_module.ICP_STEPS + 1) + 8
    assert max(votes) <= (2 * most) ** 2


def test_a_refined_scale_stays_in_the_searched_range() -> None:
    """ICP left alone shrinks a pose on lines that match nothing (0.48x here) toward a point,
    where every line would count as on a wall."""
    rng = np.random.default_rng(4)
    sheet = rng.uniform(0, 30, (12, 2, 2))
    plan = np.array([[w.a, w.b] for w in floor(7)])
    _, scale, _ = register_module._icp(plan, sheet, 0.0, 1.0, np.zeros(2), (0.9, 1.1))
    assert 0.9 <= scale <= 1.1

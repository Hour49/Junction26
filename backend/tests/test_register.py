"""register: a services sheet's wall lines laid over the plan's (rotation, scale, shift)."""

import math

import numpy as np

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

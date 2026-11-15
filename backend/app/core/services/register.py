"""`register`: where a services sheet lies on the plan, from wall lines alone (rotation, scale,
shift), for a pair of sheets that print no shared room names. Pure geometry on segments; the
caller finds the lines (the plan's walls in metres, the sheet's in its own units).

Method (`.agents` research, pairing §2): the rotation from the two sets' length-weighted
direction histograms (mod 180 deg), tried at all four quarter turns since plans are mostly
orthogonal; for each, a scale searched around the ratio of the sets' extents and the shift voted
for by every pair of points (Hough); the best few poses refined by trimmed ICP with Umeyama's
closed-form similarity; the winner accepted when enough sheet lines lie on a plan wall and no
other quarter turn does nearly as well.
"""

import math
from collections.abc import Sequence

import numpy as np

from app.core.model import Frozen
from app.core.services.model import Point2

MIN_WALLS = 6  # fewer sheet lines than this cannot pin a rotation, scale and shift apart
TOL_M = 0.2  # a sheet line within this of a plan wall (all along) lies on it: a wall's thickness
MIN_SHARE = 0.5  # services lines (pipes, ducts) are no walls: half the sheet's line LENGTH
# on walls; by length, since many short stubs fit some wall of a dense plan at a wrong pose
QUADRANTS = 3  # the matched lines lie in this many of the sheet's quarters: not one corner
TURN_DEG = 3.0  # the pose's turn agrees with the direction histograms' (mod 90) this closely
MARGIN = 1.3  # the best pose must beat another quarter turn's by this, or it is a guess
COVER = (0.75, 1.33)  # the placed sheet spans this share of the plan's extent: a sheet of the
# same floor draws the same building; a wrong scale shrinks it onto part of a dense plan
NUDGES = (0.94, 0.96, 0.98, 1.02, 1.04, 1.06)  # the best pose restarted at these scales:
# ICP stops in a local fit a few % off when walls slide along themselves
PRIOR = np.exp(np.linspace(math.log(0.8), math.log(1.25), 23))  # around a caller's scale
SCALES = np.exp(np.linspace(math.log(0.5), math.log(2.0), 71))  # around the extents' ratio, 2%
VOTE_M = 0.5  # shift vote bin: wide enough for a 2% scale step across a floor
POSES = 3  # poses refined by ICP per quarter turn
ICP_STEPS = 25
SETTLED = 1e-6  # ICP stops when a step moves the sheet's points less than this share of its size
TRIM = 0.7  # ICP fits the best 70% of points: missing walls and services lines fall out
SAMPLES = 5  # points per sheet line, ends included
LONGEST = 120  # lines kept per side, longest first: the cost grows with lines on both sides
SPREAD = (5.0, 95.0)  # percentiles of the points a set's extent is taken between: a stray line
# far off neither sizes the scale search nor the shift vote


class Segment(Frozen):
    a: Point2
    b: Point2


class Place(Frozen):
    """Sheet -> plan: p = scale * R(rotation_deg) q + shift."""

    rotation_deg: float
    scale: float
    shift: Point2
    inliers: int  # sheet lines on a plan wall
    of_total: int  # sheet lines
    rms_m: float  # over the inliers' points

    @property
    def reason(self) -> str:
        return (
            f"walls match: {self.inliers} of {self.of_total} within {TOL_M} m after rotation "
            f"{self.rotation_deg:.1f} deg"
        )


class Refusal(Frozen):
    reason: str


def register(
    plan_walls: Sequence[Segment],
    sheet_walls: Sequence[Segment],
    expected_scale: float | None = None,
) -> Place | Refusal:
    """How the sheet's lines land on the plan's walls, or why they cannot be laid over. Lines
    with a point that is not a finite number are left out; of the rest, the `LONGEST` longest
    of each side are used (`of_total` counts the sheet's used lines). `expected_scale` (plan
    units per sheet unit, e.g. from both printed scales and the dpi) keeps the scale within
    -20%/+25% of it."""
    if expected_scale is not None and not (math.isfinite(expected_scale) and expected_scale > 0):
        return Refusal(reason=f"the expected scale {expected_scale} is not a positive number")
    plan, sheet = _ends(plan_walls), _ends(sheet_walls)
    if len(sheet) and float(_lengths(sheet).max()) <= 0.0:
        return Refusal(reason="the services sheet's wall lines have no length")
    if len(sheet) < MIN_WALLS:
        return Refusal(
            reason=f"only {len(sheet)} wall lines on the services sheet ({MIN_WALLS} needed)"
        )
    if len(plan) < MIN_WALLS:
        return Refusal(reason=f"only {len(plan)} walls on the plan ({MIN_WALLS} needed)")
    length = _lengths(sheet)
    best: dict[int, tuple[float, float, float, np.ndarray]] = {}  # turn -> (share, pose)
    base = _rotation(plan, sheet)
    for turn in range(4):
        deg = base + 90.0 * turn
        guesses, searched = _guesses(plan, sheet, deg, expected_scale)
        for scale, shift in guesses:
            pose = _icp(plan, sheet, deg, scale, shift, searched)
            on, _ = _inliers(plan, sheet, *pose)
            share = float(length[on].sum() / max(length.sum(), 1e-12))
            if turn not in best or share > best[turn][0]:
                best[turn] = (share, *pose)
    ranked = sorted(best.values(), key=lambda p: -p[0])
    share, deg, scale, shift = ranked[0]
    for nudge in NUDGES:
        pose = _icp(plan, sheet, deg, scale * nudge, shift, (scale * 0.9, scale * 1.1))
        on, _ = _inliers(plan, sheet, *pose)
        nudged = float(length[on].sum() / max(length.sum(), 1e-12))
        if nudged > share:
            share, (deg, scale, shift) = nudged, pose
    on, _ = _inliers(plan, sheet, deg, scale, shift)
    if on.sum() >= MIN_WALLS:  # polish on the matched lines alone, each point alike: precise
        deg, scale, shift = _icp(
            plan, sheet[on], deg, scale, shift, (scale * 0.98, scale * 1.02), weighted=False
        )
    ranked[0] = (share, deg, scale, shift)
    on, rms = _inliers(plan, sheet, deg, scale, shift)
    hits = int(on.sum())
    if share < MIN_SHARE or hits < MIN_WALLS:
        return Refusal(
            reason=f"only {hits} of {len(sheet)} wall lines match ({share:.0%} of their length; "
            f"{MIN_SHARE:.0%} and {MIN_WALLS} lines needed)"
        )
    if ranked[1][0] * MARGIN > share:
        return Refusal(
            reason=f"wall lines match two ways ({share:.0%} and {ranked[1][0]:.0%} of their "
            "length): the sheet's turn is a guess"
        )
    cover = _extent(_place(_points(sheet), deg, scale, shift)) / max(_extent(_points(plan)), 1e-12)
    if not COVER[0] <= cover <= COVER[1]:
        return Refusal(
            reason=f"laid over, the sheet would span {cover:.0%} of the plan's size "
            f"({COVER[0]:.0%}-{COVER[1]:.0%} needed): another floor or a wrong scale"
        )
    off = abs((deg - base + 45.0) % 90.0 - 45.0)
    if off > TURN_DEG:
        return Refusal(
            reason=f"the fitted turn is {off:.1f} deg off the wall directions' (a forced fit)"
        )
    spread = _quadrants(sheet, on)
    if spread < QUADRANTS:
        return Refusal(
            reason=f"the matching wall lines lie in {spread} of the sheet's 4 quarters "
            f"({QUADRANTS} needed)"
        )
    deg = (deg + 180.0) % 360.0 - 180.0
    return Place(
        rotation_deg=deg,
        scale=scale,
        shift=(float(shift[0]), float(shift[1])),
        inliers=hits,
        of_total=len(sheet),
        rms_m=rms,
    )


def _ends(walls: Sequence[Segment]) -> np.ndarray:
    """(n, 2, 2): the `LONGEST` longest lines' two ends, lines with a non-finite point left out."""
    ends = np.array([[w.a, w.b] for w in walls], np.float64).reshape(-1, 2, 2)
    ends = ends[np.isfinite(ends).all(axis=(1, 2))]
    d = ends[:, 1] - ends[:, 0]
    with np.errstate(over="ignore"):
        length = np.hypot(d[:, 0], d[:, 1])
    return ends[np.argsort(-length, kind="stable")[:LONGEST]]


def _extent(points: np.ndarray) -> float:
    """The set's longer side between the `SPREAD` percentiles: strays left out."""
    lo, hi = np.percentile(points, SPREAD, axis=0)
    return float((hi - lo).max())


def _turn(deg: float) -> np.ndarray:
    t = math.radians(deg)
    return np.array([[math.cos(t), -math.sin(t)], [math.sin(t), math.cos(t)]])


def _rotation(plan: np.ndarray, sheet: np.ndarray) -> float:
    """The turn (deg, mod 180) that best lays the sheet's line directions on the plan's."""

    def histogram(ends: np.ndarray) -> np.ndarray:
        d = ends[:, 1] - ends[:, 0]
        angle = np.degrees(np.arctan2(d[:, 1], d[:, 0])) % 180.0
        h = np.bincount(
            np.floor(angle).astype(int) % 180, weights=np.hypot(d[:, 0], d[:, 1]), minlength=180
        )
        return np.convolve(np.r_[h[-2:], h, h[:2]], [1, 2, 3, 2, 1], "valid")  # +-2 deg blur

    spectrum = np.fft.fft(histogram(plan)) * np.conj(np.fft.fft(histogram(sheet)))
    corr: np.ndarray = np.real(np.fft.ifft(spectrum))
    return float(np.argmax(corr))


def _points(ends: np.ndarray, n: int = 3) -> np.ndarray:
    t = np.linspace(0.0, 1.0, n)[None, :, None]
    return (ends[:, :1] * (1 - t) + ends[:, 1:] * t).reshape(-1, 2)


def _guesses(
    plan: np.ndarray, sheet: np.ndarray, deg: float, expected: float | None = None
) -> tuple[list[tuple[float, np.ndarray]], tuple[float, float]]:
    """The `POSES` (scale, shift) pairs with the most votes at this turn, and the scale range
    searched. Votes are counted per occupied cell, so a far point costs no memory."""
    p = plan.reshape(-1, 2)  # line ends vote; corners are what two floors' walls share
    q = sheet.reshape(-1, 2) @ _turn(deg).T
    weight = np.repeat(_lengths(sheet), 2)  # a long line's ends weigh more than a stub's
    weight = np.tile(weight / max(float(weight.mean()), 1e-12), len(p))
    ratio, steps = (
        (_extent(p) / max(_extent(q), 1e-12), SCALES)
        if expected is None
        else (
            expected,
            PRIOR,
        )
    )
    found: list[tuple[float, float, np.ndarray]] = []
    for scale in ratio * steps:
        diffs = (p[:, None, :] - scale * q[None, :, :]).reshape(-1, 2)
        cells = np.clip(np.floor(diffs / VOTE_M), -(2.0**30), 2.0**30).astype(np.int64)
        keys, index = np.unique((cells[:, 0] << 32) + cells[:, 1], return_inverse=True)
        votes = np.bincount(index.ravel(), weights=weight)
        i = int(np.argmax(votes))
        cell = np.array([(keys[i] + 2**31) >> 32, ((keys[i] + 2**31) & 0xFFFFFFFF) - 2**31])
        found.append((float(votes[i]), float(scale), (cell + 0.5) * VOTE_M))
    found.sort(key=lambda f: -f[0])
    return [(s, t) for _, s, t in found[:POSES]], (ratio * steps[0], ratio * steps[-1])


def _nearest(points: np.ndarray, walls: np.ndarray) -> np.ndarray:
    """Each point's nearest point on any wall (by matrix products: no points x walls x 2)."""
    a, ab = walls[:, 0], walls[:, 1] - walls[:, 0]
    length2 = np.maximum((ab * ab).sum(1), 1e-12)
    pa = points @ ab.T - (a * ab).sum(1)  # (p - a) . ab
    t = np.clip(pa / length2, 0.0, 1.0)
    p_a2 = (points * points).sum(1)[:, None] - 2 * points @ a.T + (a * a).sum(1)  # |p - a|^2
    i = np.argmin(p_a2 - 2 * t * pa + t * t * length2, axis=1)
    return a[i] + t[np.arange(len(points)), i, None] * ab[i]


def _place(q: np.ndarray, deg: float, scale: float, shift: np.ndarray) -> np.ndarray:
    return scale * q @ _turn(deg).T + shift


def _icp(
    plan: np.ndarray,
    sheet: np.ndarray,
    deg: float,
    scale: float,
    shift: np.ndarray,
    searched: tuple[float, float],
    weighted: bool = True,
) -> tuple[float, float, np.ndarray]:
    """The pose (deg, scale, shift) refined by trimmed ICP with Umeyama's similarity, its scale
    kept in the `searched` range (left alone, ICP on lines that match nothing shrinks the sheet
    toward a point, where every line lies on a wall)."""
    q = _points(sheet, SAMPLES)
    # a long wall pulls more than a stub (finding the pose); alike (polishing it)
    weight = np.repeat(_lengths(sheet), SAMPLES) if weighted else np.ones(len(sheet) * SAMPLES)
    size = _extent(q) * scale
    moved = _place(q, deg, scale, shift)
    for _ in range(ICP_STEPS):
        target = _nearest(moved, plan)
        err = np.hypot(*(moved - target).T)
        keep = err <= np.quantile(err, TRIM)
        deg, fitted, shift = _umeyama(q[keep], target[keep], weight[keep])
        scale = min(max(fitted, searched[0]), searched[1])
        if scale != fitted:  # the shift that goes with the clamped scale
            gap = target[keep] - _place(q[keep], deg, scale, np.zeros(2))
            shift = np.average(gap, axis=0, weights=weight[keep])
        before, moved = moved, _place(q, deg, scale, shift)
        if np.abs(moved - before).max() <= SETTLED * size:
            break
    return deg, scale, shift


def _lengths(ends: np.ndarray) -> np.ndarray:
    d = ends[:, 1] - ends[:, 0]
    return np.hypot(d[:, 0], d[:, 1])


def _umeyama(
    src: np.ndarray, dst: np.ndarray, weight: np.ndarray
) -> tuple[float, float, np.ndarray]:
    """The similarity (deg, scale, shift) taking `src` closest to `dst`, by `weight` (no
    mirror)."""
    w = weight / max(float(weight.sum()), 1e-24)
    ms, md = w @ src, w @ dst
    s, d = src - ms, dst - md
    u, sv, vt = np.linalg.svd((d * w[:, None]).T @ s)
    sign = np.diag([1.0, np.sign(np.linalg.det(u @ vt)) or 1.0])
    r = u @ sign @ vt
    scale = float(np.trace(np.diag(sv) @ sign) / max(float(w @ (s * s).sum(1)), 1e-24))
    return math.degrees(math.atan2(r[1, 0], r[0, 0])), scale, md - scale * r @ ms


def _quadrants(sheet: np.ndarray, on: np.ndarray) -> int:
    """In how many quarters of the sheet (split at its lines' median middle) the `on` lines'
    middles lie."""
    middle = sheet.mean(axis=1)
    centre = np.median(middle, axis=0)
    right, below = middle[on, 0] >= centre[0], middle[on, 1] >= centre[1]
    return len(set(zip(right.tolist(), below.tolist(), strict=True)))


def _inliers(
    plan: np.ndarray, sheet: np.ndarray, deg: float, scale: float, shift: np.ndarray
) -> tuple[np.ndarray, float]:
    """Which sheet lines lie on a plan wall all along, and the rms of their points (m)."""
    moved = _place(_points(sheet, SAMPLES), deg, scale, shift)
    err = np.hypot(*(moved - _nearest(moved, plan)).T).reshape(len(sheet), SAMPLES)
    on = (err <= TOL_M).all(axis=1)
    rms = float(np.sqrt((err[on] ** 2).mean())) if on.any() else 0.0
    return on, rms

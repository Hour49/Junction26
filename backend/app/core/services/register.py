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
MIN_SHARE = 0.4  # services lines (pipes, ducts) are no walls: 40% of the sheet's lines on walls
MARGIN = 1.3  # the best pose must beat another quarter turn's by this, or it is a guess
SCALES = np.exp(np.linspace(math.log(0.5), math.log(2.0), 71))  # around the extents' ratio, 2%
VOTE_M = 0.5  # shift vote bin: wide enough for a 2% scale step across a floor
POSES = 6  # poses refined by ICP
ICP_STEPS = 25
TRIM = 0.7  # ICP fits the best 70% of points: missing walls and services lines fall out
SAMPLES = 5  # points per sheet line, ends included


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


def register(plan_walls: Sequence[Segment], sheet_walls: Sequence[Segment]) -> Place | Refusal:
    """How the sheet's lines land on the plan's walls, or why they cannot be laid over."""
    if len(sheet_walls) < MIN_WALLS:
        return Refusal(
            reason=f"only {len(sheet_walls)} wall lines on the services sheet ({MIN_WALLS} needed)"
        )
    if len(plan_walls) < MIN_WALLS:
        return Refusal(reason=f"only {len(plan_walls)} walls on the plan ({MIN_WALLS} needed)")
    plan = _ends(plan_walls)
    sheet = _ends(sheet_walls)
    needed = max(MIN_WALLS, math.ceil(MIN_SHARE * len(sheet)))
    best: dict[int, tuple[int, float, float, np.ndarray]] = {}  # turn -> pose, scored
    base = _rotation(plan, sheet)
    for turn in range(4):
        deg = base + 90.0 * turn
        for scale, shift in _guesses(plan, sheet, deg):
            pose = _icp(plan, sheet, deg, scale, shift)
            hits, _ = _inliers(plan, sheet, *pose)
            if turn not in best or hits > best[turn][0]:
                best[turn] = (hits, *pose)
    ranked = sorted(best.values(), key=lambda p: -p[0])
    hits, deg, scale, shift = ranked[0]
    if hits < needed:
        return Refusal(reason=f"only {hits} of {len(sheet)} wall lines match ({needed} needed)")
    if ranked[1][0] * MARGIN > hits:
        return Refusal(
            reason=f"wall lines match two ways ({hits} and {ranked[1][0]} of {len(sheet)}): "
            "the sheet's turn is a guess"
        )
    hits, rms = _inliers(plan, sheet, deg, scale, shift)
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
    """(n, 2, 2): each line's two ends."""
    return np.array([[w.a, w.b] for w in walls], np.float64)


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


def _guesses(plan: np.ndarray, sheet: np.ndarray, deg: float) -> list[tuple[float, np.ndarray]]:
    """The `POSES` (scale, shift) pairs with the most votes at this turn."""
    p = _points(plan)
    q = _points(sheet) @ _turn(deg).T
    ratio = float(np.ptp(p, axis=0).max() / max(np.ptp(q, axis=0).max(), 1e-12))
    found: list[tuple[int, float, np.ndarray]] = []
    for scale in ratio * SCALES:
        diffs = (p[:, None, :] - scale * q[None, :, :]).reshape(-1, 2)
        cells = np.floor(diffs / VOTE_M).astype(np.int64)
        cells -= cells.min(axis=0)
        width = int(cells[:, 1].max()) + 1
        counts = np.bincount(cells[:, 0] * width + cells[:, 1])
        i = int(np.argmax(counts))
        corner = np.floor(diffs.min(axis=0) / VOTE_M)
        cell = np.array([i // width, i % width]) + corner
        found.append((int(counts[i]), float(scale), (cell + 0.5) * VOTE_M))
    found.sort(key=lambda f: -f[0])
    return [(s, t) for _, s, t in found[:POSES]]


def _nearest(points: np.ndarray, walls: np.ndarray) -> np.ndarray:
    """Each point's nearest point on any wall."""
    a, b = walls[:, 0][None], walls[:, 1][None]
    ab = b - a
    t = np.clip(
        ((points[:, None] - a) * ab).sum(-1) / np.maximum((ab * ab).sum(-1), 1e-12), 0.0, 1.0
    )
    near = a + t[..., None] * ab
    i = np.argmin(((points[:, None] - near) ** 2).sum(-1), axis=1)
    return near[np.arange(len(points)), i]


def _place(q: np.ndarray, deg: float, scale: float, shift: np.ndarray) -> np.ndarray:
    return scale * q @ _turn(deg).T + shift


def _icp(
    plan: np.ndarray, sheet: np.ndarray, deg: float, scale: float, shift: np.ndarray
) -> tuple[float, float, np.ndarray]:
    """The pose (deg, scale, shift) refined by trimmed ICP with Umeyama's similarity."""
    q = _points(sheet, SAMPLES)
    for _ in range(ICP_STEPS):
        moved = _place(q, deg, scale, shift)
        target = _nearest(moved, plan)
        err = np.hypot(*(moved - target).T)
        keep = err <= np.quantile(err, TRIM)
        deg, scale, shift = _umeyama(q[keep], target[keep])
    return deg, scale, shift


def _umeyama(src: np.ndarray, dst: np.ndarray) -> tuple[float, float, np.ndarray]:
    """The similarity (deg, scale, shift) taking `src` closest to `dst` (no mirror)."""
    ms, md = src.mean(0), dst.mean(0)
    s, d = src - ms, dst - md
    u, sv, vt = np.linalg.svd(d.T @ s / len(src))
    sign = np.diag([1.0, np.sign(np.linalg.det(u @ vt)) or 1.0])
    r = u @ sign @ vt
    scale = float(np.trace(np.diag(sv) @ sign) / max((s * s).sum() / len(src), 1e-24))
    return math.degrees(math.atan2(r[1, 0], r[0, 0])), scale, md - scale * r @ ms


def _inliers(
    plan: np.ndarray, sheet: np.ndarray, deg: float, scale: float, shift: np.ndarray
) -> tuple[int, float]:
    """Sheet lines lying on a plan wall all along, and the rms of their points (m)."""
    moved = _place(_points(sheet, SAMPLES), deg, scale, shift)
    err = np.hypot(*(moved - _nearest(moved, plan)).T).reshape(len(sheet), SAMPLES)
    on = (err <= TOL_M).all(axis=1)
    rms = float(np.sqrt((err[on] ** 2).mean())) if on.any() else 0.0
    return int(on.sum()), rms

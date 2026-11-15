"""Page cleanup before the picture readers (picture bar 2): a scan's salt and pepper taken out by
a 3x3 median, uneven light flattened by dividing by the page's blurred paper, and a page turned
by up to `MAX_TURN` degrees turned back. A clean export is left as it is: the median runs only on
a page with salt (it would take out one-pixel lines), and a turn under `MIN_TURN` is not undone.
`to_clean` and `to_page` move boxes between the page as given and the cleaned one.
"""

from typing import NamedTuple

import cv2
import numpy as np

from app.core.drawing.model import Box

TURN_INK = 235  # grey level below which a pixel counts for the turn: grey walls are the long lines
SALT = 0.0002  # share of lone pixels (all 8 neighbours far from it) from which a page is salted
LONE = 100  # grey levels a lone pixel differs from each of its neighbours, at least
PAPER_SIDE = 160  # px: the page's long side when its paper is estimated
PAPER_INK = 5  # px on that small page: ink thinner than this is taken off the paper estimate
MAX_TURN = 2.0  # degrees
MIN_TURN = 0.1  # degrees: a smaller turn is left
TURN_SIDE = 1000  # px: the page's long side when its turn is estimated
STEPS = (0.1, 0.02)  # degrees: the coarse then the fine search step


class Cleaned(NamedTuple):
    gray: np.ndarray  # the cleaned page, the size of the given one
    angle: float  # degrees the page was turned (counter-clockwise), now undone; 0 when not
    turn: np.ndarray  # 2x3: given page pixels -> cleaned page pixels
    salted: bool = False  # the page had salt and pepper: a scan, not a clean export


def clean_page(gray: np.ndarray, straighten: bool = True) -> Cleaned:
    """The grey page with its salt out, its light even and (`straighten`) its turn undone."""
    salted = _salted(gray)
    out = cv2.medianBlur(gray, 3) if salted else gray
    out = _flattened(out)
    angle = _turn(out) if straighten else 0.0
    height, width = out.shape
    if abs(angle) < MIN_TURN:
        return Cleaned(out, 0.0, np.array([[1.0, 0, 0], [0, 1.0, 0]]), salted)
    turn = cv2.getRotationMatrix2D((width / 2, height / 2), -angle, 1.0)
    out = cv2.warpAffine(out, turn, (width, height), flags=cv2.INTER_LINEAR, borderValue=255)
    return Cleaned(out, angle, turn, salted)


def to_clean(box: Box, cleaned: Cleaned) -> Box:
    """A box (page fractions) on the page as given -> its box on the cleaned page."""
    return _moved(box, cleaned.turn, cleaned.gray.shape)


def to_page(box: Box, cleaned: Cleaned) -> Box:
    """A box (page fractions) on the cleaned page -> its box on the page as given."""
    return _moved(box, cv2.invertAffineTransform(cleaned.turn), cleaned.gray.shape)


def _moved(box: Box, turn: np.ndarray, shape: tuple[int, ...]) -> Box:
    height, width = shape[:2]
    x0, y0, x1, y1 = box[0] * width, box[1] * height, box[2] * width, box[3] * height
    corners = np.array([(x0, y0, 1), (x1, y0, 1), (x1, y1, 1), (x0, y1, 1)]) @ turn.T
    xs, ys = corners[:, 0] / width, corners[:, 1] / height
    return (
        round(float(max(0.0, xs.min())), 5),
        round(float(max(0.0, ys.min())), 5),
        round(float(min(1.0, xs.max())), 5),
        round(float(min(1.0, ys.max())), 5),
    )


def _salted(gray: np.ndarray) -> bool:
    """Whether the page has salt or pepper: lone pixels far from all 8 neighbours."""
    ring = np.ones((3, 3), np.uint8)
    ring[1, 1] = 0
    page = gray.astype(np.int16)
    darkest = cv2.erode(gray, ring).astype(np.int16)  # of the 8 neighbours
    lightest = cv2.dilate(gray, ring).astype(np.int16)
    lone = (page - lightest >= LONE) | (darkest - page >= LONE)
    return bool(lone.mean() >= SALT)


def _flattened(gray: np.ndarray) -> np.ndarray:
    """The page divided by its paper: the brightest grey around each spot (ink taken off on a
    shrunk page), blurred; paper becomes white wherever the light fell."""
    height, width = gray.shape
    shrink = min(1.0, PAPER_SIDE / max(height, width))
    small = cv2.resize(gray, None, fx=shrink, fy=shrink, interpolation=cv2.INTER_AREA)
    paper = cv2.dilate(small, np.ones((PAPER_INK, PAPER_INK), np.uint8))
    paper = cv2.GaussianBlur(paper, (0, 0), PAPER_INK)
    paper = cv2.resize(paper, (width, height), interpolation=cv2.INTER_LINEAR)
    flat = gray.astype(np.float32) * 255 / np.maximum(paper.astype(np.float32), 1)
    return np.clip(flat, 0, 255).astype(np.uint8)


def _turn(gray: np.ndarray) -> float:
    """The page's turn in degrees (counter-clockwise), within MAX_TURN: the angle at which its
    ink's rows and columns are sharpest (walls and symbols are drawn square to the page)."""
    height, width = gray.shape
    shrink = min(1.0, TURN_SIDE / max(height, width))
    small = cv2.resize(gray, None, fx=shrink, fy=shrink, interpolation=cv2.INTER_AREA)
    ink = (small < TURN_INK).astype(np.float32)
    if not ink.any():
        return 0.0
    centre = (ink.shape[1] / 2, ink.shape[0] / 2)

    def sharpness(angle: float) -> float:
        turn = cv2.getRotationMatrix2D(centre, -angle, 1.0)
        turned = cv2.warpAffine(ink, turn, (ink.shape[1], ink.shape[0]), flags=cv2.INTER_LINEAR)
        return float((turned.sum(axis=1) ** 2).sum() + (turned.sum(axis=0) ** 2).sum())

    best = 0.0
    for step, reach in zip(STEPS, (MAX_TURN, STEPS[0]), strict=True):
        angles = best + np.arange(-reach, reach + step / 2, step)
        best = float(max(angles, key=sharpness))
    return round(best, 3)

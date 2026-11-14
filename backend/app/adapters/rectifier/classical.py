"""R1c `classical_contrast` (photo experiment, prototypes/photo/rectify.py): find the paper in a
phone photo as a quadrilateral and undo the perspective with one homography.

Candidate quads come from five sheet masks (Otsu on lightness minus saturation, the top class of
a 3-class Otsu, gradient edges at three floors), each closed, hole-filled and opened; the largest
blob's hull gives the quad, its sides refined by line fits. The quad kept is the one whose border
is most sheet-like: per side, the median lightness just inside minus just outside, the weakest
side counting. Below MIN_CONTRAST nothing is sheet-like and no quad is returned. On synthetic
photos it finds the sheet within 2% of its diagonal in 99% (mild) to 89% (hard) of photos; on 30
real Commons photos it fires on 7, all of them right (.agents/exp/photo.md).
"""

import math

import cv2
import numpy as np
from numpy.typing import NDArray

Image = NDArray[np.uint8]  # RGB, height x width x 3
Corners = NDArray[np.float64]  # (4, 2) pixels, top left, top right, bottom right, bottom left

WORK = 900  # the long side the masks are made at
MASKS = ("otsu", "otsu3", "edges20", "edges40", "edges80")
MIN_QUALITY = 0.85  # blob area / quad area: how quad-like the blob is
MIN_CONTRAST = 6.0  # lightness levels (0-255) inside minus outside, on the weakest side


def order_corners(points: NDArray[np.float64]) -> Corners:
    """Top left, top right, bottom right, bottom left: clockwise from the corner nearest the
    image's top left."""
    centre = points.mean(0)
    angle = np.arctan2(points[:, 1] - centre[1], points[:, 0] - centre[0])
    points = points[np.argsort(angle)]
    return np.roll(points, -int(np.argmin(points.sum(1))), axis=0)


def quad_size(quad: Corners) -> tuple[int, int]:
    width = max(np.linalg.norm(quad[1] - quad[0]), np.linalg.norm(quad[2] - quad[3]))
    height = max(np.linalg.norm(quad[3] - quad[0]), np.linalg.norm(quad[2] - quad[1]))
    return max(1, round(float(width))), max(1, round(float(height)))


def warp_quad(photo: Image, quad: Corners) -> Image:
    """The paper inside `quad`, seen straight on, at the size of its longer sides."""
    width, height = quad_size(quad)
    target = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]])
    homography = cv2.getPerspectiveTransform(quad.astype(np.float32), target.astype(np.float32))
    flat = cv2.warpPerspective(
        photo, homography, (width, height), flags=cv2.INTER_CUBIC, borderValue=(255, 255, 255)
    )
    return np.asarray(flat, np.uint8)


def find_quad(photo: Image) -> Corners | None:
    """The most sheet-like quad (photo pixels) over the candidate masks, or None."""
    best, best_contrast = None, -math.inf
    for method in MASKS:
        mask, scale = _sheet_mask(photo, method)
        found = _quad_from_mask(mask)
        if found is None or found[1] < MIN_QUALITY:
            continue
        quad = found[0] / scale
        contrast = _border_contrast(photo, quad)
        if contrast > best_contrast + 10:  # ties go to the earlier (tighter) masks
            best, best_contrast = quad, contrast
    return best if best_contrast >= MIN_CONTRAST else None


def _work(photo: Image) -> tuple[Image, float, int]:
    scale = WORK / max(photo.shape[:2])
    small = cv2.resize(photo, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    return np.asarray(small, np.uint8), scale, max(3, int(WORK * 0.02)) | 1


def _sheet_mask(photo: Image, method: str) -> tuple[NDArray[np.uint8], float]:
    small, scale, k = _work(photo)
    hsv = cv2.cvtColor(small, cv2.COLOR_RGB2HSV)
    light = cv2.GaussianBlur(hsv[..., 2], (0, 0), 2)
    saturation = cv2.GaussianBlur(hsv[..., 1], (0, 0), 2)
    score = cv2.subtract(light, (saturation.astype(np.float32) * 0.7).astype(np.uint8))
    if method == "otsu":
        _, mask = cv2.threshold(score, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    elif method == "otsu3":
        quarter = cv2.resize(score, None, fx=0.25, fy=0.25, interpolation=cv2.INTER_AREA)
        mask = np.where(score > _otsu3_top(np.asarray(quarter, np.uint8)), 255, 0)
    else:  # edgesN: gradient magnitude of the blurred lightness above N (or its 80th percentile)
        lab = cv2.cvtColor(small, cv2.COLOR_RGB2LAB)[..., 0].astype(np.float32)
        lab = cv2.GaussianBlur(lab, (0, 0), 1.5)
        magnitude = cv2.magnitude(
            cv2.Sobel(lab, cv2.CV_32F, 1, 0), cv2.Sobel(lab, cv2.CV_32F, 0, 1)
        )
        floor = max(float(method.removeprefix("edges")), float(np.percentile(magnitude, 80)))
        mask = cv2.dilate(
            np.where(magnitude > floor, 255, 0).astype(np.uint8),
            cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)),
        )
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k, k))
    mask = cv2.morphologyEx(np.asarray(mask, np.uint8), cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(_fill_holes(np.asarray(mask, np.uint8)), cv2.MORPH_OPEN, kernel)
    return np.asarray(mask, np.uint8), scale


def _otsu3_top(image: NDArray[np.uint8]) -> int:
    """The upper threshold of a 3-class Otsu."""
    histogram = np.bincount(image.ravel(), minlength=256).astype(float)
    p = histogram / histogram.sum()
    c0, c1 = np.cumsum(p), np.cumsum(p * np.arange(256))
    best, best_t = -1.0, 255
    for t1 in range(1, 254):
        for t2 in range(t1 + 1, 255):
            weights = (c0[t1], c0[t2] - c0[t1], 1 - c0[t2])
            if min(weights) <= 0:
                continue
            means = (c1[t1], c1[t2] - c1[t1], c1[-1] - c1[t2])
            between = sum(m * m / w for m, w in zip(means, weights, strict=True))
            if between > best:
                best, best_t = between, t2
    return best_t


def _fill_holes(mask: NDArray[np.uint8]) -> NDArray[np.uint8]:
    """The mask plus every background component that does not touch the border."""
    _, labels = cv2.connectedComponents(cv2.bitwise_not(mask), connectivity=4)
    border = np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))
    out = mask.copy()
    out[~np.isin(labels, border) & (labels > 0)] = 255
    return out


def _quad_from_mask(mask: NDArray[np.uint8]) -> tuple[Corners, float] | None:
    """Corners (work pixels) of the largest blob, and blob area / quad area."""
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        return None
    contour = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(contour)
    if area < 0.1 * mask.size or area > 0.97 * mask.size:
        return None
    hull = cv2.convexHull(contour)
    perimeter = cv2.arcLength(hull, True)
    quad = None
    for eps in np.linspace(0.01, 0.1, 19):
        approx = cv2.approxPolyDP(hull, eps * perimeter, True)
        if len(approx) == 4:
            quad = approx.reshape(4, 2).astype(float)
            break
    if quad is None:
        quad = cv2.boxPoints(cv2.minAreaRect(contour)).astype(float)
    quad = order_corners(quad)
    refined = _refined(quad, contour.reshape(-1, 2).astype(float))
    if np.abs(refined - quad).max() > 0.05 * max(mask.shape):
        refined = quad  # a line fit ran off: keep the hull corners
    quad_area = cv2.contourArea(refined.astype(np.float32))
    quality = min(area, quad_area) / max(area, quad_area) if quad_area > 0 else 0.0
    return refined, quality


def _refined(quad: Corners, outline: NDArray[np.float64]) -> Corners:
    """Each corner where the line fits of its two sides meet (outline points near each side,
    away from the corners)."""
    lines: list[tuple[NDArray[np.float64], NDArray[np.float64]]] = []
    for i in range(4):
        a, b = quad[i], quad[(i + 1) % 4]
        ab = b - a
        length = float(np.linalg.norm(ab))
        t = ((outline - a) @ ab) / length**2
        distance = np.abs(ab[0] * (outline[:, 1] - a[1]) - ab[1] * (outline[:, 0] - a[0])) / length
        near = outline[(t > 0.1) & (t < 0.9) & (distance < 0.03 * length)]
        if len(near) >= 10:
            vx, vy, x0, y0 = cv2.fitLine(near.astype(np.float32), cv2.DIST_HUBER, 0, 0.01, 0.01)
            lines.append((np.array([x0[0], y0[0]]), np.array([vx[0], vy[0]])))
        else:
            lines.append((a, ab / length))
    corners = []
    for i in range(4):
        (p, r), (q, s) = lines[i - 1], lines[i]
        den = r[0] * s[1] - r[1] * s[0]
        if abs(den) < 1e-9:
            corners.append(quad[i])
        else:
            corners.append(p + ((q[0] - p[0]) * s[1] - (q[1] - p[1]) * s[0]) / den * r)
    return np.array(corners)


def _border_contrast(photo: Image, quad: Corners) -> float:
    """Per side, median lightness just inside minus just outside (bands of 1.5% of the side);
    the weakest side counts."""
    small, scale, _ = _work(photo)
    light = cv2.cvtColor(small, cv2.COLOR_RGB2LAB)[..., 0].astype(np.float32)
    corners = quad * scale
    centre = corners.mean(0)
    height, width = light.shape
    worst = math.inf
    for i in range(4):
        a, b = corners[i], corners[(i + 1) % 4]
        points = a + (b - a) * np.linspace(0.15, 0.85, 40)[:, None]
        normal = np.array([-(b - a)[1], (b - a)[0]])
        normal /= np.linalg.norm(normal) + 1e-9
        if np.dot(centre - points.mean(0), normal) < 0:
            normal = -normal  # point inward
        step = max(3.0, 0.015 * float(np.linalg.norm(b - a)))
        sides = []
        for sign in (1, -1):
            band = points + sign * step * normal
            x = np.clip(band[:, 0].round().astype(int), 0, width - 1)
            y = np.clip(band[:, 1].round().astype(int), 0, height - 1)
            sides.append(float(np.median(light[y, x])))
        worst = min(worst, sides[0] - sides[1])
    return worst

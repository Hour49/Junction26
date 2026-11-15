"""Room outlines for a raster plan: a rooms reader gives each room a label box; this gives it the
free space its label sits in, bounded by the drawn walls.

The page is binarised and thin strokes (text, furniture, dimension lines) are opened away; the
thick dark mass left is the wall mask. Gaps in it up to a door's width are closed, so a door
opening does not let one room into the next. A label's region is the connected free space under
its centre; labels sharing a region (an open space) split it by nearest label centre. A region
that fills a large part of the page or touches its edge leaked outside the flat: that room keeps
its box (no polygon).

`RoomOutlines(inner, files)` wraps any rooms `Extractor`; only `Room.polygon` is set.
"""

import io

import cv2
import numpy as np
from PIL import Image

from app.core.drawing.model import Room
from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from app.core.pipeline.ports import DrawingFiles, Extractor

WORK_SIDE = 1200  # the page is shrunk to this long side, so the numbers below are fractions of it
STROKE = 0.0030  # strokes thinner than this (of the long side) are not walls
DOOR = 0.035  # (of the long side) a wall gap up to twice this, a door opening, is closed
LONG_LINE = 0.05  # a straight stroke this long (of the long side) is a wall
MAX_SHARE = 0.40  # a region over this share of the page leaked
MAX_POINTS = 40


def solid_walls(gray: np.ndarray) -> np.ndarray:
    """Thick dark strokes of a grayscale page (uint8 0/255): thin lines and text opened away."""
    _, dark = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    side = max(gray.shape)
    k = max(3, round(STROKE * side))
    thick = cv2.morphologyEx(dark, cv2.MORPH_OPEN, np.ones((k, k), np.uint8))
    # a long straight stroke, however thin, is a wall too: a window drawn as lines in a wall gap
    n = max(k + 1, round(LONG_LINE * side))
    straight = cv2.morphologyEx(dark, cv2.MORPH_OPEN, np.ones((1, n), np.uint8))
    upright = cv2.morphologyEx(dark, cv2.MORPH_OPEN, np.ones((n, 1), np.uint8))
    return cv2.bitwise_or(cv2.bitwise_or(thick, straight), upright)


def bridged(walls: np.ndarray) -> np.ndarray:
    """The walls with every gap up to about a door closed (a morphological closing: it adds a
    bar across a gap and thickens nothing else)."""
    r = max(1, round(DOOR * max(walls.shape)))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    return cv2.morphologyEx(walls, cv2.MORPH_CLOSE, kernel)


def regions(walls: np.ndarray, centres: list[tuple[int, int]]) -> list[np.ndarray | None]:
    """The pixels of each centre's room (bool masks), or None where the centre is on a wall or
    the region leaked. Centres in one free region split it by the nearest centre."""
    h, w = walls.shape
    _, labels = cv2.connectedComponents((walls == 0).astype(np.uint8), connectivity=4)
    out: list[np.ndarray | None] = [None] * len(centres)
    by_region: dict[int, list[int]] = {}
    for i, (x, y) in enumerate(centres):
        if 0 <= x < w and 0 <= y < h and labels[y, x] != 0 and walls[y, x] == 0:
            by_region.setdefault(int(labels[y, x]), []).append(i)
    for region, members in by_region.items():
        mask = labels == region
        edge = mask[0].any() or mask[-1].any() or mask[:, 0].any() or mask[:, -1].any()
        if edge or mask.sum() > MAX_SHARE * w * h:
            continue
        if len(members) == 1:
            out[members[0]] = mask
            continue
        ys, xs = np.nonzero(mask)
        d = np.stack([(xs - centres[i][0]) ** 2 + (ys - centres[i][1]) ** 2 for i in members])
        nearest = d.argmin(axis=0)
        for n, i in enumerate(members):
            part = np.zeros_like(mask)
            part[ys[nearest == n], xs[nearest == n]] = True
            out[i] = part
    return out


def seeds(solid: np.ndarray, centres: list[tuple[int, int]], got: list[np.ndarray | None]) -> None:
    """For a centre the closing swallowed (a small room between thick things), its pixels
    in the open walls' free space, when they are a small closed pocket. Fills `got` in place."""
    h, w = solid.shape
    _, labels = cv2.connectedComponents((solid == 0).astype(np.uint8), connectivity=4)
    for i, (x, y) in enumerate(centres):
        if got[i] is not None or not (0 <= x < w and 0 <= y < h) or labels[y, x] == 0:
            continue
        mask = labels == labels[y, x]
        edge = mask[0].any() or mask[-1].any() or mask[:, 0].any() or mask[:, -1].any()
        if not edge and mask.sum() <= MAX_SHARE * w * h:
            got[i] = mask


def regrown(
    masks: list[np.ndarray | None], solid: np.ndarray, steps: int
) -> list[np.ndarray | None]:
    """Each mask grown `steps` pixels into the free space the closing took (never onto a solid
    wall, never onto another room): a contested pixel goes to the first room that reaches it."""
    owner = np.zeros(solid.shape, np.int32)
    owner[solid > 0] = -1
    for k, mask in enumerate(masks, start=1):
        if mask is not None:
            owner[mask & (owner == 0)] = k
    kernel = np.ones((3, 3), np.uint8)
    for _ in range(steps):
        for k, mask in enumerate(masks, start=1):
            if mask is None:
                continue
            reach = cv2.dilate((owner == k).astype(np.uint8), kernel) > 0
            owner[reach & (owner == 0)] = k
    return [None if m is None else owner == k for k, m in enumerate(masks, start=1)]


def outline(mask: np.ndarray) -> tuple[tuple[float, float], ...] | None:
    """The largest outer contour of `mask`, simplified to at most MAX_POINTS corners, in page
    fractions."""
    h, w = mask.shape
    pixels = mask.astype(np.uint8) * 255
    found, _ = cv2.findContours(pixels, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not found:
        return None
    contour = max(found, key=cv2.contourArea)
    eps = 0.002 * max(w, h)
    approx = cv2.approxPolyDP(contour, eps, True)
    while len(approx) > MAX_POINTS:
        eps *= 1.3
        approx = cv2.approxPolyDP(contour, eps, True)
    if len(approx) < 3:
        return None
    return tuple(
        (round(min(1.0, max(0.0, float(x) / w)), 5), round(min(1.0, max(0.0, float(y) / h)), 5))
        for x, y in approx.reshape(-1, 2)
    )


def outlines(image: Image.Image, rooms: tuple[Room, ...]) -> tuple[Room, ...]:
    """`rooms` with `polygon` set where the page's walls close the room in."""
    gray = np.asarray(image.convert("L"))
    scale = min(1.0, WORK_SIDE / max(gray.shape))
    if scale < 1:
        size = (round(gray.shape[1] * scale), round(gray.shape[0] * scale))
        gray = cv2.resize(gray, size, interpolation=cv2.INTER_AREA)
    h, w = gray.shape
    solid = solid_walls(gray)
    for r in rooms:  # a room's own label is not a wall, however bold
        x0, y0, x1, y1 = r.box
        solid[
            max(0, int(y0 * h) - 2) : int(y1 * h) + 3, max(0, int(x0 * w) - 2) : int(x1 * w) + 3
        ] = 0
    walls = bridged(solid)
    todo = [r for r in rooms if r.polygon is None]
    centres = [
        (round((r.box[0] + r.box[2]) / 2 * w), round((r.box[1] + r.box[3]) / 2 * h)) for r in todo
    ]
    shaped: dict[str, tuple[tuple[float, float], ...]] = {}
    found = regions(walls, centres)
    seeds(solid, centres, found)
    steps = round(DOOR * max(w, h)) + 2  # back across what the closing filled
    for room, mask in zip(todo, regrown(found, solid, steps), strict=True):
        if mask is not None and (ring := outline(mask)):
            shaped[room.id] = ring
    return tuple(
        r.model_copy(update={"polygon": shaped[r.id]}) if r.id in shaped else r for r in rooms
    )


class RoomOutlines:
    def __init__(self, inner: Extractor, files: DrawingFiles) -> None:
        self._inner = inner
        self._files = files

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        found = self._inner.extract(source, sheet)
        if not found.rooms:
            return found
        with Image.open(io.BytesIO(self._files.read(source.path))) as image:
            rooms = outlines(image, found.rooms)
        shaped = sum(r.polygon is not None for r in rooms) - sum(
            r.polygon is not None for r in found.rooms
        )
        note = f"room outlines: {shaped} of {len(found.rooms)} rooms closed in by walls"
        return found.model_copy(update={"rooms": rooms, "notes": (*found.notes, note)})

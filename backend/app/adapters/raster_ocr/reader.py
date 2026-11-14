"""Room labels of a raster plan, read with an OCR engine (prototypes/ocr arm A).

The page is enlarged with Lanczos when it is small, the engine finds the text boxes, and each box
is cut out and read eight ways: turned 0, 90, 180 and 270 degrees, as printed and mirrored. A crop
names a room when one of its readings folds to a label of the room label table (labels.py); the
best-scored such reading wins. One sheet in two is turned and a few are printed mirrored, so the
mirrored family is kept for the whole sheet when its readings score more than the plain ones.

The engine is behind `TextEngine`, so the rules here are tested with a fake one; `RapidOcrEngine`
is the real one (rapidocr 3.10, PP-OCRv6 small detection and recognition, onnxruntime, CPU).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import cv2
import numpy as np
from PIL import Image

from app.adapters.raster_ocr.labels import room_type
from app.core.drawing.model import Room

LONG_SIDE = 3000  # a page is enlarged until its long side reaches this, at most UPSCALE times
UPSCALE = 2.0
MIN_SCORE = 0.5  # a reading the recogniser is less sure of names nothing
TURNS = (0, 1, 2, 3)  # quarter turns, counter-clockwise (numpy rot90)
Quad = Sequence[Sequence[float]]  # a text box's four corners, in pixels of the image read


class TextEngine(Protocol):
    def detect(self, image: np.ndarray) -> list[Quad]:
        """The text boxes on an RGB image (H x W x 3, uint8)."""
        ...

    def recognise(self, crops: Sequence[np.ndarray]) -> list[tuple[str, float]]:
        """The text and score of each crop, read as given."""
        ...

    def cut(self, image: np.ndarray, quad: Quad) -> np.ndarray:
        """The text box `quad` cut out of `image`, lying flat (`crop` is the simple cutter)."""
        ...


@dataclass(frozen=True)
class Reading:
    text: str
    score: float
    turn: int  # quarter turns of the crop
    mirrored: bool


@dataclass(frozen=True)
class RoomLabels:
    rooms: tuple[Room, ...]
    notes: tuple[str, ...]


def crop(image: np.ndarray, quad: Quad) -> np.ndarray:
    """The axis-aligned box around `quad`; a crop much taller than wide is turned to lie flat,
    as the engine's own cutter does."""
    xs = [p[0] for p in quad]
    ys = [p[1] for p in quad]
    h, w = image.shape[:2]
    x1, x2 = max(0, int(min(xs))), min(w, int(np.ceil(max(xs))))
    y1, y2 = max(0, int(min(ys))), min(h, int(np.ceil(max(ys))))
    part = image[y1:y2, x1:x2]
    if part.shape[1] and part.shape[0] / part.shape[1] >= 1.5:
        part = np.rot90(part)
    return np.ascontiguousarray(part)


def variants(part: np.ndarray) -> list[tuple[np.ndarray, int, bool]]:
    out: list[tuple[np.ndarray, int, bool]] = []
    for mirrored in (False, True):
        base = part[:, ::-1] if mirrored else part
        out.extend((np.ascontiguousarray(np.rot90(base, k)), k, mirrored) for k in TURNS)
    return out


def best_hits(readings: Sequence[Sequence[Reading]]) -> list[Reading | None]:
    """Per crop, the best reading that names a room, from the family (plain or mirrored) whose
    best readings score more over the sheet; None for a crop that names no room."""
    best: list[dict[bool, Reading]] = []
    for crop_readings in readings:
        found: dict[bool, Reading] = {}
        for reading in crop_readings:
            if reading.score < MIN_SCORE or room_type(reading.text) is None:
                continue
            kept = found.get(reading.mirrored)
            if kept is None or reading.score > kept.score:
                found[reading.mirrored] = reading
        best.append(found)
    weight = {f: sum(found[f].score for found in best if f in found) for f in (False, True)}
    mirrored = weight[True] > weight[False]
    return [found.get(mirrored) for found in best]


class RoomLabelReader:
    """Reads one raster page into rooms: one per printed label the table knows, `type` from the
    table, `label` the text as read, `box` the label's box in page fractions, `attrs.score` the
    recogniser's score, `attrs.turn` how the label was turned on the page."""

    def __init__(self, engine: TextEngine) -> None:
        self._engine = engine

    def read(self, image: Image.Image) -> RoomLabels:
        rgb = image.convert("RGB")
        w, h = rgb.size
        scale = max(1.0, min(UPSCALE, LONG_SIDE / max(w, h)))
        pixels = np.asarray(rgb)
        if scale > 1:  # OpenCV's Lanczos, as the measured arm used (PIL's differs slightly)
            size = (round(w * scale), round(h * scale))
            pixels = cv2.resize(pixels, size, interpolation=cv2.INTER_LANCZOS4)
        quads = self._engine.detect(pixels)
        crops = [self._engine.cut(pixels, quad) for quad in quads]
        turned = [variants(part) for part in crops if part.size]
        quads = [quad for quad, part in zip(quads, crops, strict=True) if part.size]
        texts = self._engine.recognise([v[0] for vs in turned for v in vs])
        per_crop = len(TURNS) * 2
        readings = [
            [
                Reading(text=t, score=s, turn=k, mirrored=m)
                for (t, s), (_, k, m) in zip(
                    texts[i * per_crop : (i + 1) * per_crop], turned[i], strict=True
                )
            ]
            for i in range(len(turned))
        ]
        rooms: list[Room] = []
        turns: dict[str, int] = {}
        for quad, hit in zip(quads, best_hits(readings), strict=True):
            kind = room_type(hit.text) if hit else None
            if hit is None or kind is None:
                continue
            how = f"{90 * hit.turn}" + (" mirrored" if hit.mirrored else "")
            turns[how] = turns.get(how, 0) + 1
            xs = [float(p[0]) / scale / w for p in quad]
            ys = [float(p[1]) / scale / h for p in quad]
            box = (max(0.0, min(xs)), max(0.0, min(ys)), min(1.0, max(xs)), min(1.0, max(ys)))
            attrs: dict[str, Any] = {"score": round(hit.score, 4), "turn": how}
            rooms.append(
                Room(
                    id=f"r{len(rooms) + 1}",
                    type=kind,
                    label=hit.text.strip(),
                    page=1,
                    box=box,
                    outdoor=kind in ("balcony", "outdoor"),
                    attrs=attrs,
                )
            )
        notes = [f"room labels read by OCR: {len(quads)} text boxes, {len(rooms)} name a room"]
        if turns:
            notes.append(f"labels read turned {max(turns, key=lambda k: turns[k])} most often")
        return RoomLabels(rooms=tuple(rooms), notes=tuple(notes))

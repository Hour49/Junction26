"""PRINTED_OCR_CHECK=on: the OCR tokens around the printed values the Carbon reader gave, for
the core check (app/core/pipeline/printed_ocr.py).

What is read. Each printed fact's box (Carbon's `box_2d`), padded by PAD of the page, cut out of
the image at its own resolution (crops, not the letterboxed page: a fact's digits on a 10200 px
sheet are a few px tall once the page is shrunk). The scale text has no box in Carbon's reply, so
the whole sheet is read for it, but only when the sheet has at most `whole_sheet_px` pixels: on
T1 (14000 x 9902) a whole-sheet pass took longer than the 20 s the task allows (measured in the
PR), so a big sheet's scale text is not checked ("not found" changes nothing).

How (Partanen 2025 on engineering drawings; docs/research/pdf-accuracy/scanned.md #6, #7):
- a region larger than TILE px is read in TILE px tiles overlapping by OVERLAP, and a token read
  twice on a seam is kept once (the same text, boxes overlapping, the better score kept);
- a region lower than MIN_HEIGHT px is enlarged to it (Lanczos): the recogniser reads lines at 48;
- long horizontal and vertical ruling lines (at least RULE_PX long: table borders, underlines)
  are removed before reading, by a morphological open and a subtraction: a digit touching a
  table line is otherwise read with it;
- each text box is read upright and turned 180 degrees, and a short one (neither side 1.5x the
  other: rapidocr only turns a crop it finds tall) also at 90 and 270; the best score wins
  (a four-way vote read 192/192 labels against 83/192 upright only, lit-campaign).
"""

import io
from collections.abc import Sequence

import cv2
import numpy as np
from PIL import Image

from app.adapters.raster_ocr.reader import Quad, TextEngine
from app.core.drawing.model import Box
from app.core.pipeline.model import DrawingFile, Sheet
from app.core.pipeline.ports import DrawingFiles
from app.core.pipeline.printed import PrintedSheet
from app.core.pipeline.printed_ocr import OcrToken

TILE = 1600  # px: PP-OCR's detector is trained on pages of about this size
OVERLAP = 0.05  # of a tile, shared with the next one
MIN_HEIGHT = 48  # px: the recogniser's line height
PAD = 0.004  # of the page, around Carbon's box: its boxes sit tight on the text or a little off
RULE_PX = 100  # px: a straight dark run this long is a ruling line, never part of a glyph
SHORT = 1.5  # a box with neither side this many times the other is read four ways
WHOLE_SHEET_PX = 40_000_000  # px: larger sheets are not read whole (T1's 139 MP took too long)
SAME_BOX = 0.5  # two readings of one text whose boxes overlap this much (of the smaller) are one


class PrintedOcr:
    """The `tokens` OCR reads around a sheet's printed values (page 1: a raster sheet's image)."""

    def __init__(
        self, engine: TextEngine, files: DrawingFiles, whole_sheet_px: int = WHOLE_SHEET_PX
    ) -> None:
        self._engine = engine
        self._files = files
        self._whole_sheet_px = whole_sheet_px

    def tokens(self, source: DrawingFile, sheet: Sheet, printed: PrintedSheet) -> list[OcrToken]:
        regions = joined([_padded(f.box) for f in printed.printed_facts if f.box and f.page == 1])
        if not sheet.pages or not (regions or printed.printed_scale):
            return []
        try:
            image = Image.open(io.BytesIO(self._files.read(source.path)))
            image.load()
        except (OSError, ValueError, Image.DecompressionBombError):
            return []  # nothing read: every value is "not found", which changes nothing
        width, height = image.size
        if printed.printed_scale and width * height <= self._whole_sheet_px:
            regions.append((0.0, 0.0, 1.0, 1.0))
        found: list[OcrToken] = []
        for region in regions:
            x1, y1 = int(region[0] * width), int(region[1] * height)
            x2, y2 = int(np.ceil(region[2] * width)), int(np.ceil(region[3] * height))
            if x2 - x1 < 2 or y2 - y1 < 2:
                continue
            pixels = np.asarray(image.crop((x1, y1, x2, y2)).convert("RGB"))
            for text, score, (bx1, by1, bx2, by2) in self._read(pixels):
                box = (
                    (x1 + bx1) / width,
                    (y1 + by1) / height,
                    (x1 + bx2) / width,
                    (y1 + by2) / height,
                )
                found.append(OcrToken(text=text, box=_clamped(box), score=score))
        return merged(found)

    def _read(self, pixels: np.ndarray) -> list[tuple[str, float, tuple[float, ...]]]:
        """(text, score, box in `pixels`' px) of every text box read in `pixels`."""
        k = max(1.0, MIN_HEIGHT / pixels.shape[0])
        if k > 1:
            size = (round(pixels.shape[1] * k), round(pixels.shape[0] * k))
            pixels = cv2.resize(pixels, size, interpolation=cv2.INTER_LANCZOS4)
        pixels = ruled_out(pixels)
        h, w = pixels.shape[:2]
        boxes: list[tuple[float, ...]] = []
        parts: list[np.ndarray] = []
        for y in tile_origins(h, TILE):
            for x in tile_origins(w, TILE):
                tile = np.ascontiguousarray(pixels[y : y + TILE, x : x + TILE])
                for quad in self._engine.detect(tile):
                    part = self._engine.cut(tile, quad)
                    if part.size:
                        parts.append(part)
                        boxes.append(_bounds(quad, x, y, k))
        turned = [_turns(part) for part in parts]
        texts = iter(self._engine.recognise([t for ts in turned for t in ts]))
        out: list[tuple[str, float, tuple[float, ...]]] = []
        for box, turns in zip(boxes, turned, strict=True):
            text, score = max((next(texts) for _ in turns), key=lambda r: r[1])
            if text.strip():
                out.append((text.strip(), score, box))
        return out


def tile_origins(length: int, tile: int) -> list[int]:
    """Where tiles of `tile` px start along `length` px, overlapping by at least OVERLAP."""
    if length <= tile:
        return [0]
    step = int(tile * (1 - OVERLAP))
    starts = list(range(0, length - tile, step))
    return [*starts, length - tile]


def ruled_out(pixels: np.ndarray) -> np.ndarray:
    """`pixels` (RGB) with every horizontal or vertical dark run of RULE_PX or more made white."""
    gray = cv2.cvtColor(pixels, cv2.COLOR_RGB2GRAY)
    dark = (gray < 128).astype(np.uint8)
    lines = cv2.bitwise_or(
        cv2.morphologyEx(dark, cv2.MORPH_OPEN, np.ones((1, RULE_PX), np.uint8)),
        cv2.morphologyEx(dark, cv2.MORPH_OPEN, np.ones((RULE_PX, 1), np.uint8)),
    )
    if not lines.any():
        return pixels
    out = pixels.copy()
    out[lines.astype(bool)] = 255
    return out


def joined(boxes: Sequence[Box]) -> list[Box]:
    """`boxes` with every two that overlap read as one, their union: a sheet prints its facts in
    one table (T2: 20 boxes, one column), and one detection over it is cheaper than 20."""
    out = list(boxes)
    while True:
        pair = next(
            ((i, j) for i in range(len(out)) for j in range(i) if _overlap(out[i], out[j]) > 0),
            None,
        )
        if pair is None:
            return out
        a, b = out.pop(pair[0]), out.pop(pair[1])
        out.append((min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])))


def merged(tokens: Sequence[OcrToken]) -> list[OcrToken]:
    """`tokens` with each text read twice in one place (a tile seam, two padded boxes) kept once,
    the better-scored reading."""
    kept: list[OcrToken] = []
    for token in sorted(tokens, key=lambda t: -t.score):
        if not any(k.text == token.text and _overlap(k.box, token.box) >= SAME_BOX for k in kept):
            kept.append(token)
    return sorted(kept, key=lambda t: (t.box[1], t.box[0]))


def _turns(part: np.ndarray) -> list[np.ndarray]:
    h, w = part.shape[:2]
    short = max(h, w) < SHORT * min(h, w)
    turns = (0, 2, 1, 3) if short else (0, 2)
    return [np.ascontiguousarray(np.rot90(part, k)) for k in turns]


def _bounds(quad: Quad, x: int, y: int, k: float) -> tuple[float, ...]:
    xs = [float(p[0]) for p in quad]
    ys = [float(p[1]) for p in quad]
    return ((min(xs) + x) / k, (min(ys) + y) / k, (max(xs) + x) / k, (max(ys) + y) / k)


def _padded(box: Box) -> Box:
    return _clamped((box[0] - PAD, box[1] - PAD, box[2] + PAD, box[3] + PAD))


def _clamped(box: tuple[float, ...]) -> Box:
    x1, y1, x2, y2 = (min(1.0, max(0.0, v)) for v in box)
    return (x1, y1, max(x2, x1), max(y2, y1))


def _overlap(a: Box, b: Box) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    if w <= 0 or h <= 0:
        return 0.0
    smaller = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return w * h / smaller if smaller > 0 else 0.0

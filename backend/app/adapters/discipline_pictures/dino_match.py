"""`dino_match`: a second look at the template reader's sightings with DINOv2-small, to drop
look-alikes on scans and photos (bench bar 1: lights 0.14, sanitary 0.09 precision on scans,
where blur and salt make plain outlines correlate everywhere).

Each sighting's box, and each legend symbol cropped to its ink, is padded by `CONTEXT`, put on a
white square and shrunk to `SIDE` px; DINOv2-small (facebook/dinov2-small, Apache-2.0, the
onnx-community ONNX export, quantized, CPU) turns it into the mean of its patch features. A
sighting stays when its cosine to its own legend symbol (best of the four quarter turns, as the
template reader turns them) is at least `KEEP`, and no other legend symbol is closer by more than
`MARGIN`. Scores are untouched; a dropped sighting is gone, so this only raises precision.

Shortcut: it confirms the template's candidates and does not find new ones. Tiling the whole page
at the symbols' scale (symbols are ~2 patches at 150 dpi, so the page must be enlarged) costs
~75 s per A3 page on CPU; upgrade if recall on scans becomes the problem.

The model file is local only (data/models/dinov2-small/, gitignored), checked by sha256 once.
"""

import hashlib
from collections.abc import Sequence
from functools import cache
from pathlib import Path
from typing import Any, Protocol

import cv2
import numpy as np

from app.adapters.discipline_pictures import pixels
from app.core.errors import InvalidInputError, NotFoundError
from app.core.picture_facts import LegendEntry, PictureReading

READER = "dino"
MODEL = Path(__file__).resolve().parents[4] / "data" / "models" / "dinov2-small"
FILE = "model_quantized.onnx"  # onnx-community/dinov2-small, onnx/model_quantized.onnx
SHA256 = "c179f8f7f592449c4c1bca4cd124a7538021428c5ffb89afde9503935b197efb"
THREADS = 4
SIDE = 112  # px of the square a crop is shrunk to: 8 x 8 patches of 14
CONTEXT = 0.25  # share of the box's long side added around it
KEEP = 0.5  # cosine to its own legend symbol a sighting needs; tune on the bench tune half
MARGIN = 0.0  # how much closer another legend symbol may be before the sighting is dropped
INK = 200  # grey level below which a pixel is drawn (as the template reader)
PAD = 2  # pixels kept around a legend symbol's ink (as the template reader)
BATCH = 64
MEAN, STD = np.float32([0.485, 0.456, 0.406]), np.float32([0.229, 0.224, 0.225])


class Session(Protocol):
    """What we use of `onnxruntime.InferenceSession` (tests pass a fake)."""

    def run(self, output_names: list[str] | None, input_feed: dict[str, Any]) -> Sequence[Any]: ...


@cache
def load(folder: Path = MODEL) -> Session:
    """The checked DINOv2-small session (once per folder)."""
    import onnxruntime

    path = folder / FILE
    if not path.is_file():
        raise NotFoundError(f"{path} is missing: onnx-community/dinov2-small, {FILE}")
    if hashlib.sha256(path.read_bytes()).hexdigest() != SHA256:
        raise InvalidInputError(f"{path} is not the pinned dinov2-small export")
    options = onnxruntime.SessionOptions()
    options.intra_op_num_threads = THREADS
    return onnxruntime.InferenceSession(str(path), options, providers=["CPUExecutionProvider"])


def confirm(
    gray: np.ndarray,
    reading: PictureReading,
    session: Session,
    keep: float = KEEP,
    margin: float = MARGIN,
) -> PictureReading:
    """`reading` (the template reader's, on the grey page `gray`) without the sightings that do
    not look like their legend symbol."""
    own, other = similarities(gray, reading, session)
    kept = tuple(
        s
        for s, o, b in zip(reading.sightings, own, other, strict=True)
        if o >= keep and b <= o + margin
    )
    dropped = len(reading.sightings) - len(kept)
    notes = (f"{READER}: dropped {dropped} of {len(reading.sightings)} sightings",) if dropped else ()
    return reading.model_copy(update={"sightings": kept, "notes": reading.notes + notes})


def similarities(
    gray: np.ndarray, reading: PictureReading, session: Session
) -> tuple[list[float], list[float]]:
    """Per sighting: its cosine to its own legend symbol, and the best cosine to any other
    (-1 when the legend has no other symbol; 1 for its own when its label has no symbol, so an
    unknown label is never dropped)."""
    if not reading.sightings:
        return [], []
    height, width = gray.shape
    symbols = _legend_symbols(gray, reading.legend or ())
    labels = list(symbols)
    turns = [np.ascontiguousarray(np.rot90(symbols[label], q)) for label in labels for q in range(4)]
    crops = [
        gray[y0:y1, x0:x1]
        for x0, y0, x1, y1 in (pixels(s.spot.box, width, height) for s in reading.sightings)
    ]
    vectors = _embed([*turns, *crops], session)
    legend, found = vectors[: len(turns)], vectors[len(turns) :]
    cos = (found @ legend.T).reshape(len(crops), len(labels), 4).max(axis=2)
    own: list[float] = []
    other: list[float] = []
    for i, sighting in enumerate(reading.sightings):
        mine = labels.index(sighting.label) if sighting.label in symbols else None
        rest = [float(c) for j, c in enumerate(cos[i]) if j != mine]
        own.append(1.0 if mine is None else float(cos[i, mine]))
        other.append(max(rest, default=-1.0))
    return own, other


def _legend_symbols(gray: np.ndarray, legend: tuple[LegendEntry, ...]) -> dict[str, np.ndarray]:
    """Each legend symbol cut to its ink, as the template reader cuts it."""
    out: dict[str, np.ndarray] = {}
    for entry in legend:
        if entry.line or entry.box is None:
            continue
        x0, y0, x1, y1 = pixels(entry.box, gray.shape[1], gray.shape[0])
        crop = gray[y0:y1, x0:x1]
        rows, cols = np.nonzero(crop < INK)
        if rows.size:
            top, left = max(0, rows.min() - PAD), max(0, cols.min() - PAD)
            out[entry.label] = crop[top : rows.max() + PAD + 1, left : cols.max() + PAD + 1]
    return out


def _square(crop: np.ndarray) -> np.ndarray:
    """`crop` centred on a white square with `CONTEXT` around it, shrunk to SIDE x SIDE."""
    h, w = crop.shape
    side = max(1, round(max(h, w) * (1 + 2 * CONTEXT)))
    square = np.full((side, side), 255, np.uint8)
    top, left = (side - h) // 2, (side - w) // 2
    square[top : top + h, left : left + w] = crop
    return cv2.resize(square, (SIDE, SIDE), interpolation=cv2.INTER_AREA)


def _embed(crops: list[np.ndarray], session: Session) -> np.ndarray:
    """Unit-length mean patch feature of each crop."""
    out = []
    for start in range(0, len(crops), BATCH):
        grey = np.stack([_square(c) for c in crops[start : start + BATCH]]).astype(np.float32)
        rgb = np.repeat(grey[..., None] / 255.0, 3, axis=3)
        batch = ((rgb - MEAN) / STD).transpose(0, 3, 1, 2).astype(np.float32)
        tokens = np.asarray(session.run(None, {"pixel_values": batch})[0])
        out.append(tokens[:, 1:].mean(axis=1))  # skip the class token
    vectors = np.concatenate(out)
    return vectors / np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-9)

"""`dino_match`: a second look at the template reader's sightings with DINOv2-small, to drop
look-alikes on scans and photos (bench bar 1: lights 0.14, sanitary 0.09 precision on scans,
where blur and salt make plain outlines correlate everywhere).

Each sighting's box, and each legend symbol cropped to its ink, is padded by `CONTEXT`, put on a
white square and shrunk to `SIDE` px; DINOv2-small (facebook/dinov2-small, Apache-2.0, the
onnx-community ONNX export, quantized, CPU) turns it into its 8 x 8 grid of patch features
minus a blank white square's grid ("gridc": the mean patch hides layout and calls radiators
alike, and every crop shares much of the blank's features). A sighting stays when its cosine to
its own legend symbol (best of the four quarter turns, as the template reader turns them) is at
least its kind's keep (`KEEPS`, else `KEEP`), and no other legend symbol is closer by more than
`MARGIN`. Scores are untouched; a dropped sighting is gone, so this only raises precision.

Shortcut: it confirms the template's candidates and does not find new ones. Tiling the whole page
at the symbols' scale (symbols are ~2 patches at 150 dpi, so the page must be enlarged) costs
~75 s per A3 page on CPU; upgrade if recall on scans becomes the problem.

The model file is local only (data/models/dinov2-small/, gitignored), checked by sha256 once.
"""

import hashlib
import re
from collections.abc import Collection, Mapping, Sequence
from functools import cache
from pathlib import Path
from typing import Any, Protocol

import cv2
import numpy as np

from app.adapters.discipline_pictures import pixels
from app.core.errors import InvalidInputError, NotFoundError
from app.core.picture_facts import LegendEntry, PictureReading, kind_of

READER = "dino"
MODEL = Path(__file__).resolve().parents[4] / "data" / "models" / "dinov2-small"
FILE = "model_quantized.onnx"  # onnx-community/dinov2-small, onnx/model_quantized.onnx
SHA256 = "c179f8f7f592449c4c1bca4cd124a7538021428c5ffb89afde9503935b197efb"
THREADS = 4
SIDE = 112  # px of the square a crop is shrunk to: 8 x 8 patches of 14
CONTEXT = 0.25  # share of the box's long side added around it
# Cosine to its own legend symbol a sighting needs, by IFC kind (`kind_of`), else KEEP. From
# w4:p1's gridc sweep on the bench tune half (scans): keep ~0.70-0.75 took sanitary precision
# 0.11 -> 0.60 at recall 0.92 and lights 0.06 -> 0.79 at recall 0.82.
KEEP = 0.70
KEEPS: dict[str, float] = {"light_fixture": 0.75, "sanitary_terminal": 0.70}
# The IFC kinds (`kind_of`) that are confirmed. Tudor's re-measure on the bench tune half:
# confirming hurts clean pages (sanitary clean precision 1.00 -> 0.25) and lights need more
# data; on scans and photos air terminals gain (precision/recall 0.80/0.93 -> 0.91/0.86).
# A label of no kind is not confirmed by itself: on the bench it was mostly a valve or a fixture
# under a Dutch or brand name ('regelklep', 'kraan', 'Grohe_Rapid_SL'; 1,075 of 1,085 valves).
CONFIRM_KINDS: frozenset[str] = frozenset({"air_terminal"})
# ... unless its label or legend heading has air words: then it is an air terminal the kind
# words miss ('toevoer rooster', a symbol under a 'Ventilatie' heading).
AIR_WORDS = re.compile(r"rooster|lucht|ventilat|\bair\b|ilma|luft|grille|diffus", re.I)
MARGIN = 0.0  # how much closer another legend symbol may be before the sighting is dropped
INK = 200  # grey level below which a pixel is drawn (as the template reader)
PAD = 2  # pixels kept around a legend symbol's ink (as the template reader)
BATCH = 64
MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)


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
    keeps: Mapping[str, float] = KEEPS,
    margin: float = MARGIN,
    kinds: Collection[str] | None = CONFIRM_KINDS,
) -> PictureReading:
    """`reading` (the template reader's, on the grey page `gray`) without the sightings of the
    confirmed `kinds` (None: every label), or of no kind but with air words in the label or
    its legend heading, that do not look like their legend symbol; the others
    stay exactly as the template read them. This is the one call the picture lane makes, after
    `template.read_symbols`, and only on scanned or photographed pages: the caller gates the
    page kind (on a clean page the template is already 0.98-0.99 precise, and confirming hurt)."""
    groups = {entry.label: entry.group for entry in reading.legend or ()}

    def kind(label: str) -> str | None:
        found = kind_of(label, groups.get(label))
        return found[0] if found else None

    def needs(label: str) -> float:
        k = kind(label)
        return keep if k is None else keeps.get(k, keep)

    def checks(label: str) -> bool:
        if kinds is None:
            return True
        k = kind(label)
        if k is not None:
            return k in kinds
        return "air_terminal" in kinds and bool(
            AIR_WORDS.search(f"{label} {groups.get(label) or ''}")
        )

    checked = [checks(s.label) for s in reading.sightings]
    if not any(checked):
        return reading
    own, other = similarities(gray, reading, session)
    kept = tuple(
        s
        for s, o, b, c in zip(reading.sightings, own, other, checked, strict=True)
        if not c or (o >= needs(s.label) and b <= o + margin)
    )
    dropped = len(reading.sightings) - len(kept)
    notes = (
        (f"{READER}: dropped {dropped} of {len(reading.sightings)} sightings",) if dropped else ()
    )
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
    turns = [
        np.ascontiguousarray(np.rot90(symbols[label], q)) for label in labels for q in range(4)
    ]
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
    """Unit-length "gridc" of each crop: its patch grid minus a blank square's, flattened."""
    squares = [np.full((SIDE, SIDE), 255, np.uint8)] + [_square(c) for c in crops]
    out = []
    for start in range(0, len(squares), BATCH):
        grey = np.stack(squares[start : start + BATCH]).astype(np.float32)
        rgb = np.repeat(grey[..., None] / 255.0, 3, axis=3)
        batch = ((rgb - MEAN) / STD).transpose(0, 3, 1, 2).astype(np.float32)
        tokens = np.asarray(session.run(None, {"pixel_values": batch})[0])
        out.append(tokens[:, 1:])  # skip the class token
    grids = np.concatenate(out)
    vectors = (grids[1:] - grids[:1]).reshape(len(crops), -1)
    return vectors / np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-9)

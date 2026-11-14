"""TRIAGE_CLASSIFIER=siglip: the sheet register read by fixed heads on a SigLIP2 image embedding.

The model folder (data/models/triage/siglip2-512-v2/, local only like the other models) holds
`vision.onnx` (google/siglip2-base-patch16-512's image tower, Apache-2.0, exported to ONNX),
`heads.npz` (logistic-regression heads as plain arrays) and `manifest.json` (their sha256, the
thresholds and the preprocessing). Both files are checked against the manifest when loaded, once.
Built and measured in prototypes/triage (export.py, export_onnx.py; .agents/exp/triage-models.md).

The heads read the register (decision 0010 section 8): kind (12), has_floor_plan, photo_of_sheet,
scale_shown, quality. has_floor_plan is the local plan head OR the sheet-kind signal's P(a plan,
drawn or photographed) >= the manifest's threshold, when ingest's KindProbe got a reply for the
file (`Probed.p_plan_sheet`): unsure means a plan. The classifier never asks the signal itself, so
it adds no call; a scan, a photo the camera EXIF marked or a file whose kind read failed gets the
local head alone. Vector PDFs, models and CAD never reach a classifier (core's triage takes images
and scans).
Preprocessing is the one the heads were trained on: page 1 of a PDF rendered at 2048 px, an image
decoded (JPEG draft 2048), transparency on white, long side 1024 LANCZOS, JPEG q90 round trip, then
512x512 BICUBIC, scaled to [-1, 1]. It is done in strips, so a call holds one decoded image and no
full-size copy; 16-bit greyscale is scaled to 8 bits (the training set had none). Over Pillow's
pixel limit an image is refused (`Unavailable`: read as today). CPU, onnxruntime.
"""

import hashlib
import io
import json
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np
import pypdfium2
from numpy.typing import NDArray
from PIL import Image

from app.adapters.eight_bit import eight_bit
from app.adapters.pdfium_lock import PDFIUM
from app.core.errors import InvalidInputError, NotFoundError
from app.core.ingest.model import Classified, Probed, Unavailable

MODEL_DIR = Path(__file__).resolve().parents[4] / "data" / "models" / "triage" / "siglip2-512-v2"
THREADS = 4
FIELDS = ("kind", "scale_shown", "quality")
Vector = NDArray[np.float32]
SIDE = 1024  # training's long side (prototypes/triage/shrink.py)
GAP = 2.0  # Pillow thumbnail's reducing_gap: box-reduce by int(size / target / 2) first
STRIP = 256  # rows put on white at a time


class Session(Protocol):
    """What we use of `onnxruntime.InferenceSession` (tests pass a fake)."""

    def run(self, output_names: list[str], input_feed: dict[str, Any]) -> Sequence[Any]: ...


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def _checked(folder: Path, name: str, sha: str) -> Path:
    path = folder / name
    if not path.is_file():
        raise NotFoundError(f"{path} is missing: build it with prototypes/triage (export.py)")
    if _sha256(path) != sha:
        raise InvalidInputError(f"{path} does not match the sha256 in its manifest.json")
    return path


@dataclass(frozen=True)
class Heads:
    """The fixed heads and thresholds of one model folder."""

    arrays: dict[str, NDArray[Any]]
    thresholds: dict[str, float]
    method: str

    def logits(self, name: str, x: Vector) -> NDArray[np.float64]:
        coef, intercept = self.arrays[f"{name}_coef"], self.arrays[f"{name}_intercept"]
        return x.astype(np.float64) @ coef.T.astype(np.float64) + intercept

    def p(self, name: str, x: Vector) -> float:
        """P(yes) of a binary head (plan, photo_of_sheet)."""
        return float(1 / (1 + np.exp(-self.logits(name, x)[0])))

    def label(self, name: str, x: Vector) -> str:
        return str(self.arrays[f"{name}_classes"][int(self.logits(name, x).argmax())])


def _decoded(data: bytes) -> Image.Image:
    """Page 1 of a PDF rendered at 2048 px, or the image opened (a JPEG decodes at <= 2048 px)."""
    if data.startswith(b"%PDF-"):
        with PDFIUM:
            pdf = pypdfium2.PdfDocument(data)
            try:
                page = pdf[0]
                return page.render(scale=2048 / max(page.get_size())).to_pil()
            finally:
                pdf.close()
    image = Image.open(io.BytesIO(data))
    image.draft("RGB", (2048, 2048))
    return image


def _on_white(strip: Image.Image) -> Image.Image:
    """A strip of the decoded image as 8-bit RGB, transparency on white (as training did)."""
    strip = eight_bit(strip)  # 16-bit greyscale: Pillow's convert would clip it to white
    if strip.mode in ("RGBA", "LA", "P"):
        strip = strip.convert("RGBA")
        white = Image.new("RGBA", strip.size, (255, 255, 255, 255))
        strip = Image.alpha_composite(white, strip)
    return strip.convert("RGB")


def _fitted(width: int, height: int) -> tuple[int, int]:
    """The size Pillow's thumbnail((1024, 1024)) gives (its own rounding), training's size."""
    if width <= SIDE and height <= SIDE:
        return width, height
    aspect = width / height

    def rounded(number: float, error: Callable[[int], float]) -> int:
        return max(min(math.floor(number), math.ceil(number), key=error), 1)

    if aspect >= 1:
        return SIDE, rounded(SIDE / aspect, lambda n: 0 if n == 0 else abs(aspect - SIDE / n))
    return rounded(SIDE * aspect, lambda n: abs(aspect - n / SIDE)), SIDE


def page_1024(data: bytes) -> Image.Image:
    """The page as training saw it: on white, RGB, thumbnail((1024, 1024), LANCZOS), JPEG q90
    round trip. Done strip by strip as thumbnail does it (an integer box reduce, then LANCZOS), so
    only the decoded image is held at full size: no full-size RGB, RGBA or premultiplied copy."""
    image = _decoded(data)
    width, height = image.size
    size = _fitted(width, height)
    fx = int(width / size[0] / GAP) or 1
    fy = int(height / size[1] / GAP) or 1
    reduced = Image.new("RGB", (math.ceil(width / fx), math.ceil(height / fy)))
    step = fy * max(1, STRIP // fy)
    for top in range(0, height, step):
        strip = _on_white(image.crop((0, top, width, min(height, top + step))))
        reduced.paste(strip.reduce((fx, fy)) if fx > 1 or fy > 1 else strip, (0, top // fy))
    del image
    if size != (width, height):
        box = (0.0, 0.0, width / fx, height / fy)
        reduced = reduced.resize(size, Image.Resampling.LANCZOS, box=box)
    buffer = io.BytesIO()
    reduced.save(buffer, format="JPEG", quality=90)
    buffer.seek(0)
    return Image.open(buffer).convert("RGB")


class SiglipClassifier:
    def __init__(self, session: Session, heads: Heads, embedding: dict[str, Any]) -> None:
        self._session = session
        self._heads = heads
        self._size = int(embedding["size"])
        self._mean = np.array(embedding["mean"], np.float32)
        self._std = np.array(embedding["std"], np.float32)

    @classmethod
    def from_folder(cls, folder: Path = MODEL_DIR) -> "SiglipClassifier":
        """Loads the model once; NotFoundError if a file is missing, InvalidInputError if one does
        not match its manifest's sha256."""
        manifest_path = folder / "manifest.json"
        if not manifest_path.is_file():
            raise NotFoundError(f"{manifest_path} is missing: build it with prototypes/triage")
        manifest = json.loads(manifest_path.read_text())
        heads_path = _checked(folder, "heads.npz", manifest["heads_sha256"])
        vision = manifest["vision_onnx"]
        onnx_path = _checked(folder, vision["file"], vision["sha256"])
        with np.load(heads_path, allow_pickle=False) as found:
            arrays = {name: found[name] for name in found.files}
        heads = Heads(arrays, manifest["thresholds"], f"{manifest['method']}, CPU")
        import onnxruntime

        options = onnxruntime.SessionOptions()
        options.intra_op_num_threads = THREADS
        options.inter_op_num_threads = 1
        session = onnxruntime.InferenceSession(
            str(onnx_path), options, providers=["CPUExecutionProvider"]
        )
        return cls(session, heads, manifest["embedding"])

    def embed(self, data: bytes) -> Vector:
        """The L2-normalised image embedding the heads read."""
        page = page_1024(data).resize((self._size, self._size), Image.Resampling.BICUBIC)
        pixels = (np.asarray(page, np.float32) / 255 - self._mean) / self._std
        (found,) = self._session.run(
            ["embedding"], {"pixel_values": pixels.transpose(2, 0, 1)[None]}
        )
        return np.asarray(found, np.float32)[0]

    def classify(self, image: bytes, probed: Probed) -> Classified | Unavailable:
        try:
            x = self.embed(image)
        except (OSError, Image.DecompressionBombError, ValueError, pypdfium2.PdfiumError) as error:
            return Unavailable(note=f"the image cannot be decoded: {error}")
        heads, limits = self._heads, self._heads.thresholds
        p_plan = heads.p("plan", x)
        method = heads.method
        has_plan = p_plan >= limits["plan"]
        if probed.p_plan_sheet is not None:
            method += f" OR Gemini kind (P(plan) {probed.p_plan_sheet:.2f})"
            has_plan = has_plan or probed.p_plan_sheet >= limits["gemini_p_plan_sheet"]
            p_plan = max(p_plan, probed.p_plan_sheet)
        register = {name: heads.label(name, x) for name in FIELDS}
        register |= {
            "has_floor_plan": has_plan,
            "photo_of_sheet": heads.p("photo_of_sheet", x) >= limits["photo_of_sheet"],
            "method": method,
        }
        return Classified.model_validate({"p_plan": p_plan, "method": method, "register": register})

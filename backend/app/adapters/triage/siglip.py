"""TRIAGE_CLASSIFIER=siglip: the sheet register read by fixed heads on a SigLIP2 image embedding.

The model folder (data/models/triage/siglip2-512-v2/, local only like the other models) holds
`vision.onnx` (google/siglip2-base-patch16-512's image tower, Apache-2.0, exported to ONNX),
`heads.npz` (logistic-regression heads as plain arrays) and `manifest.json` (their sha256, the
thresholds and the preprocessing). Both files are checked against the manifest when loaded, once.
Built and measured in prototypes/triage (export.py, export_onnx.py; .agents/exp/triage-models.md).

The heads read the register (decision 0010 section 8): kind (12), has_floor_plan, photo_of_sheet,
scale_shown, quality. has_floor_plan is the local plan head OR, when the sheet-kind signal is on,
Gemini's P(a plan, drawn or photographed) >= the manifest's threshold: unsure means a plan.
The signal is read only for a file ingest's KindProbe already asked about (a drawing image it kept,
or one the signal made a photo), so the read is a cache hit and never a new call: a scanned PDF or a
photo the camera EXIF marked gets the local head alone. Vector PDFs, models and CAD never reach a
classifier (core's triage takes images and scans only).
Preprocessing is the one the heads were trained on: page 1 of a PDF rendered at 2048 px, an image
decoded (JPEG draft 2048), transparency on white, long side 1024 LANCZOS, JPEG q90 round trip, then
512x512 BICUBIC, scaled to [-1, 1]. CPU, onnxruntime.
"""

import hashlib
import io
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np
import pypdfium2
from numpy.typing import NDArray
from PIL import Image

from app.adapters.decisions_kind import KindSignal, KindUnavailable
from app.adapters.decisions_kind.probe import ASKED
from app.adapters.pdfium_lock import PDFIUM
from app.core.errors import InvalidInputError, NotFoundError
from app.core.ingest.model import Classified, Probed, Unavailable

MODEL_DIR = Path(__file__).resolve().parents[4] / "data" / "models" / "triage" / "siglip2-512-v2"
THREADS = 4
FIELDS = ("kind", "scale_shown", "quality")
Vector = NDArray[np.float32]
SIGNAL_MADE_PHOTO = "-> photo_plan"  # how KindProbe's trace ends when the signal made a photo


class Session(Protocol):
    """What we use of `onnxruntime.InferenceSession` (tests pass a fake)."""

    def run(self, output_names: list[str], input_feed: dict[str, Any]) -> Sequence[Any]: ...


class KindSignals(Protocol):
    """The sheet-kind signal (app/adapters/decisions_kind): a cached reply costs nothing."""

    def read(self, data: bytes) -> KindSignal | KindUnavailable: ...


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


def page_1024(data: bytes) -> Image.Image:
    """The page as training saw it: long side <= 1024, RGB on white, after a JPEG q90 round trip."""
    if data.startswith(b"%PDF-"):
        with PDFIUM:
            pdf = pypdfium2.PdfDocument(data)
            try:
                page = pdf[0]
                image = page.render(scale=2048 / max(page.get_size())).to_pil()
            finally:
                pdf.close()
    else:
        image = Image.open(io.BytesIO(data))
        image.draft("RGB", (2048, 2048))
    if image.mode in ("RGBA", "LA", "P"):
        image = image.convert("RGBA")
        image = Image.alpha_composite(Image.new("RGBA", image.size, (255, 255, 255, 255)), image)
    image = image.convert("RGB")
    image.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    buffer.seek(0)
    return Image.open(buffer).convert("RGB")


def probe_asked(probed: Probed) -> bool:
    """Whether ingest's KindProbe read the kind signal for this file (its reply is cached)."""
    made_photo = probed.kind == "photo_plan" and probed.did.endswith(SIGNAL_MADE_PHOTO)
    return probed.kind in ASKED or made_photo


class SiglipClassifier:
    def __init__(
        self, session: Session, heads: Heads, embedding: dict[str, Any], kind: KindSignals | None
    ) -> None:
        self._session = session
        self._heads = heads
        self._size = int(embedding["size"])
        self._mean = np.array(embedding["mean"], np.float32)
        self._std = np.array(embedding["std"], np.float32)
        self._kind = kind

    @classmethod
    def from_folder(
        cls, folder: Path = MODEL_DIR, kind: KindSignals | None = None
    ) -> "SiglipClassifier":
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
        return cls(session, heads, manifest["embedding"], kind)

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
        if self._kind is not None and probe_asked(probed):
            signal = self._kind.read(image)
            if isinstance(signal, KindSignal):
                method += f" OR Gemini kind (P(plan) {signal.p_plan_sheet:.2f})"
                has_plan = has_plan or signal.p_plan_sheet >= limits["gemini_p_plan_sheet"]
                p_plan = max(p_plan, min(1.0, signal.p_plan_sheet))
            else:
                method += f" ({signal.note})"
        register = {name: heads.label(name, x) for name in FIELDS}
        register |= {
            "has_floor_plan": has_plan,
            "photo_of_sheet": heads.p("photo_of_sheet", x) >= limits["photo_of_sheet"],
            "method": method,
        }
        return Classified.model_validate({"p_plan": p_plan, "method": method, "register": register})

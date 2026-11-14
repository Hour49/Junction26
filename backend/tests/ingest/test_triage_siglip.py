"""TRIAGE_CLASSIFIER=siglip (app/adapters/triage/siglip.py): the register from fixed heads, the
class derived from it, the OR with the sheet-kind signal, the sha256 checks, and (with the local
model and data) the same embedding as training."""

import hashlib
import io
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import Image

from app.adapters.decisions_kind import KindReader, KindSignal, KindUnavailable
from app.adapters.decisions_kind.probe import KindProbe
from app.adapters.triage.siglip import MODEL_DIR, Heads, SiglipClassifier, page_1024
from app.core.errors import InvalidInputError, NotFoundError
from app.core.ingest.model import Classified, ContentKind, Probed, Unavailable
from app.core.ingest.triage import Triaged, TriageSteps, triaged
from app.core.pipeline.model import FileKind

PROBED = Probed(kind="jpeg_plan", did="test")
EMBEDDING = {"size": 512, "mean": [0.5] * 3, "std": [0.5] * 3}
# Axis 0 of the 4-d fake embedding drives the plan head, axis 1 the kind, axis 2 the photo head.
KINDS = np.array(["elevation", "floor_plan", "not_architecture"])


def heads(plan_bias: float) -> Heads:
    eye = np.eye(4, dtype=np.float32)
    arrays: dict[str, Any] = {
        "plan_coef": eye[[0]] * 10,
        "plan_intercept": np.array([plan_bias], np.float32),
        "plan_classes": np.array([0, 1]),
        "kind_coef": np.stack([eye[3], eye[0], eye[1]]),
        "kind_intercept": np.zeros(3, np.float32),
        "kind_classes": KINDS,
        "photo_of_sheet_coef": eye[[2]] * 10,
        "photo_of_sheet_intercept": np.array([-5.0], np.float32),
        "photo_of_sheet_classes": np.array([0, 1]),
        "scale_shown_coef": np.stack([eye[0], eye[1]]),
        "scale_shown_intercept": np.zeros(2, np.float32),
        "scale_shown_classes": np.array(["bar", "none"]),
        "quality_coef": np.stack([eye[0], eye[1]]),
        "quality_intercept": np.zeros(2, np.float32),
        "quality_classes": np.array(["good", "poor"]),
    }
    limits = {"plan": 0.5, "photo_of_sheet": 0.5, "gemini_p_plan_sheet": 0.2}
    return Heads(arrays, limits, "local heads (test)")


@dataclass
class FakeSession:
    vector: list[float]
    fed: list[np.ndarray] = field(default_factory=list[np.ndarray])

    def run(self, output_names: list[str], input_feed: dict[str, Any]) -> list[Any]:
        assert output_names == ["embedding"]
        self.fed.append(input_feed["pixel_values"])
        return [np.array([self.vector], np.float32)]


@dataclass
class FakeKind:
    found: KindSignal | KindUnavailable
    asked: int = 0

    def read(self, data: bytes) -> KindSignal | KindUnavailable:
        self.asked += 1
        return self.found


def png(mode: str = "RGB", colour: Any = (0, 0, 0)) -> bytes:
    out = io.BytesIO()
    Image.new(mode, (300, 200), colour).save(out, format="PNG")
    return out.getvalue()


def classify(vector: list[float], kind: FakeKind | None = None) -> Classified:
    found = SiglipClassifier(FakeSession(vector), heads(-5.0), EMBEDDING, kind).classify(
        png(), PROBED
    )
    assert isinstance(found, Classified)
    return found


def test_a_plan_head_above_its_threshold_is_a_floor_plan() -> None:
    found = classify([1, 0, 0, 0])
    assert found.class_ == "floor_plan"
    assert found.register_ is not None
    assert found.register_.has_floor_plan
    assert found.p_plan == pytest.approx(1 / (1 + np.exp(-5)))
    assert found.register_.method == found.method == "local heads (test)"


def test_the_class_follows_the_kind_when_the_gate_says_no_plan() -> None:
    not_drawing = classify([0, 1, 0, 0])
    assert not_drawing.class_ == "not_drawing"
    assert not_drawing.register_ is not None
    assert not_drawing.register_.kind == "not_architecture"
    assert not not_drawing.register_.has_floor_plan
    assert classify([0, 0, 0, 1]).class_ == "other_drawing"  # elevation


def test_every_register_field_is_filled() -> None:
    found = classify([0, 1, 1, 0])
    assert found.register_ is not None
    assert found.register_.model_dump() == {
        "kind": "not_architecture",
        "has_floor_plan": False,
        "photo_of_sheet": True,
        "scale_shown": "none",
        "quality": "poor",
        "method": "local heads (test)",
    }


def test_gemini_says_plan_so_a_plan_though_the_local_head_says_no() -> None:
    kind = FakeKind(KindSignal({"floor_plan": 0.15, "photo_plan": 0.1}, "cached"))
    found = classify([0, 1, 0, 0], kind)
    assert kind.asked == 1
    assert found.class_ == "floor_plan"
    assert found.register_ is not None
    assert found.register_.has_floor_plan
    assert found.p_plan == pytest.approx(0.25)
    assert "OR Gemini kind (P(plan) 0.25)" in found.method


def test_gemini_below_its_threshold_leaves_the_local_answer() -> None:
    kind = FakeKind(KindSignal({"floor_plan": 0.1, "not_drawing": 0.9}, "cached"))
    assert classify([0, 1, 0, 0], kind).class_ == "not_drawing"


def test_no_kind_signal_reply_means_the_local_head_alone() -> None:
    kind = FakeKind(KindUnavailable("kind signal not available: timeout"))
    found = classify([0, 1, 0, 0], kind)
    assert found.class_ == "not_drawing"
    assert "kind signal not available: timeout" in found.method


def test_bytes_no_decoder_opens_are_unavailable_not_a_crash() -> None:
    classifier = SiglipClassifier(FakeSession([1, 0, 0, 0]), heads(-5.0), EMBEDDING, None)
    found = classifier.classify(b"not an image", PROBED)
    assert isinstance(found, Unavailable)
    assert "cannot be decoded" in found.note


def test_the_model_sees_512_px_in_minus_one_to_one_and_transparency_on_white() -> None:
    session = FakeSession([1, 0, 0, 0])
    SiglipClassifier(session, heads(-5.0), EMBEDDING, None).classify(
        png("RGBA", (0, 0, 0, 0)), PROBED
    )
    (fed,) = session.fed
    assert fed.shape == (1, 3, 512, 512)
    assert fed.dtype == np.float32
    assert float(fed.min()) == pytest.approx(1.0, abs=0.02)  # all white: 1 after scaling


def test_a_large_page_is_shrunk_to_1024_like_training() -> None:
    out = io.BytesIO()
    Image.new("RGB", (3000, 1500), "white").save(out, format="JPEG")
    assert page_1024(out.getvalue()).size == (1024, 512)


def model_folder(tmp_path: Path, heads_bytes: bytes, onnx_bytes: bytes, **wrong: str) -> Path:
    (tmp_path / "heads.npz").write_bytes(heads_bytes)
    (tmp_path / "vision.onnx").write_bytes(onnx_bytes)
    manifest = {
        "method": "test",
        "heads_sha256": wrong.get("heads", hashlib.sha256(heads_bytes).hexdigest()),
        "vision_onnx": {
            "file": "vision.onnx",
            "sha256": wrong.get("onnx", hashlib.sha256(onnx_bytes).hexdigest()),
        },
        "thresholds": {},
        "embedding": EMBEDDING,
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    return tmp_path


@pytest.mark.parametrize("which", ["heads", "onnx"])
def test_a_file_that_does_not_match_its_manifest_is_refused(tmp_path: Path, which: str) -> None:
    folder = model_folder(tmp_path, b"heads", b"onnx", **{which: "0" * 64})
    with pytest.raises(InvalidInputError, match="sha256"):
        SiglipClassifier.from_folder(folder)


def test_a_missing_model_folder_says_how_to_build_it(tmp_path: Path) -> None:
    with pytest.raises(NotFoundError, match="prototypes/triage"):
        SiglipClassifier.from_folder(tmp_path)


# With the local model and Stoa data: the runtime gives the embeddings the heads were trained on.
REPO = Path(__file__).resolve().parents[3]
TRAINING = REPO / "data" / "stoa" / "exp" / "triage"
LOCAL = (MODEL_DIR / "manifest.json").is_file() and (TRAINING / "cls-manifest.json").is_file()


@pytest.mark.skipif(not LOCAL, reason="data/models/triage and data/stoa are local only")
def test_the_runtime_embedding_is_the_training_embedding() -> None:
    rows = json.loads((TRAINING / "cls-manifest.json").read_text())
    trained = np.load(TRAINING / "emb-gpu" / "siglip2-512.npy")[:, 0].astype(np.float32)
    classifier = SiglipClassifier.from_folder()
    for wanted in ("preview374", "archive", "cubicasa_val"):
        i = next(i for i, row in enumerate(rows) if row["set"] == wanted)
        path = REPO / row_path(rows[i]["path"])
        data = path.read_bytes()
        x = classifier.embed(data)
        assert float(x @ trained[i]) >= 0.999, (wanted, float(x @ trained[i]))
        assert np.array_equal(x, classifier.embed(data))  # same file, same answer
        assert classifier.classify(data, PROBED) == classifier.classify(data, PROBED)


def row_path(path: str) -> str:
    return path[path.index("data/stoa/") :]


# The kind signal end to end: ingest's KindProbe and the classifier share one cached KindReader
# (as composition builds them), so the classifier may only read what the probe already paid for.
@dataclass
class CountingDecider:
    """A Gemini stand-in: every call is counted (a paid call, 0.6-2.9 s in production)."""

    probs: dict[str, float]
    calls: int = 0

    @property
    def model(self) -> str:
        return "fake-gemini"

    def decide(self, body: dict[str, Any]) -> dict[str, Any]:
        self.calls += 1
        return {"answers": {"kind": {"probabilities": self.probs}}}


@dataclass
class InnerProbe:
    kind: ContentKind

    def probe(self, data: bytes) -> Probed:
        return Probed(kind=self.kind, did="the pixels")


def scanned_pdf() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (300, 200), "white").save(out, format="PDF")
    return out.getvalue()


def ingest(
    tmp_path: Path, kind: ContentKind, data: bytes, form: FileKind, probs: dict[str, float]
) -> tuple[Triaged, CountingDecider, FakeSession, Probed]:
    decider = CountingDecider(probs)
    reader = KindReader(decider, tmp_path / "cache")
    session = FakeSession([0, 1, 0, 0])  # the local head alone: not a plan, not_architecture
    classifier = SiglipClassifier(session, heads(-5.0), EMBEDDING, reader)
    probed = KindProbe(InnerProbe(kind), reader).probe(data)
    steps = TriageSteps(classifier=classifier, describer=None, judge=None, name="test")
    return triaged(steps, data, probed, form), decider, session, probed


@pytest.mark.parametrize(
    ("kind", "form"),
    [("pdf_vector", "pdf"), ("ifc", "ifc"), ("dxf", "dxf"), ("svg", "svg")],
)
def test_a_vector_pdf_model_or_cad_file_gets_no_register_and_no_kind_call(
    tmp_path: Path, kind: ContentKind, form: FileKind
) -> None:
    found, decider, session, _ = ingest(
        tmp_path, kind, b"%PDF-1.7 drawn", form, {"floor_plan": 0.9}
    )
    assert found.triage is None
    assert decider.calls == 0
    assert session.fed == []  # the classifier did not run


@pytest.mark.parametrize(
    ("kind", "data", "form"),
    [("pdf_scan", scanned_pdf(), "pdf"), ("photo", png(), "png"), ("photo_plan", png(), "png")],
)
def test_a_scan_or_exif_photo_gets_the_local_register_and_no_kind_call(
    tmp_path: Path, kind: ContentKind, data: bytes, form: FileKind
) -> None:
    found, decider, _, _ = ingest(tmp_path, kind, data, form, {"floor_plan": 0.9})
    assert decider.calls == 0
    assert found.triage is not None
    assert found.triage.register_ is not None
    assert found.triage.class_ == "not_drawing"  # Gemini's 0.9 was never asked
    assert "Gemini" not in found.triage.method


@pytest.mark.parametrize(
    ("probs", "kind_after"),
    [({"floor_plan": 0.3, "not_drawing": 0.1}, "png_plan"), ({"photo_plan": 0.95}, "photo_plan")],
)
def test_a_drawing_image_the_probe_asked_about_reuses_its_reply(
    tmp_path: Path, probs: dict[str, float], kind_after: ContentKind
) -> None:
    found, decider, _, probed = ingest(tmp_path, "png_plan", png(), "png", probs)
    assert decider.calls == 1  # the probe's call; the classifier's read was a cache hit
    assert found.triage is not None
    assert found.triage.class_ == "floor_plan"  # the OR with Gemini's P(plan)
    assert "OR Gemini kind" in found.triage.method
    assert probed.kind == kind_after  # kept a drawing, or made a photo by the signal

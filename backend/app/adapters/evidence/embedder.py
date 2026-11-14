"""The evidence index's sentence embedder (decision 0012): paraphrase-multilingual-MiniLM-L12-v2,
its 8-bit ONNX file on CPU through onnxruntime, its tokenizer through `tokenizers`. Mean pooling
over the attention mask, unit length, 384 float32 numbers; no query or passage prefix. One text
per run: the 8-bit model quantizes its activations over the whole batch, so a batched text's
vector would depend on its neighbours (about 1e-2 apart); one at a time, a vector depends on its
text alone (5.9 ms a passage on dev1 against 4.9 batched by 16).

The model folder is described by `manifest.json` (rag's, under data/models/rag/): the model id,
revision, and each file's name and sha256. No manifest on the machine is the declared no-models
mode (`load_embedder` gives None: BM25 alone). A manifest whose files are missing or do not match
their sha256 is an error, raised when the model is first used. The session loads on first use and
is kept for the life of the process."""

import hashlib
import json
import threading
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

MAX_TOKENS = 512
THREADS = 4


class EmbedderModelError(RuntimeError):
    """The manifest names model files that are missing or not the pinned bytes."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


class OnnxSentenceEmbedder:
    def __init__(self, manifest: Path) -> None:
        found: dict[str, Any] = json.loads(manifest.read_text())
        self._folder = manifest.parent / found["folder"]
        self._files: dict[str, str] = {file["name"]: file["sha256"] for file in found["files"]}
        self._model = next(name for name in self._files if name.endswith(".onnx"))
        self._name = f"{found['model']}@{found['revision'][:12]}/{self._model}"
        self._label = found["model"].rsplit("/", 1)[-1]
        self._lock = threading.Lock()
        self._loaded: tuple[Any, Any, set[str]] | None = None

    @property
    def name(self) -> str:
        """Model, revision and file: a new name re-embeds every passage."""
        return self._name

    @property
    def label(self) -> str:
        return self._label

    def _load(self) -> tuple[Any, Any, set[str]]:
        with self._lock:
            if self._loaded is None:
                import onnxruntime
                from tokenizers import Tokenizer

                for name, expected in self._files.items():
                    path = self._folder / name
                    if not path.is_file():
                        raise EmbedderModelError(f"embedder file {path} is missing")
                    if _sha256(path) != expected:
                        raise EmbedderModelError(f"embedder file {path} is not the pinned one")
                tokenizer = Tokenizer.from_file(str(self._folder / "tokenizer.json"))
                tokenizer.enable_truncation(max_length=MAX_TOKENS)
                options = onnxruntime.SessionOptions()
                options.intra_op_num_threads = THREADS
                session = onnxruntime.InferenceSession(
                    str(self._folder / self._model), options, providers=["CPUExecutionProvider"]
                )
                inputs = {found.name for found in session.get_inputs()}
                self._loaded = (tokenizer, session, inputs)
            return self._loaded

    def embed(self, texts: Sequence[str]) -> NDArray[np.float32]:
        """One unit-length row per text, each text run on its own."""
        tokenizer, session, inputs = self._load()
        rows: list[NDArray[np.float32]] = []
        for text in texts:
            encoded = tokenizer.encode(text)
            ids = np.array([encoded.ids], dtype=np.int64)
            mask = np.array([encoded.attention_mask], dtype=np.int64)
            feed = {"input_ids": ids, "attention_mask": mask}
            if "token_type_ids" in inputs:
                feed["token_type_ids"] = np.zeros_like(ids)
            hidden = np.asarray(session.run(None, feed)[0], np.float32)[0]  # tokens x numbers
            mean = hidden[mask[0] == 1].mean(axis=0)
            rows.append((mean / max(float(np.linalg.norm(mean)), 1e-12)).astype(np.float32))
        return np.stack(rows) if rows else np.zeros((0, 0), np.float32)

    def embed_query(self, text: str) -> NDArray[np.float32]:
        return self.embed([text])[0]


def load_embedder(manifest: Path) -> OnnxSentenceEmbedder | None:
    """The embedder the manifest describes; None when there is no manifest (no-models mode)."""
    return OnnxSentenceEmbedder(manifest) if manifest.is_file() else None

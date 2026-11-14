"""The evidence index's embedder (decision 0012): no manifest is the no-models mode, a manifest
whose files are not the pinned bytes is an error, and the real model (where the machine has it)
gives unit-length 384-number rows that carry a Finnish question to an English description."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from app.adapters.evidence.embedder import EmbedderModelError, load_embedder

MANIFEST = Path(__file__).resolve().parents[2] / "data" / "models" / "rag" / "manifest.json"


def manifest(tmp_path: Path, files: dict[str, bytes], pinned: dict[str, bytes]) -> Path:
    folder = tmp_path / "model"
    folder.mkdir(parents=True)
    for name, data in files.items():
        (folder / name).write_bytes(data)
    found = {
        "model": "test/model",
        "revision": "0123456789abcdef",
        "folder": "model",
        "files": [
            {"name": name, "sha256": hashlib.sha256(data).hexdigest()}
            for name, data in pinned.items()
        ],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(found))
    return path


def test_no_manifest_is_the_no_models_mode(tmp_path: Path) -> None:
    assert load_embedder(tmp_path / "manifest.json") is None


def test_the_name_carries_model_revision_and_file_and_nothing_loads_for_it(
    tmp_path: Path,
) -> None:
    pinned = {"model.onnx": b"weights", "tokenizer.json": b"{}"}
    embedder = load_embedder(manifest(tmp_path, {}, pinned))  # files missing: still no error
    assert embedder is not None
    assert embedder.name == "test/model@0123456789ab/model.onnx"
    assert embedder.label == "model"


def test_files_missing_or_not_the_pinned_bytes_are_an_error_when_first_used(
    tmp_path: Path,
) -> None:
    pinned = {"model.onnx": b"weights", "tokenizer.json": b"{}"}
    missing = load_embedder(manifest(tmp_path / "a", {"model.onnx": b"weights"}, pinned))
    assert missing is not None
    with pytest.raises(EmbedderModelError, match="missing"):
        missing.embed(["a wall"])
    changed = {"model.onnx": b"other weights", "tokenizer.json": b"{}"}
    swapped = load_embedder(manifest(tmp_path / "b", changed, pinned))
    assert swapped is not None
    with pytest.raises(EmbedderModelError, match="not the pinned one"):
        swapped.embed_query("a wall")


@pytest.mark.skipif(not MANIFEST.is_file(), reason="data/models/rag/ is local only")
def test_the_real_model_gives_unit_rows_and_reads_finnish_against_english() -> None:
    embedder = load_embedder(MANIFEST)
    assert embedder is not None
    passages = [
        "photograph. south facade of a two-storey wooden house. The front of the house.",
        "sheet music. a music score. Notes for a piano piece.",
    ]
    rows = embedder.embed(passages)
    assert rows.shape == (2, 384) and rows.dtype == np.float32
    assert np.allclose(np.linalg.norm(rows, axis=1), 1.0, atol=1e-5)
    query = embedder.embed_query(
        "kaksikerroksisen puutalon julkisivu"
    )  # a two-storey house's facade
    scores = rows @ query
    assert scores[0] > scores[1]
    assert np.allclose(embedder.embed(passages[:1])[0], rows[0], atol=1e-6)  # alone or not

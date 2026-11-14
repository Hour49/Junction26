"""`ab_backend.py` run for real in backend/'s environment (the other tests replace it). Skipped
where backend/ has no environment yet (`cd backend && uv sync --locked`), as in eval's CI job."""

import hashlib
import json
from pathlib import Path

import pytest

from stoa_eval import backend

pytestmark = pytest.mark.skipif(
    not (backend.BACKEND / ".venv").is_dir(), reason="backend/ has no environment"
)

# the backend's G1main question keys and cache name parts (app/adapters/decisions/g1main.py,
# client.py): a change there changes the cache key, and this test should fail with it
KEYS = {
    "door": "door", "window": "window", "sink": "sink", "toilet": "toilet",
    "shower+bathtub": "shower_bathtub", "sauna": "sauna", "plan": "plan",
    "room:kitchen": "kitchen", "room:bedroom": "bedroom", "room:bathroom": "bathroom",
    "room:wc": "wc", "room:balcony": "balcony",
}  # fmt: skip
QUESTION_SET = "adb8fe505686"
MODEL = "gemini-decision-1-high"


def test_g1main_reads_the_backends_own_cache_by_the_drawings_bytes(tmp_path: Path) -> None:
    dataset = tmp_path / "junction-dataset"
    (dataset / "data" / "cubicasa5k").mkdir(parents=True)
    cached, missing = b"\x89PNG\r\n\x1a\ncached page", b"\x89PNG\r\n\x1a\nnot cached"
    (dataset / "data/cubicasa5k/a.png").write_bytes(cached)
    (dataset / "data/cubicasa5k/b.png").write_bytes(missing)
    questions = tmp_path / "test_questions.jsonl"
    rows = [
        {"path": "data/cubicasa5k/a.png", "question": "How many doors?", "id": 1},
        {"path": "data/cubicasa5k/b.png", "question": "How many doors?", "id": 2},
    ]
    questions.write_text("".join(json.dumps(row) + "\n" for row in rows))
    cache = tmp_path / "decisions-cache"
    cache.mkdir()
    reply = {
        "answers": {
            f"g1_{key}": {"type": "choice", "probabilities": {"0": 0.25, "1": 0.75}}
            for key in KEYS.values()
        }
    }
    name = f"{hashlib.sha256(cached).hexdigest()}-{QUESTION_SET}-{MODEL}.json"
    (cache / name).write_text(json.dumps(reply))
    out = tmp_path / "g1.json"

    backend.run(
        "g1main", "--replies", str(cache), "--questions", str(questions),
        "--dataset", str(dataset), "--out", str(out),
    )  # fmt: skip

    # b.png is not in the cache: no distribution, and no API call (none is possible here)
    assert json.loads(out.read_text()) == {
        "data/cubicasa5k/a.png": {family: {"0": 0.25, "1": 0.75} for family in KEYS}
    }

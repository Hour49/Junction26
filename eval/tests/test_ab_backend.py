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


def test_answer_with_a_policy_takes_only_the_policys_families_from_the_prior(
    tmp_path: Path,
) -> None:
    """`answer --prior T --policy P`: the backend's own ANSWER_POLICY loader reads P; a family P
    sends to the prior is answered from T although the drawing gives a value, and T answers
    nothing else (a refused question stays null), so the arm differs by the policy alone."""
    drawings = tmp_path / "drawings"
    drawings.mkdir()
    doors = [
        {"id": f"e{i}", "class": "door", "page": 1, "plan": "p1", "box": [0.1, 0.1, 0.2, 0.2]}
        for i in (1, 2)
    ]
    room = {"id": "r1", "type": "living", "page": 1, "plan": "p1", "box": [0.1, 0.1, 0.9, 0.9]}
    read = {
        "schema": "extraction_v1", "file": "data/cubicasa5k/a.png", "split": "dev",
        "truth": "elements", "pages": [{"page": 1, "width": 100, "height": 100, "unit": "px"}],
        "scale": {"status": "no_scale"}, "plans": [{"id": "p1", "page": 1, "box": [0, 0, 1, 1]}],
        "elements": doors, "rooms": [room], "read": ["door", "room"],
    }  # fmt: skip
    (drawings / "a.json").write_text(json.dumps(read))
    kitchens = (
        "How many kitchens (including kitchenettes, open kitchens and utility kitchens) are on "
        "this floor plan?"
    )
    doors_asked = "How many doors are shown on this floor plan?"
    rows = [
        {"path": "data/cubicasa5k/a.png", "question": kitchens, "id": 1},
        {"path": "data/cubicasa5k/a.png", "question": doors_asked, "id": 2},
        {"path": "data/cubicasa5k/b.png", "question": doors_asked, "id": 3},
    ]
    questions = tmp_path / "val_questions.jsonl"
    questions.write_text("".join(json.dumps(row) + "\n" for row in rows))
    prior = tmp_path / "prior.json"
    counted = {"unit": "count", "confidence": 0.9, "n": 100}
    table = {
        "room:kitchen": {"value": 1, **counted}, "door": {"value": 7, **counted}
    }  # fmt: skip
    prior.write_text(json.dumps({"schema": "answer_prior_v1", "priors": {"cubicasa5k": table}}))
    policy = tmp_path / "policy.json"
    families = {"room:kitchen": {"source": "prior"}, "door": {"source": "reader"}}
    policy.write_text(
        json.dumps({"schema": "answer_policy_v1", "part": "val", "families": families})
    )

    def answers(*extra: str) -> dict[int, tuple[object, str]]:
        out = tmp_path / f"answers{len(extra)}.jsonl"
        backend.run(
            "answer", "--questions", str(questions), "--drawings", str(drawings),
            "--out", str(out), *extra,
        )  # fmt: skip
        found = [json.loads(line) for line in out.read_text().splitlines()]
        return {row["id"]: (row["answer"], row["method"]) for row in found}

    assert answers("--prior", str(prior), "--policy", str(policy)) == {
        1: (1, "prior:policy"),  # the drawing reads no kitchen; the policy answers the prior's 1
        2: (2, "takeoff"),
        3: (None, "refused:no-drawing"),  # door is not the policy's: no prior value
    }
    assert answers("--prior", str(prior)) == {
        1: (0, "takeoff"),
        2: (2, "takeoff"),
        3: (7, "refused:no-drawing"),
    }

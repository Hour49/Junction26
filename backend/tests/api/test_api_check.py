"""CHECK_POLICY with LOCAL_GATES through the API: a family whose threshold is on a local gate's
signal is certified on that gate's score of the answer (app/core/review/check.py)."""

import json
from pathlib import Path

import pytest
from conftest import plan_png, raster_arm, upload
from fastapi.testclient import TestClient

from app.composition import build_ingest
from app.main import create_app
from app.settings import Settings

SHA = "9c762d68a698dd45a6c1ca4fa7fae39f19199aae470d1b195ed82a873d8c48e9"


def gate(folder: Path) -> Path:
    """lgate-rt-noL1 on doors, scoring sigmoid(the answered count - 1): 0.73 for two doors."""
    n = 3  # the answered count, its prior, the door one-hot
    doc = {
        "schema": "local_gate_v1", "name": "lgate-rt-noL1", "families": ["door"], "readers": [],
        "blocks": [], "prior": {"door": {"2": 0.5}},
        "mu": [0.0] * n, "sd": [1.0] * n, "coef": [1.0, 0.0, 0.0], "intercept": -1.0,
    }  # fmt: skip
    path = folder / "lgate-rt-noL1.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def policy(folder: Path, threshold: float) -> Path:
    doc = {
        "schema": "check_policy_v1", "part": "val", "split_sha256": SHA,
        "families": {"door": {"signal": "lgate-rt-nol1", "threshold": threshold}}, "routes": {},
    }  # fmt: skip
    path = folder / f"check-{threshold}.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


@pytest.mark.parametrize(("threshold", "asks"), [(0.7, False), (0.75, True)])
def test_a_door_count_is_certified_on_its_local_gate_s_score(
    settings: Settings, threshold: float, asks: bool
) -> None:
    root = settings.projects_dir.parent
    raster_arm(root / "arm", "plan.png")
    settings = settings.model_copy(
        update={
            "extractor_raster": "composite",
            "raster_components": "elements=dir:arm,plans=dir:arm,rooms=dir:arm",
            "check_policy": str(policy(root, threshold)),
            "local_gates": str(gate(root)),
        }
    )
    client = TestClient(
        create_app(settings, build_ingest(settings, settings.projects_dir, background=False))
    )
    project = client.get(f"/api/projects/{upload(client, plan_png(), 'plan.png')}").json()
    ask = {"drawing_id": project["drawings"][0]["drawing_id"], "question": "How many doors?"}
    answer = client.post("/api/ask", json=ask).json()
    assert answer["answer"] == 2
    assert (answer["check"] is not None) == asks

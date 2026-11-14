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


LEVELS = {
    "cut": 0.2,
    "crossfit": {
        "high": {"units": 1517, "exact": 1501},
        "medium": {"units": 1185, "exact": 1084},
        "low": {"units": 680, "exact": 397},
    },
}


def policy(folder: Path, threshold: float, medium: float | None = None) -> Path:
    """`medium`: the door's Medium score, in a file with levels; None: a file without them."""
    door = {"signal": "lgate-rt-nol1", "threshold": threshold}
    doc = {
        "schema": "check_policy_v1", "part": "val", "split_sha256": SHA,
        "families": {"door": door}, "routes": {},
    }  # fmt: skip
    if medium is not None:
        door["medium"] = medium
        doc["levels"] = LEVELS
    path = folder / f"check-{threshold}-{medium}.json"
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


def doors_asked(settings: Settings, check: Path) -> tuple[dict, dict]:
    """ "How many doors?" on the arm's plan (the gate scores its two doors 0.73) under the policy
    file `check`: POST /api/ask's answer, and the project ask's."""
    root = settings.projects_dir.parent
    raster_arm(root / "arm", "plan.png")
    settings = settings.model_copy(
        update={
            "extractor_raster": "composite",
            "raster_components": "elements=dir:arm,plans=dir:arm,rooms=dir:arm",
            "check_policy": str(check),
            "local_gates": str(gate(root)),
        }
    )
    client = TestClient(
        create_app(settings, build_ingest(settings, settings.projects_dir, background=False))
    )
    project_id = upload(client, plan_png(), "plan.png")
    project = client.get(f"/api/projects/{project_id}").json()
    ask = {"drawing_id": project["drawings"][0]["drawing_id"], "question": "How many doors?"}
    answer = client.post("/api/ask", json=ask).json()
    total = client.post(f"/api/projects/{project_id}/ask", json={"question": "How many doors?"})
    return answer, total.json()


@pytest.mark.parametrize(
    ("threshold", "medium", "level", "basis"),
    [(0.7, 0.5, "high", "certified"), (0.75, 0.7, "medium", "score"), (0.9, 0.8, "low", "score")],
)
def test_the_answer_carries_its_level_and_the_project_s_total_the_lowest(
    settings: Settings, threshold: float, medium: float, level: str, basis: str
) -> None:
    """Decision 0011: High exactly when nothing is asked."""
    root = settings.projects_dir.parent
    answer, total = doors_asked(settings, policy(root, threshold, medium))
    assert (answer["level"]["level"], answer["level"]["basis"]) == (level, basis)
    assert (answer["level"]["level"] == "high") == (answer["check"] is None)
    assert answer["level"]["text"].startswith(f"{level.capitalize()} confidence: on our validation")
    assert "level" not in answer["line"]  # answer_v1.1, the scorer's line, is untouched
    assert (total["total"], total["total_level"]) == (2, level)


def test_a_policy_file_without_levels_gives_the_answer_no_level(settings: Settings) -> None:
    answer, total = doors_asked(settings, policy(settings.projects_dir.parent, 0.75))
    assert answer["check"] is not None and answer["level"] is None
    assert total["total_level"] is None

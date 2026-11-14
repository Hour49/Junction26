"""A Swiss floor uploaded as a lone image, through the API (think-acc's certified-wrong bathroom,
.agents/exp/certified-bathroom.md): its rooms take their printed Swiss names' types on the raster
route, and a room count on it is not certified, whatever its score."""

import json
from pathlib import Path

from conftest import plan_png, upload
from fastapi.testclient import TestClient
from test_api_check import LEVELS, SHA

from app.composition import build_ingest
from app.main import create_app
from app.settings import Settings


def swiss_arm(folder: Path, name: str) -> None:
    """site980's two bathrooms as the image route read them: "Bagno 1.09" typed `other`."""
    folder.mkdir(parents=True, exist_ok=True)
    rooms = [
        ("bathroom", "Bagno\n1.01", [0.1, 0.1, 0.3, 0.4]),
        ("other", "Bagno\n1.09", [0.6, 0.1, 0.8, 0.4]),
        ("bedroom", "Stanza\n1.02", [0.1, 0.5, 0.4, 0.9]),
    ]
    drawing = {
        "schema": "extraction_v1", "file": name, "split": "dev", "truth": "elements",
        "pages": [{"page": 1, "width": 800, "height": 400, "unit": "px"}],
        "scale": {"status": "no_scale"},
        "plans": [{"id": "p1", "page": 1, "box": [0.0, 0.0, 1.0, 1.0]}],
        "elements": [],
        "rooms": [{"id": f"r{at}", "type": kind, "label": label, "page": 1, "plan": "p1",
                   "box": box} for at, (kind, label, box) in enumerate(rooms, start=1)],
    }  # fmt: skip
    (folder / f"{Path(name).stem}.json").write_text(json.dumps(drawing), encoding="utf-8")


def files(folder: Path) -> tuple[Path, Path]:
    """A local gate scoring sigmoid(the bathroom count - 1) (one bathroom 0.5, two 0.73) and a
    policy certifying bathrooms from 0.45 on it, Medium from 0.3: both counts would be High."""
    gate = {
        "schema": "local_gate_v1", "name": "lgate-rt-noL1", "families": ["room:bathroom"],
        "readers": [], "blocks": [], "prior": {"room:bathroom": {"2": 0.5}},
        "mu": [0.0] * 3, "sd": [1.0] * 3, "coef": [1.0, 0.0, 0.0], "intercept": -1.0,
    }  # fmt: skip
    family = {"signal": "lgate-rt-nol1", "threshold": 0.45, "medium": 0.3}
    policy = {
        "schema": "check_policy_v1", "part": "val", "split_sha256": SHA,
        "families": {"room:bathroom": family}, "routes": {}, "levels": LEVELS,
    }  # fmt: skip
    (folder / "gate.json").write_text(json.dumps(gate), encoding="utf-8")
    (folder / "policy.json").write_text(json.dumps(policy), encoding="utf-8")
    return folder / "gate.json", folder / "policy.json"


def test_a_lone_swiss_image_counts_its_labelled_bathrooms_and_is_not_certified(
    settings: Settings,
) -> None:
    root = settings.projects_dir.parent
    swiss_arm(root / "arm", "plan.png")
    gate, policy = files(root)
    settings = settings.model_copy(
        update={
            "extractor_raster": "composite",
            "raster_components": "elements=dir:arm,plans=dir:arm,rooms=dir:arm",
            "check_policy": str(policy),
            "local_gates": str(gate),
        }
    )
    client = TestClient(
        create_app(settings, build_ingest(settings, settings.projects_dir, background=False))
    )
    project = client.get(f"/api/projects/{upload(client, plan_png(), 'plan.png')}").json()
    ask = {"drawing_id": project["drawings"][0]["drawing_id"], "question": "How many bathrooms?"}
    answer = client.post("/api/ask", json=ask).json()
    assert answer["answer"] == 2  # was 1: "Bagno 1.09" typed other
    assert (answer["level"]["level"], answer["level"]["basis"]) == ("medium", "score")  # was High
    assert answer["line"]["sure"] is False
    assert "not in our validation" in answer["check"]["reason"]

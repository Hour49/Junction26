"""Two wrong answers of the fresh judge set, through the API (.agents/exp/judge-fresh-fixes.md):
a sheet whose rooms are labelled only "Rum" answered "10 bedrooms", and a sheet with two plans and
elevations answered "6 floor plans"."""

import json
from pathlib import Path

from conftest import plan_png, upload
from fastapi.testclient import TestClient

from app.composition import build_ingest
from app.main import create_app
from app.settings import Settings

UPPER, GROUND = [0.10, 0.50, 0.75, 0.68], [0.20, 0.72, 0.80, 0.88]
FACADE, SIDE = [0.09, 0.08, 0.57, 0.25], [0.67, 0.09, 0.92, 0.25]


def arm(folder: Path, name: str, rooms: list[tuple[str, str, list[float]]]) -> None:
    """A sheet as the image route read it: two plans, two elevations boxed as plans, `rooms`."""
    folder.mkdir(parents=True, exist_ok=True)
    drawing = {
        "schema": "extraction_v1", "file": name, "split": "dev", "truth": "elements",
        "pages": [{"page": 1, "width": 800, "height": 400, "unit": "px"}],
        "scale": {"status": "no_scale"},
        "plans": [{"id": f"p{at}", "page": 1, "box": box}
                  for at, box in enumerate([FACADE, UPPER, GROUND, SIDE], start=1)],
        "elements": [],
        "rooms": [{"id": f"r{at}", "type": kind, "label": label, "page": 1, "plan": "p1",
                   "box": box} for at, (kind, label, box) in enumerate(rooms, start=1)],
    }  # fmt: skip
    (folder / f"{Path(name).stem}.json").write_text(json.dumps(drawing), encoding="utf-8")


def asked(settings: Settings, rooms: list[tuple[str, str, list[float]]], question: str) -> dict:
    root = settings.projects_dir.parent
    arm(root / "arm", "plan.png", rooms)
    settings = settings.model_copy(
        update={
            "extractor_raster": "composite",
            "raster_components": "elements=dir:arm,plans=dir:arm,rooms=dir:arm",
        }
    )
    client = TestClient(
        create_app(settings, build_ingest(settings, settings.projects_dir, background=False))
    )
    project = client.get(f"/api/projects/{upload(client, plan_png(), 'plan.png')}").json()
    ask = {"drawing_id": project["drawings"][0]["drawing_id"], "question": question}
    return client.post("/api/ask", json=ask).json()


RUM = [
    ("bedroom", "Rum", [0.27, 0.52, 0.37, 0.66]),
    ("bedroom", "Rum", [0.40, 0.52, 0.50, 0.66]),
    ("kitchen", "Kök", [0.27, 0.74, 0.37, 0.86]),
]


def test_rooms_labelled_only_room_are_not_bedrooms_and_the_count_is_refused(
    settings: Settings,
) -> None:
    answer = asked(settings, RUM, "How many bedrooms are there?")
    assert answer["answer"] is None  # was 2
    assert answer["refusal"]["code"] == "not-in-drawing"
    assert answer["refusal"]["text"] == (
        'This drawing doesn\'t say which rooms are bedrooms: 2 rooms are labelled only "Rum", '
        "a word for any room."
    )


def test_a_labelled_bedroom_is_counted_beside_rooms_labelled_only_room(settings: Settings) -> None:
    rooms = [*RUM, ("bedroom", "Sovrum", [0.45, 0.74, 0.55, 0.86])]
    answer = asked(settings, rooms, "How many bedrooms are there?")
    assert (answer["answer"], answer["refusal"]) == (1, None)


def test_elevations_boxed_beside_the_plans_are_not_floor_plans(settings: Settings) -> None:
    answer = asked(settings, RUM, "How many floor plans are on this sheet?")
    assert (answer["answer"], answer["refusal"]) == (2, None)  # was 4

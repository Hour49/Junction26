"""scripts/scale_bench.py: every candidate's signed error against a gold or a hand reference, on
synthetic sheets whose numbers are worked out by hand."""

import importlib.util
import math
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from app.core.pipeline.raster_scale import BOX_RATIO


def script() -> ModuleType:
    path = Path(__file__).parents[1] / "scripts" / "scale_bench.py"
    spec = importlib.util.spec_from_file_location("scale_bench", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def door(width: float, score: float = 0.9) -> dict[str, Any]:
    return {
        "id": "e",
        "class": "door",
        "page": 1,
        "box": [0, 0, width, 0.02],
        "attrs": {"score": score},
    }


def room(area: float | None, source: str, polygon: Any = None) -> dict[str, Any]:
    box = [0, 0, 0.4, 0.8]
    return {
        "id": "r",
        "type": "room",
        "page": 1,
        "box": box,
        "polygon": polygon,
        "area_m2": area,
        "area_source": source,
    }


# 1000 x 500 px; doors 80, 100, 120 px long (a 0.3-score door is not counted): median 100 px.
SCAN = {
    "file": "data/scans/a.jpg",
    "pages": [{"page": 1, "width": 1000, "height": 500, "unit": "px"}],
    "scale": {
        "status": "estimated",
        "m_per_unit": 0.01,
        "text": "1:100",
        "uncertainty": 0.1,
        "source": "printed scale 1:100 at the image's 200 dpi",
    },
    "elements": [door(0.08), door(0.1), door(0.12), door(0.5, score=0.3)],
    "rooms": [
        room(16, "printed", [[0, 0], [0.4, 0], [0.4, 0.8], [0, 0.8]]),  # 160,000 px²: 0.01 m/px
        room(16, "printed"),  # the box, 160,000 px² over BOX_RATIO
        room(99, "geometry_x_scale"),  # not printed: not a candidate
    ],
}
GOLD = {"file": "data/scans/a.jpg", "pages": [{"width": 2000}], "scale": {"m_per_unit": 0.004}}
# 400 px wide, scaled with no band (so scale_scoring's 2%), a ratio only in a note.
PHOTO = {
    "file": "r4/photos/b.jpg",
    "pages": [{"page": 1, "width": 400, "height": 300, "unit": "px"}],
    "scale": {"status": "scaled", "m_per_unit": 0.02, "source": "printed scale bar (one bar)"},
    "notes": ["carbon: printed scale 1:50: read, not used by Carbon"],
}
REFS = {"b.jpg": {"m_per_unit": 0.0198, "dpi": 100, "how": "hand"}}
NO_REFERENCE = {**PHOTO, "file": "c.png"}


def test_every_candidate_against_gold_and_hand_reference() -> None:
    bench = script()
    run = {sheet["file"]: sheet for sheet in (SCAN, PHOTO, NO_REFERENCE)}
    scan, photo = bench.rows(run, {GOLD["file"]: GOLD}, REFS)  # c.png has no reference

    truth = 0.004 * 2000  # metres across the gold's page 1
    label = 0.01 * (1 + math.sqrt(BOX_RATIO)) / 2  # median of the polygon and the box room
    expected = {
        "final": 10 / truth - 1,  # +25%
        "door": 0.794 / 100 * 1000 / truth - 1,
        "carbon_door": 1.069 / 100 * 1000 / truth - 1,
        "ratio": 100 * 0.0254 / 200 * 1000 / truth - 1,  # 1:100 at the stated 200 dpi
        "label_area": label * 1000 / truth - 1,
    }
    assert scan["kind"] == "synthetic scan" and scan["band"] == 0.1 and not scan["inside"]
    assert scan["errors"] == pytest.approx(expected, rel=1e-12)

    assert photo["kind"] == "photo" and photo["band"] == 0.02 and photo["inside"]
    assert photo["errors"]["final"] == pytest.approx(0.02 / 0.0198 - 1, rel=1e-12)
    assert photo["errors"]["ratio"] == pytest.approx(50 * 0.0254 / 100 / 0.0198 - 1, rel=1e-12)
    assert photo["errors"]["door"] is None and photo["errors"]["label_area"] is None

    lines = bench.summary([scan, photo])
    assert lines[0].startswith("photo: 1 sheets; inside the band 1/1")
    assert lines[1].startswith(
        "synthetic scan: 1 sheets; inside the band 0/1 (0%); median |error| final=25.0%"
    )
    assert lines[2] == "worst 5 (final): data/scans/a.jpg +25.0%; r4/photos/b.jpg +1.0%"

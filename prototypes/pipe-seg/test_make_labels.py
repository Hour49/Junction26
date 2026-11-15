"""make_labels.moved puts a label pixel where the renderer's own _scan / _photo put that point.

cd backend && uv run pytest -q ../prototypes/pipe-seg/test_make_labels.py
"""

import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from app.adapters.ifc_model.plan_picture import _photo, _scan
from make_labels import clean_label, moved


def _truth(x: float, y: float) -> dict:
    return {"symbols": [{"x": x, "y": y}], "legend": [], "legend_lines": []}


@pytest.mark.parametrize("variant", ["scan", "photo"])
@pytest.mark.parametrize("seed", [1, 7, 11])
def test_a_label_pixel_lands_on_the_moved_point(variant: str, seed: int) -> None:
    w, h, x, y = 900, 700, 610, 233
    image = Image.new("RGB", (w, h), "white")
    label = np.zeros((h, w), np.uint8)
    label[y, x] = 3
    rng = np.random.default_rng(seed)
    if variant == "scan":
        out, truth = _scan(image, _truth(x + 0.5, y + 0.5), rng)
    else:
        out, truth = _photo(image, _truth(x + 0.5, y + 0.5), rng)
    truth["variant"] = variant
    got = np.array(moved(Image.fromarray(label), truth))
    assert got.shape == np.array(out).shape[:2]
    ys, xs = np.nonzero(got == 3)
    assert len(xs) >= 1
    sx, sy = truth["symbols"][0]["x"], truth["symbols"][0]["y"]
    assert abs(xs.mean() + 0.5 - sx) <= 1.0 and abs(ys.mean() + 0.5 - sy) <= 1.0


def test_clean_label_reads_the_palette_and_nothing_else() -> None:
    rgb = np.full((2, 4, 3), 255, np.uint8)
    rgb[0, 0] = (0xD6, 0x27, 0x28)  # COLOURS[0] -> 1
    rgb[0, 1] = (0x7F, 0x7F, 0x7F)  # other grey -> 9
    rgb[0, 2] = (0, 0, 0)  # text
    rgb[0, 3] = (0xD9, 0xD9, 0xD9)  # wall fill
    assert clean_label(rgb).tolist() == [[1, 9, 0, 0], [0, 0, 0, 0]]

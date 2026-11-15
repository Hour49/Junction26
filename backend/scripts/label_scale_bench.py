"""LABEL_SCALE measure: on scans with a known scale, the label scale (core/pipeline/label_scale.py)
from the Carbon reader's rooms and their printed areas, the Carbon door estimate the sheet has
today (SCALE_CARBON_DOORS, raster_scale.carbon_door_scale), and the final scale with LABEL_SCALE
off, on and always (`with_label_scale` over that estimate), each as a SIGNED relative error
against the reference (estimate / reference - 1) and whether the reference is inside its band.

    cd backend && PYTHONPATH=. uv run python scripts/label_scale_bench.py \
        --scans ../data/stoa/runs/<scans> [--scans ...] --cache <carbon-reader cache dir>

Each --scans folder is scripts/make_scans.py's output: dataset/data/scans/<stem>.jpg and
gold/<stem>.json (metres across the image's width). Cached Carbon replies only: a page without one
is skipped (nothing is paid for). Partner-derived data: the output names files, keep it in .agents/.
"""

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Any

from PIL import Image

from app.adapters.carbon.reader import CarbonReader
from app.adapters.raster_ocr.gemini import GeminiError
from app.core.drawing.model import Page, Scale
from app.core.pipeline.label_scale import label_scale, with_label_scale
from app.core.pipeline.model import Extracted
from app.core.pipeline.raster_scale import carbon_door_scale, door_sides


class CacheOnly:
    """A Carbon model that is never asked: every reply must come from the cache."""

    def generate(self, jpeg: bytes, prompt: str, schema: dict[str, Any], max_tokens: int) -> dict:
        raise GeminiError("cache only")


def error(scale: Scale | None, reference: float) -> tuple[float, bool] | None:
    """(signed relative error, reference inside the band); None without a value."""
    if scale is None or scale.m_per_unit is None:
        return None
    signed = scale.m_per_unit / reference - 1
    return signed, abs(math.log1p(signed)) <= math.log1p(scale.uncertainty or 0.0)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scans", type=Path, action="append", required=True)
    parser.add_argument("--cache", type=Path, required=True)
    args = parser.parse_args()
    reader = CarbonReader(CacheOnly(), args.cache)
    rows: list[dict[str, Any]] = []
    for folder in args.scans:
        for gold_path in sorted((folder / "gold").glob("*.json")):
            gold = json.loads(gold_path.read_text())
            image = Image.open(folder / "dataset" / gold["file"])
            page = Page(page=1, width=image.width, height=image.height, unit="px")
            reference = gold["scale"]["m_per_unit"] * gold["pages"][0]["width"] / image.width
            found = reader.read(image)
            if not found.read:
                continue  # no cached reply
            doors = carbon_door_scale(door_sides(found.elements, [page]))
            today = Extracted(method="detector", scale=doors or Scale(status="no_scale"),
                              rooms=found.rooms)  # fmt: skip
            printed = sum(room.area_source == "printed" for room in found.rooms)
            on = with_label_scale(today, [page]).scale
            always = with_label_scale(today, [page], always=True).scale
            rows.append({
                "file": gold["file"], "printed": printed,
                "label": error(label_scale(found.rooms, [page]), reference),
                "door": error(doors, reference), "off": error(today.scale, reference),
                "on": error(on, reference), "always": error(always, reference),
            })  # fmt: skip
    for row in rows:
        cells = [
            f"{row[key][0]:+.1%}{'' if row[key][1] else '!'}" if row[key] else "-"
            for key in ("label", "door", "off", "on", "always")
        ]
        print(row["file"].split("/")[-1][:48].ljust(48), str(row["printed"]).rjust(3), *cells)
    print("columns: printed rooms, label, door (Carbon), final off, on, always; ! = outside band")
    for key in ("label", "door", "off", "on", "always"):
        made = [row for row in rows if row[key] and row["label"]]  # the sheets labels cover
        if made:
            errors = [abs(row[key][0]) for row in made]
            inside = sum(row[key][1] for row in made)
            print(f"{key}: n={len(made)} median |error| {statistics.median(errors):.1%}, "
                  f"inside band {inside}/{len(made)}")  # fmt: skip


if __name__ == "__main__":
    main()

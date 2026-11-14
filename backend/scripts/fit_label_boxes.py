"""Threshold sweep for the label-box rule (app/core/pipeline/raster_scale.py `refused_boxes`).

    cd backend && uv run python scripts/fit_label_boxes.py --run <out>/extraction \
        --gold ../data/stoa/golden/v2/part1_extraction/gold [--pdf]

`--run` is the extraction folder of a pipeline run (`app.cli golden|answer --out <out>`) whose room
reader gives boxes (Gemini rooms; replies from the cache cost 0 USD). Every room whose area the
box measured (no polygon, area_source geometry_x_*) is measured again from its box at the run's
scale, the area main would give, and matched to the gold room that holds its box's centre. For
each (MIN_SIDE_M, MIN_COVER) pair the sweep prints how many of those areas the rule refuses, and
of them how many were right (within 2% of gold: Stoa's tolerance), close (within 20%) or label-
sized (under a third of gold), and how many label-sized ones it keeps. `--pdf`: PDF files only
(the scanned PDFs the rule is for). "printed" columns: the sheets on a printed scale (status
scaled), whose areas are said without "about". Pick the pair that refuses the most label-sized
areas and no right one.
"""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.adapters.extraction_v1 import ExtractionV1Reader
from app.core.drawing.model import Drawing, Room
from app.core.pipeline.raster_scale import BOX_RATIO, refused_boxes

SIDES = (0.0, 0.3, 0.5, 0.7, 0.9, 1.2)
COVERS = (0.0, 0.05, 0.1, 0.2, 0.3)
RIGHT, CLOSE, LABEL = 0.02, 0.20, 1 / 3
KEYS = ("ref", "right", "close", "label", "kept_label", "p_ref", "p_right", "p_label")


def files(folder: Path) -> list[str]:
    found = (json.loads(p.read_text(encoding="utf-8")).get("file") for p in folder.rglob("*.json"))
    return sorted(f for f in found if isinstance(f, str))


def inside(x: float, y: float, room: Room) -> bool:
    if room.polygon is None:
        x0, y0, x1, y1 = room.box
        return x0 <= x <= x1 and y0 <= y <= y1
    hit, points = False, room.polygon
    for (ax, ay), (bx, by) in zip(points, [*points[1:], points[0]], strict=True):
        if (ay > y) != (by > y) and x < ax + (y - ay) * (bx - ax) / (by - ay):
            hit = not hit
    return hit


def box_area(room: Room, drawing: Drawing) -> float | None:
    page = next((p for p in drawing.pages if p.page == room.page), None)
    if page is None or drawing.scale.m_per_unit is None:
        return None
    x0, y0, x1, y1 = room.box
    share = (x1 - x0) * (y1 - y0) / BOX_RATIO
    return share * page.width * page.height * drawing.scale.m_per_unit**2


def sheets(run: Path, gold: Path, pdf: bool) -> list[tuple[Drawing, list[Room], dict[str, float]]]:
    """Each run sheet with a scale, its rooms as the box would measure them (areas the box gave
    cleared), and the gold area of each such room it matched."""
    runs, golds = ExtractionV1Reader(run), ExtractionV1Reader(gold)
    out = []
    for file in files(run):
        if pdf and not file.lower().endswith(".pdf"):
            continue
        drawing, truth = runs.drawing(file), golds.drawing(file)
        if drawing is None or truth is None or drawing.scale.m_per_unit is None:
            continue
        rooms = [
            r.model_copy(update={"area_m2": None})
            if r.polygon is None and (r.area_source or "").startswith("geometry_x")
            else r
            for r in drawing.rooms
        ]
        matched: dict[str, float] = {}
        for room in rooms:
            if room.polygon is not None or room.area_m2 is not None:
                continue
            x, y = (room.box[0] + room.box[2]) / 2, (room.box[1] + room.box[3]) / 2
            hit = next(
                (g for g in truth.rooms if g.page == room.page and g.area_m2 and inside(x, y, g)),
                None,
            )
            if hit is not None and hit.area_m2:
                matched[room.id] = hit.area_m2
        out.append((drawing, rooms, matched))
    return out


def sweep(rows: Sequence[tuple[Drawing, list[Room], dict[str, float]]]) -> None:
    print("side_m cover | refused right close label | kept_label | printed: refused right label")
    for side in SIDES:
        for cover in COVERS:
            n = dict.fromkeys(KEYS, 0)
            for drawing, rooms, matched in rows:
                refused = refused_boxes(rooms, drawing.scale, drawing.pages, side, cover)
                printed = drawing.scale.status == "scaled"
                for room in rooms:
                    if room.id not in matched:
                        continue
                    area = box_area(room, drawing)
                    if area is None:
                        continue
                    error = abs(area / matched[room.id] - 1)
                    label = area < matched[room.id] * LABEL
                    if room.id in refused:
                        n["ref"] += 1
                        n["right"] += error <= RIGHT
                        n["close"] += error <= CLOSE
                        n["label"] += label
                        n["p_ref"] += printed
                        n["p_right"] += printed and error <= RIGHT
                        n["p_label"] += printed and label
                    else:
                        n["kept_label"] += label
            print(
                f"{side:6.2f} {cover:5.2f} | {n['ref']:7d} {n['right']:5d} {n['close']:5d} "
                f"{n['label']:5d} | {n['kept_label']:10d} | {n['p_ref']:15d} {n['p_right']:5d} "
                f"{n['p_label']:5d}"
            )


def main() -> None:
    args = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    args.add_argument("--run", type=Path, required=True, help="a run's extraction folder")
    args.add_argument("--gold", type=Path, required=True, help="the gold extraction folder")
    args.add_argument("--pdf", action="store_true", help="PDF files only")
    parsed = args.parse_args()
    rows = sheets(parsed.run, parsed.gold, parsed.pdf)
    rooms = sum(len(matched) for _, _, matched in rows)
    print(f"{len(rows)} sheets with a scale, {rooms} box-measured rooms matched to gold")
    sweep(rows)


if __name__ == "__main__":
    main()

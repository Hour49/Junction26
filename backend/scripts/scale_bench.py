"""Scale bench: for a run's sheets that have a reference scale, every scale candidate the
extraction lets us rebuild, the final scale and its source, the SIGNED relative error of each
against the reference (estimate / reference - 1: below 0 the scale is too small, lengths too
short, areas too small by (1 + error)^2), the band and whether the reference is inside it; then a
summary per source kind (median |error| per candidate, share inside the band) and the worst 5.

    PYTHONPATH=. uv run python scripts/scale_bench.py --run <run>/extraction \
        [--gold ../data/stoa/golden/v2/<gold extraction dir>] [--refs <references.json>]

--run holds extraction_v1 JSON files (any depth, as scripts/carbon_door_scale.py), matched by
their `file`. The reference is the gold's (carbon_door_scale.reference: m_per_unit, else
reference_m_per_unit, metres across the gold's page 1), else the references file's entry for the
file or its base name: {"<file>": {"m_per_unit": <m per unit of the run's page 1>, "how": "...",
"kind": optional, "dpi": optional}}. Hand references name partner files: keep that file in
.agents/, never in git. Scales compare as metres across page 1, as eval/stoa_eval/scale_scoring.py.

Candidates, in m per page unit (each None when the extraction cannot give it):
- final: the run's scale (its status, source and band printed beside it);
- door: DOOR_M over the median long side of the doors raster_scale.door_sides counts;
- carbon_door: CARBON_DOOR_M over the same sides (the extraction does not say whose doors they
  are, so both priors are tried on every sheet);
- ratio: the printed ratio (printed.ratio_of on the scale's text, else on a "printed scale ...:"
  note) at the dpi the run's source states ("at the image's N dpi") or the reference gives; a PDF
  page is 72 units to the inch;
- label_area: the median over rooms with a printed area of sqrt(area_m2 / outline area in units^2),
  the outline being the polygon, else the box over BOX_RATIO.
The bar values per bar are not in extraction_v1 (only the final scale says "printed scale bar").
The band is the scale's `uncertainty`; a scaled sheet without one gets scale_scoring's 2%.

Kind (references' "kind" wins): synthetic scan for scripts/make_scans.py's data/scans/, photo for
a path with "photo", scan for other pixel pages, vector for PDF pages.
Reads JSON only: no partner data leaves the machine.
"""

import argparse
import json
import math
import re
import statistics
from pathlib import Path
from typing import Any

from app.core.drawing.model import Element, Page
from app.core.pipeline.printed import INCH_M, POINTS_PER_INCH, ratio_of
from app.core.pipeline.raster_scale import BOX_RATIO, CARBON_DOOR_M, DOOR_M, door_sides

CANDIDATES = ("final", "door", "carbon_door", "ratio", "label_area")
SCALED_BAND = 0.02  # eval/stoa_eval/scale_scoring.py SCALE_TOLERANCE
STATED_DPI = re.compile(r"at the image's ([0-9.]+) dpi")
PRINTED_NOTE = re.compile(r"printed scale (.+?): read")  # "carbon: printed scale 1:200: read, ..."


def by_file(folder: Path) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for path in sorted(folder.rglob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("file"), str):
            found[data["file"]] = data
    return found


def metres(extraction: dict[str, Any], m_per_unit: float | None) -> float | None:
    """Metres across page 1 at `m_per_unit`; None without a value or a page."""
    pages = extraction.get("pages") or []
    if m_per_unit is None or not pages:
        return None
    return m_per_unit * pages[0]["width"]


def gold_metres(gold: dict[str, Any]) -> float | None:
    scale = gold["scale"]
    return metres(gold, scale.get("m_per_unit") or scale.get("reference_m_per_unit"))


def ratio_scale(run: dict[str, Any], dpi: float | None) -> float | None:
    scale = run["scale"]
    texts = [scale.get("text")] + [
        found.group(1) for note in run.get("notes", []) if (found := PRINTED_NOTE.search(note))
    ]
    ratio = next((r for text in texts if (r := ratio_of(text)) is not None), None)
    stated = STATED_DPI.search(scale.get("source") or "")
    unit = run["pages"][0]["unit"] if run.get("pages") else None
    per_inch = POINTS_PER_INCH if unit == "pt" else (float(stated.group(1)) if stated else dpi)
    return None if ratio is None or not per_inch else ratio * INCH_M / per_inch


def _area(polygon: list[list[float]]) -> float:
    """The shoelace area of a polygon given as [x, y] pairs."""
    pairs = zip(polygon, polygon[1:] + polygon[:1], strict=True)
    return abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in pairs)) / 2


def label_scale(run: dict[str, Any]) -> float | None:
    pages = {page["page"]: page for page in run.get("pages", [])}
    found = []
    for room in run.get("rooms", []):
        page = pages.get(room["page"])
        if room.get("area_source") != "printed" or not room.get("area_m2") or page is None:
            continue
        if room.get("polygon"):
            fraction = _area(room["polygon"])
        else:
            x0, y0, x1, y1 = room["box"]
            fraction = (x1 - x0) * (y1 - y0) / BOX_RATIO
        if fraction > 0:
            found.append(math.sqrt(room["area_m2"] / (fraction * page["width"] * page["height"])))
    return statistics.median(found) if found else None


def candidates(run: dict[str, Any], dpi: float | None = None) -> dict[str, float | None]:
    """Every candidate scale of a run's sheet, in m per page unit."""
    doors = [Element.model_validate(e) for e in run.get("elements", []) if e["class"] == "door"]
    sides = door_sides(doors, [Page.model_validate(page) for page in run.get("pages", [])])
    side = statistics.median(sides) if sides else None
    return {
        "final": run["scale"].get("m_per_unit"),
        "door": DOOR_M / side if side else None,
        "carbon_door": CARBON_DOOR_M / side if side else None,
        "ratio": ratio_scale(run, dpi),
        "label_area": label_scale(run),
    }


def kind_of(run: dict[str, Any]) -> str:
    file = run["file"].lower()
    if "data/scans/" in file:
        return "synthetic scan"
    if "photo" in file:  # not by .jpg: the HABS scans and make_scans' scans are JPEGs
        return "photo"
    pages = run.get("pages") or [{}]
    return "vector" if pages[0].get("unit") == "pt" else "scan"


def rows(
    run: dict[str, dict], gold: dict[str, dict], refs: dict[str, dict]
) -> list[dict[str, Any]]:
    """One row per run sheet with a reference: file, kind, status, source, band, the signed
    error per candidate (None when it has no value) and whether the final is inside the band."""
    out = []
    for file, sheet in sorted(run.items()):
        ref = refs.get(file) or refs.get(Path(file).name) or {}
        truth = gold_metres(gold[file]) if file in gold else metres(sheet, ref.get("m_per_unit"))
        if truth is None:
            continue
        scale = sheet["scale"]
        errors = {
            name: (value / truth - 1 if (value := metres(sheet, m)) is not None else None)
            for name, m in candidates(sheet, ref.get("dpi")).items()
        }
        band = scale.get("uncertainty") or (SCALED_BAND if scale["status"] == "scaled" else 0.0)
        final = errors["final"]
        out.append(
            {
                "file": file,
                "kind": ref.get("kind") or kind_of(sheet),
                "status": scale["status"],
                "source": scale.get("source") or "",
                "band": band,
                "errors": errors,
                "inside": final is not None and abs(final) <= band,
            }
        )
    return out


def _pct(value: float | None) -> str:
    return "-" if value is None else f"{value:+.1%}"


def summary(found: list[dict[str, Any]]) -> list[str]:
    lines = []
    for kind in sorted({row["kind"] for row in found}):
        group = [row for row in found if row["kind"] == kind]
        inside = sum(row["inside"] for row in group)
        medians = []
        for name in CANDIDATES:
            errors = [abs(e) for row in group if (e := row["errors"][name]) is not None]
            value = f"{statistics.median(errors):.1%}" if errors else "-"
            medians.append(f"{name}={value} (n={len(errors)})")
        lines.append(
            f"{kind}: {len(group)} sheets; inside the band {inside}/{len(group)} "
            f"({inside / len(group):.0%}); median |error| " + ", ".join(medians)
        )
    scored = [row for row in found if row["errors"]["final"] is not None]
    worst = sorted(scored, key=lambda row: -abs(row["errors"]["final"]))[:5]
    lines.append(
        "worst 5 (final): "
        + "; ".join(f"{row['file']} {_pct(row['errors']['final'])}" for row in worst)
    )
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--gold", type=Path)
    parser.add_argument("--refs", type=Path)
    args = parser.parse_args()
    gold = by_file(args.gold) if args.gold else {}
    refs = json.loads(args.refs.read_text(encoding="utf-8")) if args.refs else {}
    found = rows(by_file(args.run), gold, refs)
    if not found:
        print("no run sheet has a reference (gold or references file)")
        return
    print("file\tkind\tstatus\tband\tinside\t" + "\t".join(CANDIDATES) + "\tsource")
    for row in found:
        print(
            f"{row['file']}\t{row['kind']}\t{row['status']}\t{row['band']:.1%}\t"
            f"{'in' if row['inside'] else 'OUT'}\t"
            + "\t".join(_pct(row["errors"][name]) for name in CANDIDATES)
            + f"\t{row['source']}"
        )
    print("\n".join(summary(found)))


if __name__ == "__main__":
    main()

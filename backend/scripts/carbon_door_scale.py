"""SCALE_CARBON_DOORS measure and fit: on the sheets whose scale came from Carbon's doors (the
`on` run's scale source says "the Carbon reader found"), the SIGNED relative scale error against
the gold scale (estimate / reference - 1: below 0 the scale is too small, so are lengths and
areas), the `off` run's status beside it (it should be no_scale: refused), the share inside the
printed band, the median signed error, and the fit: the CARBON_DOOR_M that zeroes that median.
The golden v2 "no answer worse" check is the usual answers cmp, not this script.

    uv run python scripts/carbon_door_scale.py --off <run_off>/extraction --on <run_on>/extraction \
        --gold ../data/stoa/golden/v2/<gold extraction dir>

Each folder holds extraction_v1 JSON files (any depth), matched by their `file`. The reference is
the gold's m_per_unit (scaled, estimated or a valued not_to_scale), else its reference_m_per_unit;
scales compare as metres across page 1, as eval/stoa_eval/scale_scoring.py does. The scale is
CARBON_DOOR_M over the doors' median side, so it is proportional to CARBON_DOOR_M: the fit is the
door width the run used (read from its source, "a door is about X m wide") over the median of
estimate / reference. Reads JSON only: no partner data leaves the machine.
"""

import argparse
import json
import re
import statistics
from pathlib import Path
from typing import Any

CARBON = "the Carbon reader found"  # in CarbonDoorScale's scale source
DOOR_WIDTH = re.compile(r"a door is about ([0-9.]+) m wide")  # the width the run used


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


def reference(gold: dict[str, Any]) -> float | None:
    scale = gold["scale"]
    return metres(gold, scale.get("m_per_unit") or scale.get("reference_m_per_unit"))


def rows(off: dict, on: dict, gold: dict) -> list[tuple[str, str, float, float, float]]:
    """(file, the off run's status, signed relative error, band, the door width the run used)
    per sheet scaled from Carbon's doors that has a gold reference."""
    out = []
    for file, run in sorted(on.items()):
        scale = run["scale"]
        source = scale.get("source") or ""
        width = DOOR_WIDTH.search(source)
        if CARBON not in source or width is None or file not in gold:
            continue
        truth, guess = reference(gold[file]), metres(run, scale.get("m_per_unit"))
        if truth is None or guess is None:
            continue
        before = off.get(file, {}).get("scale", {}).get("status", "missing")
        band = scale.get("uncertainty") or 0.0
        out.append((file, before, guess / truth - 1, band, float(width.group(1))))
    return out


def fit(found: list[tuple[str, str, float, float, float]]) -> float:
    """The door width that zeroes the median signed error. The scale is proportional to the
    width, so a sheet's estimate / reference per metre of width is (1 + error) / width, and the
    width whose median ratio is 1 is one over their median."""
    return 1 / statistics.median((1 + error) / width for _, _, error, _, width in found)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    for name in ("--off", "--on", "--gold"):
        parser.add_argument(name, type=Path, required=True)
    args = parser.parse_args()
    found = rows(by_file(args.off), by_file(args.on), by_file(args.gold))
    for file, before, error, band, _ in found:
        mark = "in" if abs(error) <= band else "OUT"
        print(f"{file}\toff={before}\terror={error:+.1%}\tband={band:.1%}\t{mark}")
    if not found:
        print("no sheet scaled from Carbon's doors with a gold reference")
        return
    inside = sum(abs(error) <= band for _, _, error, band, _ in found)
    errors = [error for _, _, error, _, _ in found]
    print(
        f"{len(found)} sheets; inside the band {inside}/{len(found)} ({inside / len(found):.0%}); "
        f"median signed error {statistics.median(errors):+.1%}; off refused (no_scale) on "
        f"{sum(before == 'no_scale' for _, before, _, _, _ in found)}"
    )
    widths = {width for *_, width in found}
    print(f"fit: CARBON_DOOR_M = {fit(found):.3f} (the run used {', '.join(map(str, widths))})")


if __name__ == "__main__":
    main()

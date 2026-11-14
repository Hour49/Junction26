"""SCALE_CARBON_DOORS measure: on the sheets whose scale came from Carbon's doors (the `on` run's
scale source says "the Carbon reader found"), the relative scale error against the gold scale, the
`off` run's status beside it (it should be no_scale: refused), and the share inside the printed
band. The golden v2 "no answer worse" check is the usual answers cmp, not this script.

    uv run python scripts/carbon_door_scale.py --off <run_off>/extraction --on <run_on>/extraction \
        --gold ../data/stoa/golden/v2/<gold extraction dir>

Each folder holds extraction_v1 JSON files (any depth), matched by their `file`. The reference is
the gold's m_per_unit (scaled, estimated or a valued not_to_scale), else its reference_m_per_unit;
scales compare as metres across page 1, as eval/stoa_eval/scale_scoring.py does. Reads JSON only:
no partner data leaves the machine.
"""

import argparse
import json
import statistics
from pathlib import Path
from typing import Any

CARBON = "the Carbon reader found"  # in CarbonDoorScale's scale source


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


def rows(off: dict, on: dict, gold: dict) -> list[tuple[str, str, float, float]]:
    """(file, the off run's status, relative error, band) per sheet scaled from Carbon's doors
    that has a gold reference."""
    out = []
    for file, run in sorted(on.items()):
        scale = run["scale"]
        if CARBON not in (scale.get("source") or "") or file not in gold:
            continue
        truth, guess = reference(gold[file]), metres(run, scale.get("m_per_unit"))
        if truth is None or guess is None:
            continue
        before = off.get(file, {}).get("scale", {}).get("status", "missing")
        out.append((file, before, abs(guess / truth - 1), scale.get("uncertainty") or 0.0))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    for name in ("--off", "--on", "--gold"):
        parser.add_argument(name, type=Path, required=True)
    args = parser.parse_args()
    found = rows(by_file(args.off), by_file(args.on), by_file(args.gold))
    for file, before, error, band in found:
        mark = "in" if error <= band else "OUT"
        print(f"{file}\toff={before}\terror={error:.1%}\tband={band:.1%}\t{mark}")
    if not found:
        print("no sheet scaled from Carbon's doors with a gold reference")
        return
    inside = sum(error <= band for _, _, error, band in found)
    errors = [error for _, _, error, _ in found]
    print(
        f"{len(found)} sheets; inside the band {inside}/{len(found)} ({inside / len(found):.0%}); "
        f"median error {statistics.median(errors):.1%}; off refused (no_scale) on "
        f"{sum(before == 'no_scale' for _, before, _, _ in found)}"
    )


if __name__ == "__main__":
    main()

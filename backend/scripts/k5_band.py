"""K5 metric and threshold sweep: the share of true room areas inside the printed band on CubiCasa
val pages with gold areas, before (main: the prior's band by door count) and after the door-spread
rule of app/core/pipeline/raster_scale.py (band widened past DISAGREE, no estimate past REFUSE).

    cd backend && uv run --locked python scripts/k5_band.py --arm <arm dir> \
        --gold ../data/stoa/extraction_gold/cubicasa5k --split ../data/stoa/exp/split.json [--sweep]

--arm: extraction_v1 files of the val images with the detected doors (the shipped detector's arm).
--gold: the dev gold extraction (rooms with area_m2 and an outline). --split: the exp split; its val
part is cut in two halves by image the way stoa_eval's gate does (`gate.halves`: seeded order,
GATE_SEED; reimplemented here, the backend does not import eval). --files <list> replaces the split
(one dataset path per line; the halves are then cut from it).

Each gold room's outline (page fractions) at the arm's door scale is the estimate, so only the door
estimate and its band are measured, not a room reader. Inside: |true - estimate| <= uncertainty x
estimate. "inside" is the share of the answered rooms; "refused" the share of rooms with no
estimate. Sheets with no detected door are left out (no estimate before or after).

Without --sweep: the shipped DISAGREE / REFUSE on val (both halves). With --sweep: every pair of
DISAGREE 0.10..0.40 and REFUSE 0.30..0.80 (step 0.05) on half A, then the best pair (highest inside
share with refused < 10%; ties: fewer refused) checked on half B against main. The thresholds are
set by assigning the module's constants (estimate_scale reads them at call time).
"""

import argparse
import hashlib
import json
import statistics
from dataclasses import dataclass
from pathlib import Path

from app.adapters.extraction_v1 import ExtractionV1Reader
from app.core.drawing.model import Page, Room, Scale
from app.core.pipeline import raster_scale as rs

GATE_SEED = 20261114  # eval/stoa_eval/gate.py
MAX_REFUSED = 0.10
DISAGREES = [round(0.10 + 0.05 * i, 2) for i in range(7)]  # 0.10 .. 0.40
REFUSES = [round(0.30 + 0.05 * i, 2) for i in range(11)]  # 0.30 .. 0.80


@dataclass
class Sheet:
    file: str
    sides: list[float]
    pages: tuple[Page, ...]
    rooms: list[Room]  # gold rooms, area_m2 cleared
    truths: list[float]


@dataclass
class Result:
    rooms: int = 0
    answered: int = 0
    inside: int = 0
    refused: int = 0

    def line(self) -> str:
        share = self.inside / self.answered if self.answered else 0.0
        return (
            f"inside {self.inside}/{self.answered} ({share:.1%}), "
            f"refused {self.refused}/{self.rooms} ({self.refused_share:.1%})"
        )

    @property
    def share(self) -> float:
        return self.inside / self.answered if self.answered else 0.0

    @property
    def refused_share(self) -> float:
        return self.refused / self.rooms if self.rooms else 0.0


def halves(files: list[str]) -> tuple[list[str], list[str]]:
    """stoa_eval.gate.halves: files in seeded order, first half and second half."""
    ranked = sorted(
        files, key=lambda f: hashlib.sha256(f"{GATE_SEED}:gate:{f}".encode()).hexdigest()
    )
    middle = len(ranked) // 2
    return sorted(ranked[:middle]), sorted(ranked[middle:])


def load(arm: ExtractionV1Reader, gold: ExtractionV1Reader, files: list[str]) -> list[Sheet]:
    sheets: list[Sheet] = []
    for file in files:
        found, truth = arm.drawing(file), gold.drawing(file)
        if found is None or truth is None:
            continue
        rooms = [r for r in truth.rooms if r.area_m2 and r.polygon]
        if not rooms:
            continue
        sides = rs.door_sides(found.elements, found.pages)
        if not sides:  # no door: no estimate on main either, so the rule changes nothing here
            continue
        bare = [r.model_copy(update={"area_m2": None}) for r in rooms]
        truths = [r.area_m2 or 0.0 for r in rooms]
        sheets.append(Sheet(file, sides, found.pages, bare, truths))
    return sheets


def measure(sheets: list[Sheet], main: bool = False) -> Result:
    """The rooms inside their band; `main`: the prior's band, never refused (before K5)."""
    out = Result()
    for sheet in sheets:
        out.rooms += len(sheet.rooms)
        if main:
            prior = rs.SPREAD_FEW if len(sheet.sides) < rs.FEW_DOORS else rs.SPREAD_MANY
            m = rs.DOOR_M / statistics.median(sheet.sides)
            scale = Scale(status="estimated", m_per_unit=m, uncertainty=prior)
        else:
            scale = rs.estimate_scale(sheet.sides)
        if scale is None:
            out.refused += len(sheet.rooms)
            continue
        for room, true in zip(rs.rooms_with_areas(sheet.rooms, scale, sheet.pages), sheet.truths,
                              strict=True):  # fmt: skip
            out.answered += 1
            estimate, spread = room.area_m2, room.area_uncertainty
            if estimate is not None and spread is not None:
                out.inside += abs(true - estimate) <= spread * estimate
    return out


def with_thresholds(sheets: list[Sheet], disagree: float, refuse: float) -> Result:
    rs.DISAGREE, rs.REFUSE = disagree, refuse
    return measure(sheets)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--arm", type=Path, required=True)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--split", type=Path, help="data/stoa/exp/split.json (its val part)")
    parser.add_argument("--files", type=Path, help="a file list instead of the split's val")
    parser.add_argument("--sweep", action="store_true")
    args = parser.parse_args()
    if args.files:
        files = args.files.read_text().split()
    elif args.split:
        files = json.loads(args.split.read_text())["parts"]["val"]["files"]
    else:
        parser.error("give --split or --files")
    arm, gold = ExtractionV1Reader(args.arm), ExtractionV1Reader(args.gold)
    half_a, half_b = (load(arm, gold, half) for half in halves(files))
    shipped = (rs.DISAGREE, rs.REFUSE)
    print(f"val sheets with doors and gold areas: half A {len(half_a)}, half B {len(half_b)}")
    if not args.sweep:
        for name, sheets in (("A", half_a), ("B", half_b), ("A+B", half_a + half_b)):
            print(f"half {name}: main {measure(sheets, main=True).line()}")
            print(f"half {name}: K5 {shipped} {measure(sheets).line()}")
        return
    print(f"half A main: {measure(half_a, main=True).line()}")
    rows: list[tuple[float, float, Result]] = []
    for disagree in DISAGREES:
        for refuse in REFUSES:
            got = with_thresholds(half_a, disagree, refuse)
            rows.append((disagree, refuse, got))
            print(f"A DISAGREE {disagree:.2f} REFUSE {refuse:.2f}: {got.line()}")
    allowed = [row for row in rows if row[2].refused_share < MAX_REFUSED]
    if not allowed:
        print(f"no pair keeps refused under {MAX_REFUSED:.0%} on half A")
        return
    disagree, refuse, best = max(allowed, key=lambda row: (row[2].share, -row[2].refused_share))
    print(f"best on A: DISAGREE {disagree:.2f} REFUSE {refuse:.2f}: {best.line()}")
    print(f"half B main: {measure(half_b, main=True).line()}")
    print(f"half B best pair: {with_thresholds(half_b, disagree, refuse).line()}")
    print(f"half B shipped {shipped}: {with_thresholds(half_b, *shipped).line()}")


if __name__ == "__main__":
    main()

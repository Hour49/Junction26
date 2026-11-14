"""K5: does the doors' width spread change how far off the door scale is, and what 68% band should
each page print? Measured on CubiCasa val pages with gold room areas.

    cd backend && PYTHONPATH=. uv run --locked python scripts/k5_band.py --arm <arm dir> \
        --gold ../data/stoa/extraction_gold/cubicasa5k --split ../data/stoa/exp/split.json [--fit]

--arm: extraction_v1 files of the val images with the detected doors (the demo config's detector,
C1-T1). --gold: the dev gold extraction (rooms with area_m2 and an outline). --split: the exp split;
its val part is cut in two halves by image the way stoa_eval's gate does (`gate.halves`: seeded
order, GATE_SEED; reimplemented here, the backend does not import eval). --files <list> replaces
the split (one dataset path per line; the halves are then cut from it).

A page's scale error is how far the door scale is from the gold: the median over its gold rooms of
log(true area / outline area at the door scale) / 2 (the gold outlines, so no room reader's error
is in it). A page is inside a band b when |error| <= log(1 + b). The right band covers 68% of the
pages, as narrow as that allows: the 68% quantile of |error|. Pages are grouped by door count (1-4,
5 or more: FEW_DOORS) and spread bucket (`door_spread` cut at --edges). Sheets with no detected
door are left out (no estimate either way).

Without --fit: per group and bucket, the page coverage and the mean band of the shipped bands
(raster_scale.BANDS_FEW / BANDS_MANY) and of main's (SPREAD_FEW / SPREAD_MANY), on both halves,
plus the rooms inside their area band (the band rooms_with_areas prints: scale twice and the
outline's spread; on gold outlines it is wider than the outline needs, so above 68%).
With --fit: each bucket's band fitted on half A and checked on half B, and the other way; the
fitted band is the mean of the two. Spread changes the error when, in a group, a bucket with at
least MIN_PAGES pages on each half fits a band more than SPREAD_MATTERS times (or under 1 /
SPREAD_MATTERS of) the group's own band on both halves; otherwise every bucket gets its group's
band. A bucket whose fitted band is above NOT_AN_ANSWER is listed with the rooms main had inside
its band there: refusing it would drop those. It prints the constants to paste into
app/core/pipeline/raster_scale.py.
"""

import argparse
import hashlib
import json
import math
import statistics
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from app.adapters.extraction_v1 import ExtractionV1Reader
from app.core.drawing.model import Page, Room
from app.core.pipeline import raster_scale as rs

GATE_SEED = 20261114  # eval/stoa_eval/gate.py
TARGET = 0.68
MIN_PAGES = 15  # a bucket with fewer pages on a half gets its group's band
SPREAD_MATTERS = 1.25  # a bucket's band this many times its group's (or under 1/x) is its own
# A relative scale error above this is no answer: the page-size prior's 68% error starts at 37%
# (raster_scale's docstring), and the area is then off by about 90%
NOT_AN_ANSWER = 0.37
GROUPS = ("few", "many")


@dataclass
class Sheet:
    file: str
    sides: list[float]
    pages: tuple[Page, ...]
    rooms: list[Room]  # gold rooms with an outline
    truths: list[float]  # their gold areas

    @property
    def group(self) -> str:
        return "few" if len(self.sides) < rs.FEW_DOORS else "many"

    def bucket(self, edges: Sequence[float]) -> int:
        return sum(rs.door_spread(self.sides) >= edge for edge in edges)

    def outlines(self) -> list[float]:
        """Each room's outline area in page units squared."""
        page = {p.page: p for p in self.pages}
        return [_shoelace(r.polygon or ()) * page[r.page].width * page[r.page].height
                for r in self.rooms]  # fmt: skip

    def error(self) -> float:
        """log(true scale / door scale), the median over the page's rooms."""
        m = rs.DOOR_M / statistics.median(self.sides)
        pairs = zip(self.truths, self.outlines(), strict=True)
        logs = [0.5 * math.log(true / (unit * m * m)) for true, unit in pairs if unit > 0]
        return statistics.median(logs)

    def rooms_inside(self, band: float) -> tuple[int, int]:
        """(rooms inside their printed area band, rooms) at scale band `band`; the area band is
        rooms_with_areas' (the scale's spread twice, with the outline's)."""
        m = rs.DOOR_M / statistics.median(self.sides)
        area_band = math.expm1(math.hypot(2 * math.log1p(band), rs.OUTLINE_SPREAD))
        inside = sum(abs(true - unit * m * m) <= area_band * unit * m * m
                     for true, unit in zip(self.truths, self.outlines(), strict=True))  # fmt: skip
        return inside, len(self.rooms)


def _shoelace(polygon: Sequence[tuple[float, float]]) -> float:
    pairs = zip(polygon, [*polygon[1:], polygon[0]], strict=True)
    return abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in pairs)) / 2


def quantile(values: Sequence[float], q: float = TARGET) -> float:
    """Nearest rank: the smallest value with a share `q` of the values at or below it."""
    ranked = sorted(values)
    return ranked[max(0, math.ceil(q * len(ranked)) - 1)]


def fitted_band(sheets: Sequence[Sheet]) -> float | None:
    """The relative scale error 68% of `sheets` are within; None for no sheet."""
    if not sheets:
        return None
    return round(math.expm1(quantile([abs(sheet.error()) for sheet in sheets])), 4)


def coverage(sheets: Sequence[Sheet], band_of: Callable[[Sheet], float]) -> str:
    """Pages inside their band, the mean band, and rooms inside their area band, in words."""
    if not sheets:
        return "no pages"
    bands = [band_of(sheet) for sheet in sheets]
    inside = sum(abs(s.error()) <= math.log1p(b) for s, b in zip(sheets, bands, strict=True))
    rooms = [s.rooms_inside(b) for s, b in zip(sheets, bands, strict=True)]
    rin, rall = sum(r[0] for r in rooms), sum(r[1] for r in rooms)
    return (
        f"pages {inside}/{len(sheets)} ({inside / len(sheets):.0%}) mean band "
        f"±{statistics.mean(bands):.1%}; rooms {rin}/{rall} ({rin / max(rall, 1):.0%})"
    )


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
        sides = rs.door_sides(found.elements, found.pages)
        if rooms and sides:
            sheets.append(Sheet(file, sides, found.pages, rooms, [r.area_m2 or 0.0 for r in rooms]))
    return sheets


def main_band(sheet: Sheet) -> float:
    return rs.SPREAD_FEW if sheet.group == "few" else rs.SPREAD_MANY


def fit(a: list[Sheet], b: list[Sheet], edges: Sequence[float]) -> dict[str, list[float]]:
    """The bands per group, one per bucket, from half A and half B both ways; prints the table."""
    buckets = range(len(edges) + 1)
    bands: dict[str, list[float]] = {}
    for group in GROUPS:
        ga, gb = ([s for s in h if s.group == group] for h in (a, b))
        pooled_a, pooled_b = fitted_band(ga), fitted_band(gb)
        if pooled_a is None or pooled_b is None:
            print(f"{group}: no pages on a half; keeps main's band")
            bands[group] = [rs.SPREAD_FEW if group == "few" else rs.SPREAD_MANY] * len(buckets)
            continue
        pooled = round((pooled_a + pooled_b) / 2, 4)
        print(f"{group}: group band A ±{pooled_a:.1%} B ±{pooled_b:.1%} -> ±{pooled:.1%}")
        own: list[float] = []
        for k in buckets:
            ka, kb = (
                [s for s in ga if s.bucket(edges) == k],
                [s for s in gb if s.bucket(edges) == k],
            )
            fa, fb = fitted_band(ka), fitted_band(kb)
            print(f"  bucket {k} ({_bucket_name(edges, k)}): pages A {len(ka)} B {len(kb)}")
            print(f"    main     A: {coverage(ka, main_band)} | B: {coverage(kb, main_band)}")
            if fa is None or fb is None:
                own.append(pooled)
                print("    no pages on a half: the group's band")
                continue
            print(f"    fit A ±{fa:.1%} on B: {coverage(kb, lambda _, fa=fa: fa)}")
            print(f"    fit B ±{fb:.1%} on A: {coverage(ka, lambda _, fb=fb: fb)}")
            band = round((fa + fb) / 2, 4)
            matters = min(len(ka), len(kb)) >= MIN_PAGES and all(
                f > SPREAD_MATTERS * p or f < p / SPREAD_MATTERS
                for f, p in ((fa, pooled_a), (fb, pooled_b))
            )
            own.append(band if matters else pooled)
            verdict = (
                "its own band" if matters else "the group's band (spread does not matter here)"
            )
            print(f"    fitted ±{band:.1%}: {verdict}")
            if band > NOT_AN_ANSWER:
                kept = [s.rooms_inside(main_band(s)) for s in (*ka, *kb)]
                print(
                    f"    above NOT_AN_ANSWER ±{NOT_AN_ANSWER:.0%}: refusing it would drop "
                    f"{sum(r[0] for r in kept)} rooms main had inside its band, of "
                    f"{sum(r[1] for r in kept)}"
                )
        bands[group] = own
    return bands


def _bucket_name(edges: Sequence[float], k: int) -> str:
    low = "0" if k == 0 else f"{edges[k - 1]:g}"
    return f"spread {low}+" if k == len(edges) else f"spread {low}-{edges[k]:g}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--arm", type=Path, required=True)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--split", type=Path, help="data/stoa/exp/split.json (its val part)")
    parser.add_argument("--files", type=Path, help="a file list instead of the split's val")
    parser.add_argument("--fit", action="store_true")
    parser.add_argument("--edges", default=",".join(f"{e:g}" for e in rs.SPREAD_EDGES))
    args = parser.parse_args()
    if args.files:
        files = args.files.read_text().split()
    elif args.split:
        files = json.loads(args.split.read_text())["parts"]["val"]["files"]
    else:
        parser.error("give --split or --files")
    edges = tuple(float(e) for e in args.edges.split(","))
    arm, gold = ExtractionV1Reader(args.arm), ExtractionV1Reader(args.gold)
    half_a, half_b = (load(arm, gold, half) for half in halves(files))
    print(f"val sheets with doors and gold areas: half A {len(half_a)}, half B {len(half_b)}")
    if not args.fit:
        for name, sheets in (("A", half_a), ("B", half_b)):
            for k in range(len(edges) + 1):
                some = [s for s in sheets if s.bucket(edges) == k]
                print(f"half {name} {_bucket_name(edges, k)}: main {coverage(some, main_band)}")
                print(f"half {name} {_bucket_name(edges, k)}: shipped "
                      f"{coverage(some, lambda s: rs.door_band(s.sides))}")  # fmt: skip
        return
    bands = fit(half_a, half_b, edges)
    print("\n# paste into app/core/pipeline/raster_scale.py")
    print(f"SPREAD_EDGES = {tuple(edges)}")
    print(f"BANDS_FEW = {tuple(bands['few'])}")
    print(f"BANDS_MANY = {tuple(bands['many'])}")


if __name__ == "__main__":
    main()

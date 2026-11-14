"""Printed scale on raster sheets (r8 brief AY): Carbon reads the printed scale and the scale bars
of a page, then each bar's two furthest labelled ticks on a full-resolution tile; the backend's
core (app/core/pipeline/printed.py) turns that into metres per pixel. Scored on golden v2's dev
Swiss Dwellings PNGs (gold scale from the DXF) and printed for the 4 inbox sheets (by eye).

Run from backend/ so the core imports: `cd backend && PYTHONPATH=$PWD JUNCTION_ROOT=<main clone>
uv run python ../prototypes/printed-scale/measure.py [--limit N] [--inbox]`. Calls go through prototypes/carbon-first/cf.py (cached by image
+ prompt, ledgered); this script stops at CAP_USD of its own spend (exp tag EXP).
"""

import io
import json
import os
import statistics
import sys
from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = None  # the inbox sheets are 140 Mpx, read locally
# the clone that holds data/ and the research harness (a worktree has neither): JUNCTION_ROOT
R = Path(os.environ.get("JUNCTION_ROOT", Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(R / "prototypes/carbon-first"))
import cf  # noqa: E402

from app.core.drawing.model import Page  # noqa: E402
from app.core.pipeline.printed import (  # noqa: E402
    PrintedSheet,
    ScaleBar,
    printed_scale,
    ratio_of,
    trusted_dpi,
)

EXP = "printed-scale"
CAP_USD = 3.0
MODEL = "gemini-4-carbon"
MAX_SIDE = 3072
GOLD = R / "data/stoa/golden/v2/part1_extraction"
DATASET = R / "data/stoa/full/junction-dataset"
INBOX = R / "data/inbox/hard-photos-20261114"
OUT = R / "data/stoa/exp/printed-scale"

PAGE_PROMPT = """This is an architectural drawing sheet. Report how it states its scale, in JSON.
All box_2d values are [ymin, xmin, ymax, xmax] in 0-1000 coordinates of this image.
- printed_scale: the scale as printed (for example "1:100", "1/4\\" = 1'-0\\"", "1\\" = 40'"), the one for the floor plan when several are printed; null when none is printed.
- scale_bars: every graphic scale bar (a ruler-like bar with numbered ticks): box_2d around the bar and its numbers, labels: its numbers and unit as printed. [] when there is none."""
PAGE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "printed_scale": {"type": "STRING", "nullable": True},
        "scale_bars": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
            "box_2d": {"type": "ARRAY", "items": {"type": "INTEGER"}},
            "labels": {"type": "STRING"}}, "required": ["box_2d", "labels"]}},
    },
    "required": ["printed_scale", "scale_bars"],
}  # fmt: skip
TILE_PROMPT = """This crop shows a graphic scale bar of an architectural drawing. Find the two numbered tick marks of the bar that are furthest apart (usually 0 and the largest number). For each: label as printed, metres (its value converted to metres: feet x 0.3048, inches x 0.0254), and point: [y, x] of the tick mark itself on the bar's edge, in 0-1000 coordinates of this crop. Answer in JSON."""
TILE_SCHEMA = {
    "type": "OBJECT",
    "properties": {"ticks": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
        "label": {"type": "STRING"}, "metres": {"type": "NUMBER"},
        "point": {"type": "ARRAY", "items": {"type": "NUMBER"}}},
        "required": ["label", "metres", "point"]}}},
    "required": ["ticks"],
}  # fmt: skip


def jpeg(image: Image.Image, max_side: int = MAX_SIDE) -> tuple[bytes, float]:
    """The image as JPEG, its long side at most max_side; and the factor applied."""
    factor = min(1.0, max_side / max(image.size))
    shown = image.convert("RGB")
    if factor < 1.0:
        shown = shown.resize((round(image.width * factor), round(image.height * factor)), Image.LANCZOS)
    out = io.BytesIO()
    shown.save(out, "JPEG", quality=90)
    return out.getvalue(), factor


def mine() -> float:
    ledger = cf.LEDGER
    if not ledger.exists():
        return 0.0
    rows = [json.loads(line) for line in ledger.read_text().splitlines() if line.strip()]
    return sum(row.get("usd_std", row.get("usd", 0.0)) for row in rows if row.get("exp") == EXP)


def call(images: list[bytes], prompt: str, schema: dict, item: str, res: str | None = None) -> dict:
    if mine() >= CAP_USD:
        raise SystemExit(f"own cap {CAP_USD} USD reached")
    return cf.call(MODEL, images, prompt, schema, think="low", res=res, exp=EXP, item=item)


def read(path: Path) -> dict:
    """The printed scale text and each bar's ends (page fractions) with their length."""
    image = Image.open(path)
    width, height = image.size
    page_jpeg, _ = jpeg(image)
    page = call([page_jpeg], PAGE_PROMPT, PAGE_SCHEMA, f"{path.name}:page")
    found = page["json"] or {"printed_scale": None, "scale_bars": []}
    bars: list[ScaleBar] = []
    calls = [page]
    for n, bar in enumerate(found.get("scale_bars") or []):
        box = bar.get("box_2d") or []
        if len(box) != 4:
            continue
        y0, x0, y1, x1 = (v / 1000 for v in box)
        pad_x, pad_y = 0.15 * (x1 - x0) + 0.005, 1.0 * (y1 - y0) + 0.005
        left, top = max(0.0, x0 - pad_x), max(0.0, y0 - pad_y)
        right, bottom = min(1.0, x1 + pad_x), min(1.0, y1 + pad_y)
        crop = image.crop((round(left * width), round(top * height), round(right * width), round(bottom * height)))
        tile, _ = jpeg(crop)
        reply = call([tile], TILE_PROMPT, TILE_SCHEMA, f"{path.name}:bar{n}", res="high")
        calls.append(reply)
        ticks = [t for t in (reply["json"] or {}).get("ticks", []) if len(t.get("point") or []) == 2]
        if len(ticks) < 2:
            continue
        a, b = ticks[0], ticks[-1]
        length = abs(float(b["metres"]) - float(a["metres"]))
        if length <= 0:
            continue

        def on_page(point: list[float]) -> tuple[float, float]:
            y, x = point[0] / 1000, point[1] / 1000
            return left + x * (right - left), top + y * (bottom - top)

        bars.append(ScaleBar(page=1, start=on_page(a["point"]), end=on_page(b["point"]), length_m=length,
                             text=bar.get("labels")))  # fmt: skip
    dpi = image.info.get("dpi")
    return {
        "size": [width, height],
        "dpi": None if dpi is None else [float(v) for v in dpi],
        "printed_scale": found.get("printed_scale"),
        "bars": [bar.model_dump() for bar in bars],
        "usd": sum(c.get("usd_std", c.get("usd", 0.0)) for c in calls if not c.get("cached")),
        "cached": all(c.get("cached") for c in calls),
    }


def scale_of(row: dict) -> tuple[float | None, float | None, str | None]:
    """(m/px from the bars and text as the backend takes them, m/px from the bars only, source)."""
    page = Page(page=1, width=row["size"][0], height=row["size"][1], unit="px")
    dpi = trusted_dpi(tuple(row["dpi"]) if row["dpi"] else None)
    sheet = PrintedSheet(printed_scale=row["printed_scale"], bars=tuple(ScaleBar(**b) for b in row["bars"]))
    got = printed_scale(sheet, [page], dpi)
    bars_only = printed_scale(sheet.model_copy(update={"printed_scale": None}), [page], None)
    return (None if got is None else got.m_per_unit, None if bars_only is None else bars_only.m_per_unit,
            None if got is None else got.source)  # fmt: skip


def swiss() -> list[tuple[Path, float]]:
    rows = [json.loads(line) for line in (GOLD / "files.jsonl").read_text().splitlines()]
    picked = [r for r in rows if r["source"] == "swiss_dwellings" and r["split"] == "dev" and r["file"].endswith(".png")]
    out = []
    for r in picked:
        stem = Path(r["file"]).name
        gold = json.loads((GOLD / "gold/swiss_dwellings" / f"{stem}.json").read_text())
        out.append((DATASET / r["file"], gold["scale"]["m_per_unit"]))
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    results = []
    for path, gold in swiss()[:limit]:
        row = read(path)
        got, bars_only, source = scale_of(row)
        row |= {"file": path.name, "gold": gold, "m_per_px": got, "bars_m_per_px": bars_only, "source": source,
                "error": None if got is None else got / gold - 1,
                "bars_error": None if bars_only is None else bars_only / gold - 1,
                "ratio": ratio_of(row["printed_scale"])}  # fmt: skip
        results.append(row)
        print(f"{path.name[:40]:40} text={row['printed_scale']!s:12} bars={len(row['bars'])} "
              f"err={row['error'] if row['error'] is None else round(100 * row['error'], 2)}% "
              f"bars_err={row['bars_error'] if row['bars_error'] is None else round(100 * row['bars_error'], 2)}% "
              f"${row['usd']:.3f}", flush=True)  # fmt: skip
    if "--inbox" in sys.argv:
        for path in sorted(INBOX.glob("*.png")):
            row = read(path)
            got, bars_only, source = scale_of(row)
            row |= {"file": path.name, "m_per_px": got, "bars_m_per_px": bars_only, "source": source,
                    "ratio": ratio_of(row["printed_scale"])}  # fmt: skip
            results.append(row)
            print(f"INBOX {path.name[:44]:44} text={row['printed_scale']!s:14} bars={len(row['bars'])} "
                  f"m/px={got} bars={bars_only} ${row['usd']:.3f}", flush=True)  # fmt: skip
    (OUT / "results.json").write_text(json.dumps(results, indent=1))
    scored = [r for r in results if "gold" in r]
    errs = [abs(r["error"]) for r in scored if r["error"] is not None]
    berrs = [abs(r["bars_error"]) for r in scored if r["bars_error"] is not None]
    print(f"swiss: {len(scored)} sheets; a scale found on {len(errs)}; |error| median "
          f"{statistics.median(errs) * 100 if errs else float('nan'):.2f}% max {max(errs) * 100 if errs else float('nan'):.2f}%; "
          f"bars only: found {len(berrs)}, median {statistics.median(berrs) * 100 if berrs else float('nan'):.2f}% "
          f"max {max(berrs) * 100 if berrs else float('nan'):.2f}%; within 2%: {sum(e <= 0.02 for e in errs)}; "
          f"own spend {mine():.3f} USD")  # fmt: skip


if __name__ == "__main__":
    main()
